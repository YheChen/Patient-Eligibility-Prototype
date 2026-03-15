from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
import re
from statistics import mean
from typing import Any, Optional

from fastapi import HTTPException, status

from app.schemas.common import Warning
from app.schemas.extraction import ExtractionResponse
from app.schemas.insurance import Insurance
from app.schemas.patient import Patient
from app.services.normalization_service import normalize_insurance, normalize_patient
from app.services.storage_service import StoredDocument

DATE_PATTERNS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%m-%d-%Y",
    "%m-%d-%y",
    "%Y/%m/%d",
    "%Y%m%d",
    "%b %d %Y",
    "%B %d %Y",
]

DATE_REGEXES = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    re.compile(r"\b\d{1,2}-\d{1,2}-\d{2,4}\b"),
    re.compile(r"\b\d{8}\b"),
    re.compile(
        r"\b(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)[A-Z]*\s+\d{1,2},?\s+\d{4}\b",
        re.IGNORECASE,
    ),
]

CITY_STATE_ZIP_REGEX = re.compile(
    r"([A-Za-z .'-]+?)\s*,?\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\b",
    re.IGNORECASE,
)
IDENTIFIER_REGEX = re.compile(r"[A-Za-z0-9-]+")
STREET_ADDRESS_REGEX = re.compile(
    r"\d+\s+[A-Za-z0-9.#'\- ]+\b(?:ST|STREET|RD|ROAD|AVE|AVENUE|BLVD|DR|DRIVE|LN|LANE|CT|COURT|PL|PLACE|PKWY|PARKWAY|WAY|CIR|CIRCLE)\b",
    re.IGNORECASE,
)

LABEL_HINTS = (
    "NAME",
    "DOB",
    "DATE OF BIRTH",
    "ADDRESS",
    "CITY",
    "STATE",
    "ZIP",
    "POSTAL",
    "PAYER",
    "PAYOR",
    "MEMBER",
    "SUBSCRIBER",
    "GROUP",
    "BIN",
    "PCN",
    "RX",
    "ID",
)
PAYER_HINTS = (
    "BLUE CROSS",
    "BLUE SHIELD",
    "ANTHEM",
    "AETNA",
    "CIGNA",
    "UNITED",
    "UHC",
    "HUMANA",
    "KAISER",
    "MEDICARE",
    "MEDICAID",
    "OPTUM",
    "TRICARE",
    "CVS",
)

FIELD_NAME_MAP = {
    "first_name": "firstName",
    "middle_name": "middleName",
    "last_name": "lastName",
    "date_of_birth": "dateOfBirth",
    "address": "address",
    "city": "city",
    "state": "state",
    "postal_code": "postalCode",
    "payer_name": "payerName",
    "payer_id": "payerId",
    "member_id": "memberId",
    "group_number": "groupNumber",
    "rx_bin": "rxBin",
    "rx_pcn": "rxPcn",
    "rx_group": "rxGroup",
}


@dataclass
class OCRDocumentResult:
  document_type: str
  text: str
  lines: list[str]
  confidence: float
  variant: str
  error: str = ""


def _load_ocr_dependencies():
  try:
      import pytesseract  # type: ignore
      from PIL import Image, ImageFilter, ImageOps  # type: ignore
  except ImportError as exc:  # pragma: no cover - exercised when packages are missing
      raise HTTPException(
          status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
          detail=(
              "OCR dependencies are not installed. Install backend requirements and the "
              "Tesseract system package before using document extraction."
          ),
      ) from exc

  return pytesseract, Image, ImageFilter, ImageOps


def _clean_ocr_line(value: str) -> str:
  cleaned = value.replace("|", "I")
  cleaned = re.sub(r"\s+", " ", cleaned).strip(" :;#|")
  return cleaned


def _clean_ocr_lines(text: str) -> list[str]:
  lines: list[str] = []

  for raw_line in text.splitlines():
      cleaned = _clean_ocr_line(raw_line)

      if cleaned:
          lines.append(cleaned)

  return lines


def _average_confidence(values: list[Any]) -> float:
  confidences: list[float] = []

  for value in values:
      try:
          confidence = float(value)
      except (TypeError, ValueError):
          continue

      if confidence >= 0:
          confidences.append(confidence)

  if not confidences:
      return 0.0

  return round(mean(confidences), 1)


def _score_ocr_candidate(text: str, confidence: float) -> tuple[int, float]:
  alphanumeric_count = len(re.sub(r"[^A-Za-z0-9]", "", text))
  return (alphanumeric_count, confidence)


def _build_image_variants(file_path: str, image_module: Any, image_filter: Any, image_ops: Any):
  with image_module.open(file_path) as source_image:
      image = image_ops.exif_transpose(source_image)
      grayscale = image_ops.grayscale(image)
      enhanced = image_ops.autocontrast(grayscale)
      sharpened = enhanced.filter(image_filter.SHARPEN)
      thresholded = sharpened.point(
          lambda value: 0 if value < 165 else 255,
          mode="1",
      )

      return [
          ("grayscale", enhanced.copy()),
          ("thresholded", thresholded.copy()),
      ]


def _run_tesseract_for_document(
    document: StoredDocument,
    pytesseract_module: Any,
    image_module: Any,
    image_filter: Any,
    image_ops: Any,
) -> OCRDocumentResult:
  try:
      variants = _build_image_variants(
          document.file_path,
          image_module,
          image_filter,
          image_ops,
      )
  except OSError as exc:
      return OCRDocumentResult(
          document_type=document.document_type,
          text="",
          lines=[],
          confidence=0.0,
          variant="unavailable",
          error=f"Unable to open image for OCR: {exc}",
      )

  best_result = OCRDocumentResult(
      document_type=document.document_type,
      text="",
      lines=[],
      confidence=0.0,
      variant="unavailable",
  )

  for variant_name, image in variants:
      try:
          raw_text = pytesseract_module.image_to_string(image, config="--psm 6")
          ocr_data = pytesseract_module.image_to_data(
              image,
              config="--psm 6",
              output_type=pytesseract_module.Output.DICT,
          )
      except pytesseract_module.TesseractNotFoundError as exc:  # pragma: no cover - depends on host
          raise HTTPException(
              status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
              detail=(
                  "Tesseract is not installed or not on PATH. Install the Tesseract system "
                  "package and retry document extraction."
              ),
          ) from exc
      except pytesseract_module.TesseractError as exc:
          return OCRDocumentResult(
              document_type=document.document_type,
              text="",
              lines=[],
              confidence=0.0,
              variant=variant_name,
              error=f"Tesseract OCR failed: {exc}",
          )

      candidate = OCRDocumentResult(
          document_type=document.document_type,
          text=raw_text,
          lines=_clean_ocr_lines(raw_text),
          confidence=_average_confidence(ocr_data.get("conf", [])),
          variant=variant_name,
      )

      if _score_ocr_candidate(candidate.text, candidate.confidence) > _score_ocr_candidate(
          best_result.text,
          best_result.confidence,
      ):
          best_result = candidate

  return best_result


def run_ocr_for_documents(documents: Sequence[StoredDocument]) -> list[OCRDocumentResult]:
  pytesseract_module, image_module, image_filter, image_ops = _load_ocr_dependencies()

  return [
      _run_tesseract_for_document(
          document,
          pytesseract_module,
          image_module,
          image_filter,
          image_ops,
      )
      for document in documents
  ]


def _extract_inline_label_value(line: str, label: str) -> Optional[str]:
  pattern = re.compile(rf"\b{re.escape(label)}\b[\s:#-]*(.+)$", re.IGNORECASE)
  match = pattern.search(line)

  if not match:
      return None

  value = _clean_ocr_line(match.group(1))

  if not value or value.upper() == label.upper():
      return None

  return value


def _looks_like_label(line: str) -> bool:
  upper_line = line.upper()
  return len(upper_line.split()) <= 5 and any(hint in upper_line for hint in LABEL_HINTS)


def _find_labeled_value(lines: list[str], labels: list[str], lookahead: int = 2) -> str:
  ordered_labels = sorted(labels, key=len, reverse=True)

  for index, line in enumerate(lines):
      upper_line = line.upper()

      for label in ordered_labels:
          if label.upper() not in upper_line:
              continue

          inline_value = _extract_inline_label_value(line, label)

          if inline_value:
              return inline_value

          for offset in range(1, lookahead + 1):
              next_index = index + offset

              if next_index >= len(lines):
                  break

              candidate = _clean_ocr_line(lines[next_index])

              if candidate and not _looks_like_label(candidate):
                  return candidate

  return ""


def _extract_date_from_text(value: str) -> str:
  for regex in DATE_REGEXES:
      match = regex.search(value)

      if not match:
          continue

      candidate = match.group(0).replace(",", "").replace("SEPT", "SEP")

      for pattern in DATE_PATTERNS:
          try:
              return datetime.strptime(candidate, pattern).strftime("%Y-%m-%d")
          except ValueError:
              continue

  return ""


def _find_date_value(lines: list[str], labels: list[str]) -> str:
  labeled_value = _find_labeled_value(lines, labels)

  if labeled_value:
      parsed = _extract_date_from_text(labeled_value)

      if parsed:
          return parsed

  for line in lines:
      upper_line = line.upper()

      if any(label.upper() in upper_line for label in labels):
          parsed = _extract_date_from_text(line)

          if parsed:
              return parsed

  return ""


def _split_full_name(value: str) -> tuple[str, str, str]:
  cleaned = re.sub(r"[^A-Za-z,' -]", " ", value)
  cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")

  if not cleaned:
      return ("", "", "")

  if "," in cleaned:
      last_name, remainder = [part.strip() for part in cleaned.split(",", 1)]
      tokens = [token for token in remainder.split(" ") if token]

      if not tokens:
          return ("", "", last_name)

      return (
          tokens[0],
          " ".join(tokens[1:]),
          last_name,
      )

  tokens = [token for token in cleaned.split(" ") if token]

  if len(tokens) == 1:
      return ("", "", tokens[0])

  if len(tokens) == 2:
      return (tokens[0], "", tokens[1])

  return (
      tokens[0],
      " ".join(tokens[1:-1]),
      tokens[-1],
  )


def _find_city_state_zip(lines: list[str]) -> tuple[str, str, str]:
  for line in lines:
      match = CITY_STATE_ZIP_REGEX.search(line)

      if not match:
          continue

      return (
          _clean_ocr_line(match.group(1)),
          match.group(2).upper(),
          match.group(3),
      )

  return ("", "", "")


def _find_address_line(lines: list[str], city: str, state: str, postal_code: str) -> str:
  address = _find_labeled_value(lines, ["ADDRESS", "ADDR", "STREET ADDRESS"])

  if address:
      return address

  for index, line in enumerate(lines):
      match = CITY_STATE_ZIP_REGEX.search(line)

      if not match:
          continue

      if index > 0:
          candidate = _clean_ocr_line(lines[index - 1])

          if candidate and not _looks_like_label(candidate):
              return candidate

  for line in lines:
      if city and city.lower() in line.lower() and state and state.upper() in line.upper():
          continue

      if postal_code and postal_code in line:
          continue

      if STREET_ADDRESS_REGEX.search(line):
          return _clean_ocr_line(line)

  return ""


def _normalize_identifier(value: str) -> str:
  matches = IDENTIFIER_REGEX.findall(value.upper())

  if not matches:
      return ""

  return "".join(matches)


def _extract_driver_license_fields(result: OCRDocumentResult) -> dict[str, str]:
  lines = result.lines
  first_name = _find_labeled_value(lines, ["FIRST NAME", "FIRST", "GIVEN NAME"])
  middle_name = _find_labeled_value(lines, ["MIDDLE NAME", "MIDDLE", "MIDDLE INITIAL"])
  last_name = _find_labeled_value(lines, ["LAST NAME", "LAST", "SURNAME", "FAMILY NAME"])
  full_name = _find_labeled_value(lines, ["CUSTOMER NAME", "NAME"])

  if full_name and (not first_name or not last_name):
      parsed_first, parsed_middle, parsed_last = _split_full_name(full_name)
      first_name = first_name or parsed_first
      middle_name = middle_name or parsed_middle
      last_name = last_name or parsed_last

  date_of_birth = _find_date_value(lines, ["DOB", "DATE OF BIRTH", "BIRTH DATE"])
  city, state, postal_code = _find_city_state_zip(lines)
  address = _find_address_line(lines, city, state, postal_code)

  return {
      "first_name": first_name,
      "middle_name": middle_name,
      "last_name": last_name,
      "date_of_birth": date_of_birth,
      "address": address,
      "city": city,
      "state": state,
      "postal_code": postal_code,
  }


def _extract_insurance_id_fields(result: OCRDocumentResult) -> dict[str, str]:
  lines = result.lines

  payer_name = _find_labeled_value(
      lines,
      ["PAYER NAME", "PAYOR NAME", "PLAN NAME", "INSURANCE"],
  )

  if not payer_name:
      for line in lines[:8]:
          upper_line = line.upper()

          if any(hint in upper_line for hint in PAYER_HINTS) and not any(
              label in upper_line for label in ("MEMBER", "GROUP", "RX", "BIN", "PCN", "ID")
          ):
              payer_name = _clean_ocr_line(line)
              break

  if not payer_name:
      for line in lines[:8]:
          if any(char.isdigit() for char in line):
              continue

          if _looks_like_label(line):
              continue

          if len(line) >= 6:
              payer_name = _clean_ocr_line(line)
              break

  payer_id = _normalize_identifier(
      _find_labeled_value(lines, ["PAYER ID", "PAYOR ID", "PLAN ID"])
  )
  member_id = _normalize_identifier(
      _find_labeled_value(
          lines,
          ["MEMBER ID", "SUBSCRIBER ID", "MEMBER NUMBER", "ID #", "ID NUMBER"],
      )
  )
  group_number = _normalize_identifier(
      _find_labeled_value(lines, ["GROUP NUMBER", "GROUP #", "GROUP", "GRP"])
  )

  return {
      "payer_name": payer_name,
      "payer_id": payer_id,
      "member_id": member_id,
      "group_number": group_number,
      "rx_bin": _normalize_identifier(
          _find_labeled_value(lines, ["RX BIN", "RXBIN", "BIN", "BIN #"])
      ),
      "rx_pcn": _normalize_identifier(
          _find_labeled_value(lines, ["RX PCN", "RXPCN", "PCN", "PCN #"])
      ),
      "rx_group": _normalize_identifier(
          _find_labeled_value(lines, ["RX GROUP", "RX GRP", "RXGRP", "GROUP", "GRP"])
      ),
  }


def _find_result(
    results: Sequence[OCRDocumentResult],
    document_type: str,
) -> Optional[OCRDocumentResult]:
  for result in results:
      if result.document_type == document_type:
          return result

  return None


def _calculate_confidence(
    ocr_results: Sequence[OCRDocumentResult],
    missing_fields: list[str],
) -> float:
  ocr_confidences = [result.confidence for result in ocr_results if result.confidence > 0]
  mean_ocr_confidence = (mean(ocr_confidences) / 100) if ocr_confidences else 0.0
  total_fields = len(FIELD_NAME_MAP) - 1
  completeness = max(0.0, (total_fields - len(missing_fields)) / total_fields)

  return round(min(0.99, (mean_ocr_confidence * 0.7) + (completeness * 0.3)), 2)


def _build_document_notes(ocr_results: Sequence[OCRDocumentResult]) -> list[str]:
  notes: list[str] = []

  for result in ocr_results:
      if result.error:
          notes.append(
              f"{result.document_type}: OCR failed after upload save ({result.error})"
          )
          continue

      notes.append(
          f"{result.document_type}: {len(result.lines)} OCR lines from {result.variant} image at {result.confidence:.1f}% average confidence"
      )

  return notes


def _build_missing_fields(patient: Patient, insurance: Insurance) -> list[str]:
  values = {
      "first_name": patient.first_name,
      "last_name": patient.last_name,
      "date_of_birth": patient.date_of_birth,
      "address": patient.address,
      "city": patient.city,
      "state": patient.state,
      "postal_code": patient.postal_code,
      "payer_name": insurance.payer_name,
      "payer_id": insurance.payer_id,
      "member_id": insurance.member_id,
      "group_number": insurance.group_number,
      "rx_bin": insurance.rx_bin,
      "rx_pcn": insurance.rx_pcn,
      "rx_group": insurance.rx_group,
  }

  return [
      FIELD_NAME_MAP[field_name]
      for field_name, field_value in values.items()
      if not field_value
  ]


def _build_warnings(
    ocr_results: Sequence[OCRDocumentResult],
    missing_fields: list[str],
) -> list[Warning]:
  warnings: list[Warning] = []
  failed_documents = [
      result.document_type
      for result in ocr_results
      if result.error
  ]
  empty_documents = [
      result.document_type
      for result in ocr_results
      if not result.lines and not result.error
  ]
  low_confidence_documents = [
      result.document_type
      for result in ocr_results
      if result.lines and result.confidence < 55
  ]

  if failed_documents:
      warnings.append(
          Warning(
              code="OCR-DOCUMENT-FAILED",
              message=(
                  "OCR failed for: "
                  + ", ".join(failed_documents)
                  + ". Review the saved uploads and retry extraction."
              ),
              severity="critical",
          )
      )

  if empty_documents:
      warnings.append(
          Warning(
              code="OCR-NO-TEXT",
              message=(
                  "No readable text was detected for: "
                  + ", ".join(empty_documents)
                  + ". Check image clarity and orientation."
              ),
              severity="warning",
          )
      )

  if low_confidence_documents:
      warnings.append(
          Warning(
              code="OCR-LOW-CONFIDENCE",
              message=(
                  "Low OCR confidence for: "
                  + ", ".join(low_confidence_documents)
                  + ". Validate extracted values before verification."
              ),
              severity="warning",
          )
      )

  if missing_fields:
      severity = "critical" if any(
          field in missing_fields
          for field in ("firstName", "lastName", "dateOfBirth", "payerName", "memberId")
      ) else "warning"
      warnings.append(
          Warning(
              code="EXTRACTION-INCOMPLETE",
              message=(
                  "OCR could not confidently populate: "
                  + ", ".join(missing_fields)
                  + ". Manual review is required before verification."
              ),
              severity=severity,
          )
      )

  if not warnings:
      warnings.append(
          Warning(
              code="OCR-REVIEW",
              message="Review extracted fields against the uploaded images before verification.",
              severity="info",
          )
      )

  return warnings


def extract_from_documents(documents: Sequence[StoredDocument]) -> ExtractionResponse:
  ocr_results = run_ocr_for_documents(documents)
  driver_license_result = _find_result(ocr_results, "driver_license")
  insurance_id_result = _find_result(ocr_results, "insurance_id")

  patient_fields = _extract_driver_license_fields(
      driver_license_result
      or OCRDocumentResult(
          document_type="driver_license",
          text="",
          lines=[],
          confidence=0.0,
          variant="unavailable",
      )
  )
  insurance_id_fields = _extract_insurance_id_fields(
      insurance_id_result
      or OCRDocumentResult(
          document_type="insurance_id",
          text="",
          lines=[],
          confidence=0.0,
          variant="unavailable",
      )
  )

  patient = normalize_patient(Patient(**patient_fields))
  insurance = normalize_insurance(
      Insurance(
          payer_name=insurance_id_fields["payer_name"],
          payer_id=insurance_id_fields["payer_id"],
          member_id=insurance_id_fields["member_id"],
          group_number=insurance_id_fields["group_number"],
          rx_bin=insurance_id_fields["rx_bin"],
          rx_pcn=insurance_id_fields["rx_pcn"],
          rx_group=insurance_id_fields["rx_group"],
      )
  )

  missing_fields = _build_missing_fields(patient, insurance)
  warnings = _build_warnings(ocr_results, missing_fields)

  return ExtractionResponse(
      patient=patient,
      insurance=insurance,
      confidence=_calculate_confidence(ocr_results, missing_fields),
      document_notes=_build_document_notes(ocr_results),
      missing_fields=missing_fields,
      warnings=warnings,
  )

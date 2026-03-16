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
PHONE_REGEX = re.compile(
    r"(?:\+?1[-.\s]*)?\(?(\d{3})\)?[-.\s]*(\d{3})[-.\s]*(\d{4})"
)
WEBSITE_REGEX = re.compile(
    r"\b(?:https?://)?(?:www\.)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=-]*)?\b",
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
STATE_NAME_TO_CODE = {
    "ALABAMA": "AL",
    "ALASKA": "AK",
    "ALBERTA": "AB",
    "ARIZONA": "AZ",
    "ARKANSAS": "AR",
    "BRITISH COLUMBIA": "BC",
    "CALIFORNIA": "CA",
    "COLORADO": "CO",
    "CONNECTICUT": "CT",
    "DELAWARE": "DE",
    "DISTRICT OF COLUMBIA": "DC",
    "FLORIDA": "FL",
    "GEORGIA": "GA",
    "HAWAII": "HI",
    "IDAHO": "ID",
    "ILLINOIS": "IL",
    "INDIANA": "IN",
    "IOWA": "IA",
    "KANSAS": "KS",
    "KENTUCKY": "KY",
    "LOUISIANA": "LA",
    "MAINE": "ME",
    "MANITOBA": "MB",
    "MARYLAND": "MD",
    "MASSACHUSETTS": "MA",
    "MICHIGAN": "MI",
    "MINNESOTA": "MN",
    "MISSISSIPPI": "MS",
    "MISSOURI": "MO",
    "MONTANA": "MT",
    "NEBRASKA": "NE",
    "NEVADA": "NV",
    "NEW BRUNSWICK": "NB",
    "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM",
    "NEW YORK": "NY",
    "NEWFOUNDLAND AND LABRADOR": "NL",
    "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND",
    "NOVA SCOTIA": "NS",
    "OHIO": "OH",
    "OKLAHOMA": "OK",
    "ONTARIO": "ON",
    "OREGON": "OR",
    "PENNSYLVANIA": "PA",
    "PRINCE EDWARD ISLAND": "PE",
    "QUEBEC": "QC",
    "RHODE ISLAND": "RI",
    "SASKATCHEWAN": "SK",
    "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN",
    "TEXAS": "TX",
    "UTAH": "UT",
    "VERMONT": "VT",
    "VIRGINIA": "VA",
    "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI",
    "WYOMING": "WY",
    "YUKON": "YT",
}
US_STATE_NAME_PHRASES = set(STATE_NAME_TO_CODE)
VALID_STATE_CODES = set(STATE_NAME_TO_CODE.values())
STATE_CODE_CHAR_ALTERNATIVES = {
    "0": ("O",),
    "1": ("I", "L"),
    "5": ("S",),
    "8": ("B",),
    "B": ("8",),
    "D": ("O",),
    "G": ("C", "O"),
    "H": ("N",),
    "I": ("L",),
    "K": ("N",),
    "L": ("I",),
    "M": ("N",),
    "N": ("M", "K"),
    "O": ("Q", "D", "0"),
    "Q": ("O",),
    "S": ("5",),
    "V": ("Y",),
    "Y": ("V", "N"),
    "Z": ("2",),
}
DRIVER_LICENSE_REGION_BOUNDS = {
    "identity": (0.08, 0.12, 0.94, 0.48),
    "address": (0.08, 0.48, 0.94, 0.88),
}
NON_PERSON_NAME_TOKENS = {
    "MOTORIST",
    "DRIVER",
    "LICENSE",
    "IDENTIFICATION",
    "CARD",
    "CLASS",
    "RESTR",
    "ENDORSE",
    "SEX",
    "EYES",
    "HAIR",
    "VETERAN",
    "ORGAN",
}
ADDRESS_SUFFIX_TOKENS = {
    "ST",
    "STREET",
    "RD",
    "ROAD",
    "AVE",
    "AVENUE",
    "BLVD",
    "DR",
    "DRIVE",
    "LN",
    "LANE",
    "CT",
    "COURT",
    "PL",
    "PLACE",
    "PKWY",
    "PARKWAY",
    "WAY",
    "CIR",
    "CIRCLE",
    "REET",
}
GENERIC_PAYER_NAME_TOKENS = {
    "CO",
    "COMPANY",
    "CORP",
    "CORPORATION",
    "HEALTH",
    "INC",
    "INCORPORATED",
    "INSURANCE",
    "LIMITED",
    "LLC",
    "LTD",
    "PLAN",
}

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
    "member_phone": "memberPhone",
    "provider_phone": "providerPhone",
    "provider_website": "providerWebsite",
    "pharmacy_phone": "pharmacyPhone",
    "pharmacy_claims_address": "pharmacyClaimsAddress",
}


@dataclass
class OCRDocumentResult:
  document_type: str
  text: str
  lines: list[str]
  confidence: float
  variant: str
  error: str = ""


OCR_CONFIGS_BY_DOCUMENT = {
    "driver_license": [
        ("psm11", "--oem 3 --psm 11"),
        ("psm6", "--oem 3 --psm 6"),
    ],
    "insurance_front": [
        ("psm6", "--oem 3 --psm 6"),
        ("psm11", "--oem 3 --psm 11"),
    ],
    "insurance_back": [
        ("psm6", "--oem 3 --psm 6"),
        ("psm11", "--oem 3 --psm 11"),
    ],
}


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
  cleaned = re.sub(r"\s+", " ", cleaned).strip(" :;#|.()[]{}")
  return cleaned


def _clean_ocr_lines(text: str) -> list[str]:
  lines: list[str] = []

  for raw_line in text.splitlines():
      cleaned = _clean_ocr_line(raw_line)

      if cleaned:
          lines.append(cleaned)

  return lines


def _normalize_alpha_phrase(value: str) -> str:
  cleaned = re.sub(r"[^A-Za-z ]", " ", value)
  return re.sub(r"\s+", " ", cleaned).strip().upper()


def _alpha_tokens(value: str) -> list[str]:
  normalized = _normalize_alpha_phrase(value)
  return [token for token in normalized.split(" ") if token]


def _dedupe_lines(lines: Sequence[str]) -> list[str]:
  deduped: list[str] = []
  seen: set[str] = set()

  for line in lines:
      cleaned = _clean_ocr_line(line)

      if cleaned and cleaned not in seen:
          seen.add(cleaned)
          deduped.append(cleaned)

  return deduped


def _normalize_phone(value: str) -> str:
  match = PHONE_REGEX.search(value)

  if not match:
      return ""

  return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def _normalize_website(value: str) -> str:
  match = WEBSITE_REGEX.search(value)

  if not match:
      return ""

  cleaned = match.group(0).lower()
  return cleaned.removeprefix("http://").removeprefix("https://").removeprefix("www.")


def _average_confidence(ocr_data: dict[str, Any]) -> float:
  confidences: list[float] = []
  words = ocr_data.get("text", [])
  values = ocr_data.get("conf", [])

  for value, word in zip(values, words):
      try:
          confidence = float(value)
      except (TypeError, ValueError):
          continue

      if confidence >= 0:
          cleaned_word = re.sub(r"[^A-Za-z0-9]", "", str(word or ""))

          if len(cleaned_word) >= 2:
              confidences.append(confidence)

  if not confidences:
      return 0.0

  return round(mean(confidences), 1)


def _resize_image(image: Any, image_module: Any, target_width: int):
  if image.width >= target_width:
      return image.copy()

  resampling = getattr(getattr(image_module, "Resampling", image_module), "LANCZOS", 1)
  scale_factor = target_width / max(1, image.width)
  target_height = max(1, int(round(image.height * scale_factor)))
  return image.resize((target_width, target_height), resample=resampling)


def _crop_image(image: Any, bounds: tuple[float, float, float, float]):
  left_ratio, top_ratio, right_ratio, bottom_ratio = bounds
  width, height = image.size
  left = int(round(width * left_ratio))
  top = int(round(height * top_ratio))
  right = int(round(width * right_ratio))
  bottom = int(round(height * bottom_ratio))
  return image.crop((left, top, right, bottom))


def _build_image_variants(file_path: str, image_module: Any, image_filter: Any, image_ops: Any):
  with image_module.open(file_path) as source_image:
      image = image_ops.exif_transpose(source_image)
      grayscale = image_ops.grayscale(image)
      enhanced = image_ops.autocontrast(grayscale)
      denoised = enhanced.filter(image_filter.MedianFilter(size=3))
      sharpened = denoised.filter(image_filter.SHARPEN)
      thresholded = sharpened.point(
          lambda value: 0 if value < 165 else 255,
          mode="1",
      )
      upscaled = _resize_image(sharpened, image_module, target_width=1800)
      upscaled_thresholded = upscaled.point(
          lambda value: 0 if value < 170 else 255,
          mode="1",
      )

      return [
          ("grayscale", enhanced.copy()),
          ("thresholded", thresholded.copy()),
          ("upscaled", upscaled.copy()),
          ("upscaled_thresholded", upscaled_thresholded.copy()),
      ]


def _build_driver_license_region_variants(
    file_path: str,
    image_module: Any,
    image_filter: Any,
    image_ops: Any,
) -> dict[str, list[tuple[str, Any]]]:
  with image_module.open(file_path) as source_image:
      image = image_ops.exif_transpose(source_image)
      grayscale = image_ops.grayscale(image)
      enhanced = image_ops.autocontrast(grayscale)
      denoised = enhanced.filter(image_filter.MedianFilter(size=3))
      sharpened = denoised.filter(image_filter.SHARPEN)
      upscaled = _resize_image(sharpened, image_module, target_width=2000)
      upscaled_thresholded = upscaled.point(
          lambda value: 0 if value < 168 else 255,
          mode="1",
      )

      return {
          region_name: [
              (f"{region_name}_upscaled", _crop_image(upscaled, bounds)),
              (
                  f"{region_name}_upscaled_thresholded",
                  _crop_image(upscaled_thresholded, bounds),
              ),
          ]
          for region_name, bounds in DRIVER_LICENSE_REGION_BOUNDS.items()
      }


def _candidate_signal_score(result: OCRDocumentResult) -> int:
  if result.document_type == "driver_license":
      fields = _extract_driver_license_fields(result)
      score = 0
      plausible_name = _is_plausible_person_name(
          fields["first_name"],
          fields["middle_name"],
          fields["last_name"],
      )
      plausible_address = _is_plausible_address_line(fields["address"])

      if fields["first_name"] and plausible_name:
          score += 2
      if fields["last_name"] and plausible_name:
          score += 2
      if fields["middle_name"] and plausible_name:
          score += 1
      if fields["date_of_birth"]:
          score += 3
      if fields["address"] and plausible_address:
          score += 2
      if fields["city"] and fields["state"] and fields["postal_code"]:
          score += 3

      return score

  if result.document_type == "insurance_front":
      fields = _extract_insurance_card_fields(result)
      score = 0

      if fields["payer_name"]:
          score += 2
      if fields["payer_id"]:
          score += 2
      if fields["member_id"]:
          score += 3
      if fields["group_number"]:
          score += 2
      if fields["rx_bin"]:
          score += 1
      if fields["rx_pcn"]:
          score += 1
      if fields["rx_group"]:
          score += 1

      return score

  if result.document_type == "insurance_back":
      fields = _extract_insurance_back_fields(result)
      score = 0

      if fields["member_phone"]:
          score += 2
      if fields["provider_phone"]:
          score += 2
      if fields["provider_website"]:
          score += 2
      if fields["pharmacy_phone"]:
          score += 2
      if fields["pharmacy_claims_address"]:
          score += 3

      return score

  return 0


def _score_ocr_candidate(result: OCRDocumentResult) -> tuple[int, float, int]:
  signal_score = _candidate_signal_score(result)
  alphanumeric_count = len(re.sub(r"[^A-Za-z0-9]", "", result.text))
  return (signal_score, result.confidence, alphanumeric_count)


def _run_ocr_for_variants(
    document_type: str,
    variants: Sequence[tuple[str, Any]],
    pytesseract_module: Any,
    image_module: Any,
    image_filter: Any,
    image_ops: Any,
) -> OCRDocumentResult:
  best_result = OCRDocumentResult(
      document_type=document_type,
      text="",
      lines=[],
      confidence=0.0,
      variant="unavailable",
  )

  for variant_name, image in variants:
      for config_label, config in OCR_CONFIGS_BY_DOCUMENT.get(
          document_type,
          [("default", "--oem 3 --psm 6")],
      ):
          try:
              raw_text = pytesseract_module.image_to_string(image, config=config)
              ocr_data = pytesseract_module.image_to_data(
                  image,
                  config=config,
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
                  document_type=document_type,
                  text="",
                  lines=[],
                  confidence=0.0,
                  variant=f"{variant_name}:{config_label}",
                  error=f"Tesseract OCR failed: {exc}",
              )

          candidate = OCRDocumentResult(
              document_type=document_type,
              text=raw_text,
              lines=_clean_ocr_lines(raw_text),
              confidence=_average_confidence(ocr_data),
              variant=f"{variant_name}:{config_label}",
          )

          if _score_ocr_candidate(candidate) > _score_ocr_candidate(best_result):
              best_result = candidate

  return best_result


def _merge_ocr_results(
    document_type: str,
    results: Sequence[OCRDocumentResult],
) -> OCRDocumentResult:
  usable_results = [result for result in results if result.lines]
  merged_lines = _dedupe_lines(
      line
      for result in usable_results
      for line in result.lines
  )
  merged_confidences = [
      result.confidence
      for result in usable_results
      if result.confidence > 0
  ]
  variant_description = ", ".join(
      f"{result.variant}"
      for result in usable_results
  ) or "unavailable"

  return OCRDocumentResult(
      document_type=document_type,
      text="\n".join(merged_lines),
      lines=merged_lines,
      confidence=round(mean(merged_confidences), 1) if merged_confidences else 0.0,
      variant=f"composite[{variant_description}]",
      error=next((result.error for result in results if result.error), ""),
  )


def _run_driver_license_ocr(
    document: StoredDocument,
    pytesseract_module: Any,
    image_module: Any,
    image_filter: Any,
    image_ops: Any,
) -> OCRDocumentResult:
  full_variants = _build_image_variants(
      document.file_path,
      image_module,
      image_filter,
      image_ops,
  )
  best_full = _run_ocr_for_variants(
      document.document_type,
      full_variants,
      pytesseract_module,
      image_module,
      image_filter,
      image_ops,
  )

  try:
      region_variants = _build_driver_license_region_variants(
          document.file_path,
          image_module,
          image_filter,
          image_ops,
      )
  except OSError:
      return best_full

  best_identity = _run_ocr_for_variants(
      document.document_type,
      region_variants["identity"],
      pytesseract_module,
      image_module,
      image_filter,
      image_ops,
  )
  best_address = _run_ocr_for_variants(
      document.document_type,
      region_variants["address"],
      pytesseract_module,
      image_module,
      image_filter,
      image_ops,
  )
  merged_result = _merge_ocr_results(
      document.document_type,
      [best_full, best_identity, best_address],
  )

  if _score_ocr_candidate(merged_result) >= _score_ocr_candidate(best_full):
      return merged_result

  return best_full


def _run_tesseract_for_document(
    document: StoredDocument,
    pytesseract_module: Any,
    image_module: Any,
    image_filter: Any,
    image_ops: Any,
) -> OCRDocumentResult:
  try:
      _build_image_variants(
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

  if document.document_type == "driver_license":
      return _run_driver_license_ocr(
          document,
          pytesseract_module,
          image_module,
          image_filter,
          image_ops,
      )

  return _run_ocr_for_variants(
      document.document_type,
      _build_image_variants(
          document.file_path,
          image_module,
          image_filter,
          image_ops,
      ),
      pytesseract_module,
      image_module,
      image_filter,
      image_ops,
  )


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


def _extract_all_dates_from_text(value: str) -> list[datetime]:
  parsed_dates: list[datetime] = []

  for regex in DATE_REGEXES:
      for match in regex.finditer(value):
          candidate = match.group(0).replace(",", "").replace("SEPT", "SEP")

          for pattern in DATE_PATTERNS:
              try:
                  parsed_dates.append(datetime.strptime(candidate, pattern))
                  break
              except ValueError:
                  continue

  return parsed_dates


def _find_birth_date_fallback(lines: list[str]) -> str:
  today = datetime.utcnow().date()
  plausible_birth_dates: list[datetime] = []

  for line in lines:
      for parsed_date in _extract_all_dates_from_text(line):
          age = (today - parsed_date.date()).days / 365.25

          if 14 <= age <= 120:
              plausible_birth_dates.append(parsed_date)

  if not plausible_birth_dates:
      return ""

  return min(plausible_birth_dates).strftime("%Y-%m-%d")


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


def _looks_like_name_line(line: str) -> bool:
  cleaned = re.sub(r"[^A-Za-z,' -]", " ", line)
  cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
  tokens = [token for token in cleaned.split(" ") if token]
  upper_line = line.upper()
  normalized_phrase = _normalize_alpha_phrase(line)

  if not cleaned or not tokens or len(tokens) > 4:
      return False

  if any(char.isdigit() for char in line):
      return False

  if _looks_like_label(line):
      return False

  if CITY_STATE_ZIP_REGEX.search(line) or STREET_ADDRESS_REGEX.search(line):
      return False

  if normalized_phrase in US_STATE_NAME_PHRASES:
      return False

  if any(
      hint in upper_line
      for hint in (
          "DRIVER",
          "LICENSE",
          "CLASS",
          "RESTR",
          "ENDORSE",
          "DONOR",
          "SEX",
          "HGT",
          "WGT",
          "EYES",
          "HAIR",
          "EXP",
          "ISS",
          "VETERAN",
          "ORGAN",
          "USA",
      )
  ):
      return False

  if any(token in NON_PERSON_NAME_TOKENS for token in _alpha_tokens(line)):
      return False

  return all(re.search(r"[A-Za-z]{1,}", token) for token in tokens)


def _split_unlabeled_name(value: str) -> tuple[str, str, str]:
  cleaned = re.sub(r"[^A-Za-z,' -]", " ", value)
  cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")

  if not cleaned:
      return ("", "", "")

  if "," in cleaned:
      return _split_full_name(cleaned)

  tokens = [token for token in cleaned.split(" ") if token]

  if len(tokens) == 3 and len(tokens[-1]) <= 2:
      return (
          tokens[1],
          "",
          tokens[0],
      )

  return _split_full_name(cleaned)


def _normalize_unlabeled_middle_name(value: str) -> str:
  cleaned = _clean_ocr_line(value)
  alpha_only = re.sub(r"[^A-Za-z]", "", cleaned)

  if len(alpha_only) <= 1:
      return ""

  return cleaned


def _find_unlabeled_name(lines: list[str]) -> tuple[str, str, str]:
  candidate_lines = [
      (index, _clean_ocr_line(line))
      for index, line in enumerate(lines[:8])
      if _looks_like_name_line(line)
  ]

  for current_index, (line_index, candidate) in enumerate(candidate_lines):
      current_tokens = [token for token in candidate.split(" ") if token]

      for next_index, next_candidate in candidate_lines[current_index + 1:]:
          if next_index - line_index > 2:
              break

          next_tokens = [token for token in next_candidate.split(" ") if token]

          if len(current_tokens) == 1 and 1 <= len(next_tokens) <= 2:
              return (
                  next_tokens[0],
                  _normalize_unlabeled_middle_name(" ".join(next_tokens[1:])),
                  current_tokens[0],
              )

          if 1 <= len(current_tokens) <= 2 and len(next_tokens) == 1:
              return (
                  current_tokens[0],
                  _normalize_unlabeled_middle_name(" ".join(current_tokens[1:])),
                  next_tokens[0],
              )

      if 2 <= len(current_tokens) <= 3:
          return _split_unlabeled_name(candidate)

  return ("", "", "")


def _find_city_state_zip(lines: list[str]) -> tuple[str, str, str]:
  for line in lines:
      match = CITY_STATE_ZIP_REGEX.search(line)

      if not match:
          continue

      postal_code = match.group(3)

      return (
          _clean_ocr_line(match.group(1)),
          _normalize_state_code(match.group(2), lines, postal_code),
          postal_code,
      )

  return ("", "", "")


def _extract_state_code_from_lines(lines: Sequence[str]) -> str:
  normalized_lines = [_normalize_alpha_phrase(line) for line in lines]

  for state_name in sorted(STATE_NAME_TO_CODE, key=len, reverse=True):
      if any(state_name in normalized_line for normalized_line in normalized_lines):
          return STATE_NAME_TO_CODE[state_name]

  return ""


def _state_code_candidates(raw_code: str) -> list[str]:
  cleaned = re.sub(r"[^A-Za-z0-9]", "", raw_code.upper())[:2]

  if len(cleaned) != 2:
      return []

  first_options = (cleaned[0],) + STATE_CODE_CHAR_ALTERNATIVES.get(cleaned[0], ())
  second_options = (cleaned[1],) + STATE_CODE_CHAR_ALTERNATIVES.get(cleaned[1], ())
  candidates: list[str] = []

  for first_option in first_options:
      for second_option in second_options:
          candidate = f"{first_option}{second_option}"

          if candidate not in candidates:
              candidates.append(candidate)

  return candidates


def _normalize_state_code(
    raw_state: str,
    lines: Sequence[str],
    postal_code: str = "",
) -> str:
  state_from_lines = _extract_state_code_from_lines(lines)
  cleaned = re.sub(r"[^A-Za-z0-9 ]", "", raw_state.upper()).strip()

  if not cleaned:
      return state_from_lines

  if cleaned in STATE_NAME_TO_CODE:
      return STATE_NAME_TO_CODE[cleaned]

  if len(cleaned) > 2:
      state_from_lines = state_from_lines or _extract_state_code_from_lines([cleaned])

      if state_from_lines:
          return state_from_lines

  if len(cleaned) == 2 and cleaned in VALID_STATE_CODES:
      if state_from_lines and state_from_lines != cleaned:
          return state_from_lines

      return cleaned

  for candidate in _state_code_candidates(cleaned):
      if candidate in VALID_STATE_CODES:
          if state_from_lines and state_from_lines != candidate:
              return state_from_lines

          return candidate

  if state_from_lines:
      return state_from_lines

  return cleaned[:2]


def _is_plausible_address_line(value: str) -> bool:
  cleaned = _clean_ocr_line(value)
  tokens = _alpha_tokens(cleaned)

  if not cleaned or len(cleaned) < 8:
      return False

  if cleaned.upper() in ADDRESS_SUFFIX_TOKENS:
      return False

  if not any(character.isdigit() for character in cleaned):
      return False

  if len(cleaned.split()) < 2:
      return False

  if STREET_ADDRESS_REGEX.search(cleaned):
      return True

  if re.match(r"^\d+\s+[A-Za-z0-9.#'\- ]{4,}$", cleaned):
      return True

  return bool(tokens and tokens[-1] in ADDRESS_SUFFIX_TOKENS and cleaned[0].isdigit())


def _find_address_line(lines: list[str], city: str, state: str, postal_code: str) -> str:
  address = _find_labeled_value(lines, ["ADDRESS", "ADDR", "STREET ADDRESS"])

  if address and _is_plausible_address_line(address):
      return address

  for index, line in enumerate(lines):
      match = CITY_STATE_ZIP_REGEX.search(line)

      if not match:
          continue

      for offset in range(1, 4):
          previous_index = index - offset

          if previous_index < 0:
              break

          candidate = _clean_ocr_line(lines[previous_index])

          if candidate and not _looks_like_label(candidate) and _is_plausible_address_line(
              candidate
          ):
              return candidate

  for line in lines:
      if city and city.lower() in line.lower() and state and state.upper() in line.upper():
          continue

      if postal_code and postal_code in line:
          continue

      candidate = _clean_ocr_line(line)

      if _is_plausible_address_line(candidate):
          return candidate

  return ""


def _normalize_identifier(value: str) -> str:
  matches = IDENTIFIER_REGEX.findall(value.upper())

  if not matches:
      return ""

  return "".join(matches)


def _clean_identifier_value(
    value: str,
    embedded_stop_terms: Sequence[str] = (),
) -> str:
  normalized = _normalize_identifier(value)

  if not normalized:
      return ""

  cut_index = len(normalized)
  upper_value = normalized.upper()

  for stop_term in embedded_stop_terms:
      stop_index = upper_value.find(stop_term.upper())

      if 0 < stop_index < cut_index:
          cut_index = stop_index

  cleaned = normalized[:cut_index]

  if cleaned.startswith("NUMBER") and len(cleaned) > len("NUMBER"):
      suffix = cleaned[len("NUMBER"):]

      if any(character.isdigit() for character in suffix):
          cleaned = suffix

  return cleaned


def _extract_identifier_by_patterns(
    lines: list[str],
    patterns: list[str],
    *,
    excluded_terms: Sequence[str] = (),
    embedded_stop_terms: Sequence[str] = (),
) -> str:
  compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]

  for line in lines:
      upper_line = line.upper()

      if excluded_terms and any(term.upper() in upper_line for term in excluded_terms):
          continue

      for pattern in compiled_patterns:
          match = pattern.search(line)

          if not match:
              continue

          value = _clean_identifier_value(
              match.group(1),
              embedded_stop_terms=embedded_stop_terms,
          )

          if value:
              return value

  return ""


def _extract_text_by_patterns(
    lines: list[str],
    patterns: list[str],
    *,
    excluded_terms: Sequence[str] = (),
    stop_terms: Sequence[str] = (),
) -> str:
  compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]

  for line in lines:
      upper_line = line.upper()

      if excluded_terms and any(term.upper() in upper_line for term in excluded_terms):
          continue

      for pattern in compiled_patterns:
          match = pattern.search(line)

          if not match:
              continue

          value = _clean_ocr_line(match.group(1))
          cut_index = len(value)
          upper_value = value.upper()

          for stop_term in stop_terms:
              stop_index = upper_value.find(stop_term.upper())

              if 0 < stop_index < cut_index:
                  cut_index = stop_index

          cleaned = _clean_ocr_line(value[:cut_index])

          if cleaned:
              return cleaned

  return ""


def _find_phone_value(lines: list[str], labels: list[str]) -> str:
  ordered_labels = sorted(labels, key=len, reverse=True)

  for index, line in enumerate(lines):
      upper_line = line.upper()

      for label in ordered_labels:
          if label.upper() not in upper_line:
              continue

          inline_value = _extract_inline_label_value(line, label)

          if inline_value:
              normalized = _normalize_phone(inline_value)

              if normalized:
                  return normalized

          normalized_line = _normalize_phone(line)

          if normalized_line:
              return normalized_line

          for offset in range(1, 3):
              next_index = index + offset

              if next_index >= len(lines):
                  break

              normalized_next_line = _normalize_phone(lines[next_index])

              if normalized_next_line:
                  return normalized_next_line

  return ""


def _find_website_value(lines: list[str], labels: list[str]) -> str:
  ordered_labels = sorted(labels, key=len, reverse=True)

  for index, line in enumerate(lines):
      upper_line = line.upper()

      for label in ordered_labels:
          if label.upper() not in upper_line:
              continue

          inline_value = _extract_inline_label_value(line, label)

          if inline_value:
              normalized = _normalize_website(inline_value)

              if normalized:
                  return normalized

          normalized_line = _normalize_website(line)

          if normalized_line:
              return normalized_line

          for offset in range(1, 3):
              next_index = index + offset

              if next_index >= len(lines):
                  break

              normalized_next_line = _normalize_website(lines[next_index])

              if normalized_next_line:
                  return normalized_next_line

  return ""


def _find_multiline_label_value(lines: list[str], labels: list[str], lookahead: int = 2) -> str:
  ordered_labels = sorted(labels, key=len, reverse=True)

  for index, line in enumerate(lines):
      upper_line = line.upper()

      for label in ordered_labels:
          if label.upper() not in upper_line:
              continue

          inline_value = _extract_inline_label_value(line, label)

          if inline_value:
              return inline_value

          collected_lines: list[str] = []

          for offset in range(1, lookahead + 1):
              next_index = index + offset

              if next_index >= len(lines):
                  break

              candidate = _clean_ocr_line(lines[next_index])

              if candidate and not _looks_like_label(candidate):
                  collected_lines.append(candidate)

          if collected_lines:
              return " ".join(collected_lines)

  return ""


def _sanitize_payer_name(value: str) -> str:
  cleaned = _clean_ocr_line(value)
  upper_cleaned = cleaned.upper()
  payer_hint_positions = [
      upper_cleaned.find(hint)
      for hint in PAYER_HINTS
      if upper_cleaned.find(hint) >= 0
  ]

  if payer_hint_positions:
      cleaned = cleaned[min(payer_hint_positions):]

  cleaned = re.sub(
      r"^(?:UNDERWRITTEN|ADMINISTERED|INSURED)\s+BY\s+",
      "",
      cleaned,
      flags=re.IGNORECASE,
  )
  cleaned = re.sub(r"^[A-Za-z]{1,2}[\)\].:-]+\s*", "", cleaned)
  cleaned = re.sub(r"^[^A-Za-z0-9]+", "", cleaned)
  cleaned = re.sub(r"[^A-Za-z0-9]+$", "", cleaned)
  cleaned = re.sub(r"\s+", " ", cleaned).strip()

  if not _is_plausible_payer_name(cleaned):
      return ""

  return cleaned


def _is_plausible_payer_name(value: str) -> bool:
  tokens = _alpha_tokens(value)

  if not tokens:
      return False

  if all(token in GENERIC_PAYER_NAME_TOKENS for token in tokens):
      return False

  if len(tokens) == 1 and tokens[0] in GENERIC_PAYER_NAME_TOKENS:
      return False

  return True


def _is_plausible_person_name(
    first_name: str,
    middle_name: str,
    last_name: str,
) -> bool:
  first_tokens = _alpha_tokens(first_name)
  last_tokens = _alpha_tokens(last_name)

  if not first_tokens or not last_tokens:
      return True

  full_name = _normalize_alpha_phrase(f"{first_name} {middle_name} {last_name}")
  first_last = _normalize_alpha_phrase(f"{first_name} {last_name}")
  last_first = _normalize_alpha_phrase(f"{last_name} {first_name}")
  all_tokens = first_tokens + _alpha_tokens(last_name)

  if first_last in US_STATE_NAME_PHRASES or last_first in US_STATE_NAME_PHRASES:
      return False

  if any(token in NON_PERSON_NAME_TOKENS for token in all_tokens):
      return False

  if len(first_tokens[0]) == 1 or len(last_tokens[-1]) == 1:
      return False

  return full_name not in US_STATE_NAME_PHRASES


def _apply_plausibility_checks(
    patient: Patient,
) -> tuple[Patient, list[str]]:
  flagged_fields: list[str] = []
  first_name = patient.first_name
  middle_name = patient.middle_name
  last_name = patient.last_name
  address = patient.address

  if not _is_plausible_person_name(first_name, middle_name, last_name):
      if first_name:
          flagged_fields.append("firstName")
          first_name = ""
      if middle_name:
          middle_name = ""
      if last_name:
          flagged_fields.append("lastName")
          last_name = ""

  if address and not _is_plausible_address_line(address):
      flagged_fields.append("address")
      address = ""

  return (
      Patient(
          first_name=first_name,
          middle_name=middle_name,
          last_name=last_name,
          date_of_birth=patient.date_of_birth,
          address=address,
          city=patient.city,
          state=patient.state,
          postal_code=patient.postal_code,
      ),
      flagged_fields,
  )


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

  if not first_name or not last_name:
      parsed_first, parsed_middle, parsed_last = _find_unlabeled_name(lines)
      first_name = first_name or parsed_first
      middle_name = middle_name or parsed_middle
      last_name = last_name or parsed_last

  date_of_birth = _find_date_value(lines, ["DOB", "DATE OF BIRTH", "BIRTH DATE"])

  if not date_of_birth:
      date_of_birth = _find_birth_date_fallback(lines)

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


def _extract_insurance_card_fields(result: OCRDocumentResult) -> dict[str, str]:
  lines = result.lines

  payer_name = _sanitize_payer_name(
      _find_labeled_value(
          lines,
          ["PAYER NAME", "PAYOR NAME", "PLAN NAME", "INSURANCE"],
      )
  )

  if not payer_name:
      payer_name = _sanitize_payer_name(
          _extract_text_by_patterns(
              lines,
              [
                  r"\b(?:PAYER|PAYOR|PLAN)\s+NAME\b[\s:#-]*(.+)$",
                  r"\bINSURANCE\b[\s:#-]*(.+)$",
              ],
              stop_terms=("MEMBER", "GROUP", "RX", "BIN", "PCN", "PAYER ID", "PAYOR ID", "PLAN ID"),
          )
      )

  if not payer_name:
      for line in lines[:8]:
          upper_line = line.upper()

          if any(hint in upper_line for hint in PAYER_HINTS) and not any(
              label in upper_line for label in ("MEMBER", "GROUP", "RX", "BIN", "PCN", "ID")
          ):
              payer_name = _sanitize_payer_name(line)
              break

  if not payer_name:
      for line in lines[:8]:
          if any(char.isdigit() for char in line):
              continue

          if _looks_like_label(line):
              continue

          if len(line) >= 6:
              payer_name = _sanitize_payer_name(line)
              break

  payer_id = _extract_identifier_by_patterns(
      lines,
      [
          r"\b(?:PAYER|PAYOR|PLAN)\s+ID\b[\s:#-]*([A-Za-z0-9-]+)",
      ],
  )
  member_id = _extract_identifier_by_patterns(
      lines,
      [
          r"\b(?:MEMBER|SUBSCRIBER)\s+ID\b[\s:#-]*([A-Za-z0-9-]+)",
          r"\bMEMBER\s+NUMBER\b[\s:#-]*([A-Za-z0-9-]+)",
          r"\bID\s+NUMBER\b[\s:#-]*([A-Za-z0-9-]+)",
      ],
      embedded_stop_terms=("GROUPNUMBER", "GROUP", "RXBIN", "BIN", "RXPCN", "PCN", "RXGROUP"),
  )
  group_number = _extract_identifier_by_patterns(
      lines,
      [
          r"\bGROUP\s+NUMBER\b[\s:#-]*([A-Za-z0-9-]+)",
          r"\bGROUP\s*#?[\s:#-]*([A-Za-z0-9-]+)",
          r"\bGRP\b[\s:#-]*([A-Za-z0-9-]+)",
          r"\bGROUP\b[\s:#-]*([A-Za-z0-9-]+)",
      ],
      excluded_terms=("RX GROUP", "RX GRP", "RXGRP"),
      embedded_stop_terms=("RXBIN", "BIN", "RXPCN", "PCN", "RXGROUP"),
  )

  return {
      "payer_name": payer_name,
      "payer_id": payer_id,
      "member_id": member_id,
      "group_number": group_number,
      "rx_bin": _extract_identifier_by_patterns(
          lines,
          [
              r"\bRX\s*BIN\b[\s:#-]*([A-Za-z0-9-]+)",
              r"\bBIN\s*#?\b[\s:#-]*([A-Za-z0-9-]+)",
          ],
          embedded_stop_terms=("RXPCN", "PCN", "RXGROUP", "GROUP"),
      ),
      "rx_pcn": _extract_identifier_by_patterns(
          lines,
          [
              r"\bRX\s*PCN\b[\s:#-]*([A-Za-z0-9-]+)",
              r"\bPCN\s*#?\b[\s:#-]*([A-Za-z0-9-]+)",
          ],
          embedded_stop_terms=("RXGROUP", "GROUP", "RXBIN", "BIN"),
      ),
      "rx_group": _extract_identifier_by_patterns(
          lines,
          [
              r"\bRX\s+GROUP\b[\s:#-]*([A-Za-z0-9-]+)",
              r"\bRX\s+GRP\b[\s:#-]*([A-Za-z0-9-]+)",
              r"\bRXGRP\b[\s:#-]*([A-Za-z0-9-]+)",
          ],
      ),
      "member_phone": "",
      "provider_phone": "",
      "provider_website": "",
      "pharmacy_phone": "",
      "pharmacy_claims_address": "",
  }


def _extract_insurance_back_fields(result: OCRDocumentResult) -> dict[str, str]:
  lines = result.lines

  member_phone = _find_phone_value(lines, ["PHONE", "MEMBER PHONE"])
  provider_phone = _find_phone_value(lines, ["PROVIDERS", "PROVIDER"])
  provider_website = _find_website_value(lines, ["PROVIDERS", "PROVIDER", "WEB"])
  pharmacy_phone = _find_phone_value(lines, ["PHARMACISTS", "PHARMACY"])
  pharmacy_claims_address = _find_multiline_label_value(
      lines,
      ["PHARMACY CLAIMS", "PHARMACY CLAIM"],
      lookahead=2,
  )

  return {
      "payer_name": "",
      "payer_id": "",
      "member_id": "",
      "group_number": "",
      "rx_bin": "",
      "rx_pcn": "",
      "rx_group": "",
      "member_phone": member_phone,
      "provider_phone": provider_phone,
      "provider_website": provider_website,
      "pharmacy_phone": pharmacy_phone,
      "pharmacy_claims_address": pharmacy_claims_address,
  }


def _merge_insurance_card_fields(
    primary_fields: dict[str, str],
    supplemental_fields: dict[str, str],
) -> dict[str, str]:
  return {
      field_name: primary_fields.get(field_name) or supplemental_fields.get(field_name, "")
      for field_name in (
          "payer_name",
          "payer_id",
          "member_id",
          "group_number",
          "rx_bin",
          "rx_pcn",
          "rx_group",
          "member_phone",
          "provider_phone",
          "provider_website",
          "pharmacy_phone",
          "pharmacy_claims_address",
      )
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
      "member_phone": insurance.member_phone,
      "provider_phone": insurance.provider_phone,
      "provider_website": insurance.provider_website,
      "pharmacy_phone": insurance.pharmacy_phone,
      "pharmacy_claims_address": insurance.pharmacy_claims_address,
  }

  return [
      FIELD_NAME_MAP[field_name]
      for field_name, field_value in values.items()
      if not field_value
  ]


def _build_warnings(
    ocr_results: Sequence[OCRDocumentResult],
    missing_fields: list[str],
    plausibility_flags: list[str],
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

  if plausibility_flags:
      warnings.append(
          Warning(
              code="EXTRACTION-PLAUSIBILITY",
              message=(
                  "Rejected implausible OCR values for: "
                  + ", ".join(plausibility_flags)
                  + ". Manual review is required before verification."
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
  insurance_front_result = _find_result(ocr_results, "insurance_front")
  insurance_back_result = _find_result(ocr_results, "insurance_back")

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
  insurance_front_fields = _extract_insurance_card_fields(
      insurance_front_result
      or OCRDocumentResult(
          document_type="insurance_front",
          text="",
          lines=[],
          confidence=0.0,
          variant="unavailable",
      )
  )
  insurance_back_fields = _extract_insurance_back_fields(
      insurance_back_result
      or OCRDocumentResult(
          document_type="insurance_back",
          text="",
          lines=[],
          confidence=0.0,
          variant="unavailable",
      )
  )
  insurance_fields = _merge_insurance_card_fields(
      insurance_front_fields,
      insurance_back_fields,
  )

  patient = normalize_patient(Patient(**patient_fields))
  patient, plausibility_flags = _apply_plausibility_checks(patient)
  insurance = normalize_insurance(
      Insurance(
          payer_name=insurance_fields["payer_name"],
          payer_id=insurance_fields["payer_id"],
          member_id=insurance_fields["member_id"],
          group_number=insurance_fields["group_number"],
          rx_bin=insurance_fields["rx_bin"],
          rx_pcn=insurance_fields["rx_pcn"],
          rx_group=insurance_fields["rx_group"],
          member_phone=insurance_fields["member_phone"],
          provider_phone=insurance_fields["provider_phone"],
          provider_website=insurance_fields["provider_website"],
          pharmacy_phone=insurance_fields["pharmacy_phone"],
          pharmacy_claims_address=insurance_fields["pharmacy_claims_address"],
      )
  )

  missing_fields = _build_missing_fields(patient, insurance)
  warnings = _build_warnings(ocr_results, missing_fields, plausibility_flags)

  return ExtractionResponse(
      patient=patient,
      insurance=insurance,
      confidence=_calculate_confidence(ocr_results, missing_fields),
      document_notes=_build_document_notes(ocr_results),
      missing_fields=missing_fields,
      warnings=warnings,
  )

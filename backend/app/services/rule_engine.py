from dataclasses import dataclass

from app.constants import KNOWN_ACTIVE_MEMBER_IDS, KNOWN_INACTIVE_MEMBER_IDS
from app.schemas.common import CoverageStatus, VerificationStatus, Warning
from app.schemas.patient import Patient
from app.schemas.summary import CopaySummary, PharmacyInfo
from app.schemas.verification import VerificationRequest
from app.services.normalization_service import normalize_insurance, normalize_patient


@dataclass
class RuleEngineResult:
  verification_status: VerificationStatus
  coverage_status: CoverageStatus
  copays: CopaySummary
  pharmacy_info: PharmacyInfo
  warnings: list[Warning]
  returned_patient: Patient


def _build_pharmacy_info(request: VerificationRequest) -> PharmacyInfo:
  return PharmacyInfo(
      bin=request.insurance.rx_bin or "610279",
      pcn=request.insurance.rx_pcn or "03200000",
      group=request.insurance.rx_group or "MDRX01",
      processor="MedRx Advance",
  )


def _build_active_result(request: VerificationRequest) -> RuleEngineResult:
  patient = normalize_patient(request.patient)
  returned_patient = patient.model_copy(
      update={"address": f"{patient.address}, Apt 2"}
  )

  return RuleEngineResult(
      verification_status=VerificationStatus.verified,
      coverage_status=CoverageStatus.active,
      copays=CopaySummary(
          primary_care="$25",
          specialist="$40",
          urgent_care="$60",
          pharmacy="Tiered copay plan",
      ),
      pharmacy_info=_build_pharmacy_info(request),
      warnings=[
          Warning(
              code="COPAY-DUE",
              message="Office visit copay should be collected at check-in.",
              severity="warning",
          ),
          Warning(
              code="PCP-REFERRAL",
              message="Specialist visits may require PCP referral confirmation.",
              severity="info",
          ),
      ],
      returned_patient=returned_patient,
  )


def _build_inactive_result(request: VerificationRequest) -> RuleEngineResult:
  patient = normalize_patient(request.patient)

  return RuleEngineResult(
      verification_status=VerificationStatus.verified,
      coverage_status=CoverageStatus.inactive,
      copays=CopaySummary(
          primary_care="Not available",
          specialist="Not available",
          urgent_care="Not available",
          pharmacy="Inactive coverage",
      ),
      pharmacy_info=_build_pharmacy_info(request),
      warnings=[
          Warning(
              code="COVERAGE-INACTIVE",
              message="Member record was found, but coverage is inactive for today.",
              severity="critical",
          )
      ],
      returned_patient=patient,
  )


def _build_manual_review_result(
    request: VerificationRequest,
    warning: Warning,
) -> RuleEngineResult:
  patient = normalize_patient(request.patient)

  return RuleEngineResult(
      verification_status=VerificationStatus.manual_review,
      coverage_status=CoverageStatus.unknown,
      copays=CopaySummary(
          primary_care="Manual review",
          specialist="Manual review",
          urgent_care="Manual review",
          pharmacy="Manual review",
      ),
      pharmacy_info=_build_pharmacy_info(request),
      warnings=[warning],
      returned_patient=patient,
  )


def evaluate_eligibility(request: VerificationRequest) -> RuleEngineResult:
  request.patient = normalize_patient(request.patient)
  request.insurance = normalize_insurance(request.insurance)

  member_id = request.insurance.member_id

  if not member_id:
      return _build_manual_review_result(
          request,
          Warning(
              code="MEMBER-ID-MISSING",
              message="Member ID is required before eligibility can be verified.",
              severity="critical",
          ),
      )

  if member_id in KNOWN_INACTIVE_MEMBER_IDS:
      return _build_inactive_result(request)

  if member_id in KNOWN_ACTIVE_MEMBER_IDS or member_id.startswith("XJH"):
      return _build_active_result(request)

  return _build_manual_review_result(
      request,
      Warning(
          code="ELIGIBILITY-REVIEW-REQUIRED",
          message="No deterministic demo match was found for this member ID. Review eligibility manually.",
          severity="warning",
      ),
  )

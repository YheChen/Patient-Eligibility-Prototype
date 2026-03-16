from app.schemas.insurance import Insurance
from app.schemas.patient import Patient
from app.utils.text_utils import normalize_whitespace


def normalize_patient(patient: Patient) -> Patient:
  return Patient(
      first_name=normalize_whitespace(patient.first_name).title(),
      middle_name=normalize_whitespace(patient.middle_name).title(),
      last_name=normalize_whitespace(patient.last_name).title(),
      date_of_birth=normalize_whitespace(patient.date_of_birth),
      address=normalize_whitespace(patient.address),
      city=normalize_whitespace(patient.city).title(),
      state=normalize_whitespace(patient.state).upper(),
      postal_code=normalize_whitespace(patient.postal_code),
  )


def normalize_insurance(insurance: Insurance) -> Insurance:
  return Insurance(
      payer_name=normalize_whitespace(insurance.payer_name),
      payer_id=normalize_whitespace(insurance.payer_id).upper(),
      member_id=normalize_whitespace(insurance.member_id).upper(),
      group_number=normalize_whitespace(insurance.group_number).upper(),
      rx_bin=normalize_whitespace(insurance.rx_bin),
      rx_pcn=normalize_whitespace(insurance.rx_pcn).upper(),
      rx_group=normalize_whitespace(insurance.rx_group).upper(),
      member_phone=normalize_whitespace(insurance.member_phone),
      provider_phone=normalize_whitespace(insurance.provider_phone),
      provider_website=normalize_whitespace(insurance.provider_website).lower(),
      pharmacy_phone=normalize_whitespace(insurance.pharmacy_phone),
      pharmacy_claims_address=normalize_whitespace(insurance.pharmacy_claims_address),
  )

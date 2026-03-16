from app.schemas.common import APIModel


class Insurance(APIModel):
  payer_name: str
  payer_id: str
  member_id: str
  group_number: str = ""
  rx_bin: str = ""
  rx_pcn: str = ""
  rx_group: str = ""
  member_phone: str = ""
  provider_phone: str = ""
  provider_website: str = ""
  pharmacy_phone: str = ""
  pharmacy_claims_address: str = ""

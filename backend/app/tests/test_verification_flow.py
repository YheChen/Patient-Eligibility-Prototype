def test_verification_flow_returns_summary_and_raw_271(client):
  payload = {
      "patient": {
          "firstName": "Avery",
          "middleName": "Jordan",
          "lastName": "Carter",
          "dateOfBirth": "1988-11-04",
          "address": "123 Harbor Street",
          "city": "Baltimore",
          "state": "MD",
          "postalCode": "21201",
      },
      "insurance": {
          "payerName": "Blue Cross Blue Shield of Maryland",
          "payerId": "BCBSMD01",
          "memberId": "XJH123456789",
          "groupNumber": "GRP-45029",
          "rxBin": "610279",
          "rxPcn": "03200000",
          "rxGroup": "MDRX01",
      },
  }

  response = client.post("/api/verification/verify", json=payload)

  assert response.status_code == 200

  body = response.json()

  assert body["summary"]["verificationStatus"] == "verified"
  assert body["summary"]["coverageStatus"] == "active"
  assert body["summary"]["payerName"] == "Blue Cross Blue Shield of Maryland"
  assert body["summary"]["memberId"] == "XJH123456789"
  assert body["summary"]["discrepancies"][0]["field"] == "address"
  assert "ISA*00*" in body["raw271"]
  assert body["warnings"][0]["code"] == "COPAY-DUE"


def test_verification_flow_uses_unknown_member_warning_for_manual_review(client):
  payload = {
      "patient": {
          "firstName": "Michael",
          "middleName": "",
          "lastName": "Motorist",
          "dateOfBirth": "1978-08-31",
          "address": "245 Anywhere Street",
          "city": "Yourcity",
          "state": "NY",
          "postalCode": "12345",
      },
      "insurance": {
          "payerName": "UnitedHealthcare",
          "payerId": "06111",
          "memberId": "00040560100",
          "groupNumber": "1274551",
          "rxBin": "610279",
          "rxPcn": "9999",
          "rxGroup": "UNITEDRX",
      },
  }

  response = client.post("/api/verification/verify", json=payload)

  assert response.status_code == 200

  body = response.json()

  assert body["summary"]["verificationStatus"] == "manual_review"
  assert body["summary"]["coverageStatus"] == "unknown"
  assert body["warnings"][0]["code"] == "ELIGIBILITY-REVIEW-REQUIRED"
  assert "MEMBER-ID-MISSING" not in body["raw271"]


def test_verification_flow_keeps_missing_member_id_warning(client):
  payload = {
      "patient": {
          "firstName": "Michael",
          "middleName": "",
          "lastName": "Motorist",
          "dateOfBirth": "1978-08-31",
          "address": "245 Anywhere Street",
          "city": "Yourcity",
          "state": "NY",
          "postalCode": "12345",
      },
      "insurance": {
          "payerName": "UnitedHealthcare",
          "payerId": "06111",
          "memberId": "",
          "groupNumber": "1274551",
          "rxBin": "610279",
          "rxPcn": "9999",
          "rxGroup": "UNITEDRX",
      },
  }

  response = client.post("/api/verification/verify", json=payload)

  assert response.status_code == 200

  body = response.json()

  assert body["summary"]["verificationStatus"] == "manual_review"
  assert body["warnings"][0]["code"] == "MEMBER-ID-MISSING"

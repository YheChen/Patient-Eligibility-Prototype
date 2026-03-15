from app.services.extraction_service import OCRDocumentResult


def test_documents_extract_returns_structured_data(client, sample_png_bytes, monkeypatch):
  def fake_run_ocr_for_documents(_documents):
      return [
          OCRDocumentResult(
              document_type="driver_license",
              text="",
              lines=[
                  "LAST NAME",
                  "Carter",
                  "FIRST NAME",
                  "Avery",
                  "MIDDLE NAME",
                  "Jordan",
                  "DOB 11/04/1988",
                  "123 Harbor Street",
                  "Baltimore MD 21201",
              ],
              confidence=89.0,
              variant="grayscale",
          ),
          OCRDocumentResult(
              document_type="insurance_id",
              text="",
              lines=[
                  "BLUE CROSS BLUE SHIELD OF MARYLAND",
                  "MEMBER ID XJH123456789",
                  "PAYER ID BCBSMD01",
                  "GROUP NUMBER GRP-45029",
                  "RX BIN 610279",
                  "RX PCN 03200000",
                  "RX GROUP MDRX01",
              ],
              confidence=86.0,
              variant="grayscale",
          ),
      ]

  monkeypatch.setattr(
      "app.services.extraction_service.run_ocr_for_documents",
      fake_run_ocr_for_documents,
  )

  files = {
      "driver_license": ("drivers-license.png", sample_png_bytes, "image/png"),
      "insurance_id": ("insurance-id.png", sample_png_bytes, "image/png"),
  }

  response = client.post("/api/documents/extract", files=files)

  assert response.status_code == 200

  payload = response.json()

  assert payload["patient"]["firstName"] == "Avery"
  assert payload["patient"]["lastName"] == "Carter"
  assert payload["insurance"]["memberId"] == "XJH123456789"
  assert payload["insurance"]["rxBin"] == "610279"
  assert payload["confidence"] > 0.8
  assert len(payload["documentNotes"]) == 2
  assert payload["missingFields"] == []
  assert payload["warnings"][0]["code"] == "OCR-REVIEW"


def test_documents_extract_reports_missing_fields(client, sample_png_bytes, monkeypatch):
  def fake_run_ocr_for_documents(_documents):
      return [
          OCRDocumentResult(
              document_type="driver_license",
              text="",
              lines=[
                  "FIRST NAME",
                  "Avery",
                  "LAST NAME",
                  "Carter",
              ],
              confidence=42.0,
              variant="grayscale",
          ),
          OCRDocumentResult(
              document_type="insurance_id",
              text="",
              lines=[],
              confidence=0.0,
              variant="grayscale",
          ),
      ]

  monkeypatch.setattr(
      "app.services.extraction_service.run_ocr_for_documents",
      fake_run_ocr_for_documents,
  )

  files = {
      "driver_license": ("drivers-license.png", sample_png_bytes, "image/png"),
      "insurance_id": ("insurance-id.png", sample_png_bytes, "image/png"),
  }

  response = client.post("/api/documents/extract", files=files)

  assert response.status_code == 200

  payload = response.json()

  assert "dateOfBirth" in payload["missingFields"]
  assert "payerName" in payload["missingFields"]
  assert "memberId" in payload["missingFields"]
  assert "rxBin" in payload["missingFields"]
  warning_codes = {warning["code"] for warning in payload["warnings"]}
  assert "OCR-NO-TEXT" in warning_codes
  assert "OCR-LOW-CONFIDENCE" in warning_codes
  assert "EXTRACTION-INCOMPLETE" in warning_codes

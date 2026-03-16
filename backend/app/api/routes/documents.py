from fastapi import APIRouter, File, UploadFile

from app.schemas.extraction import ExtractionResponse
from app.services.extraction_service import extract_from_documents
from app.services.image_validation_service import validate_image_upload
from app.services.storage_service import save_upload

router = APIRouter()


@router.post("/extract", response_model=ExtractionResponse)
async def extract_documents(
    driver_license: UploadFile = File(...),
    insurance_front: UploadFile = File(...),
    insurance_back: UploadFile = File(...),
) -> ExtractionResponse:
  uploads = {
      "driver_license": driver_license,
      "insurance_front": insurance_front,
      "insurance_back": insurance_back,
  }

  stored_documents = []

  for document_type, upload in uploads.items():
      file_bytes = await validate_image_upload(upload, document_type)
      stored_documents.append(
          save_upload(
              document_type=document_type,
              original_filename=upload.filename or document_type,
              content_type=upload.content_type or "application/octet-stream",
              file_bytes=file_bytes,
          )
      )

  return extract_from_documents(stored_documents)

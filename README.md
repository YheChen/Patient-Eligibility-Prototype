# MDLand Eligibility Prototype

Prototype submission for the MDLand patient eligibility evaluation.

The app demonstrates a front-desk intake flow that:

1. accepts a driver's license plus insurance card front and back
2. extracts structured patient and insurance fields
3. lets staff review and correct the extracted values
4. submits the edited data to a verification API
5. returns a front-desk summary with coverage, copays, pharmacy details, warnings, discrepancies, raw `271`, and the structured JSON summary returned by the API

## Demo Video

Watch the short demo here:

https://youtu.be/SNQb_Ei9BRU

## Demo Scope

The current MVP is intentionally frontend-first and prototype-oriented.

- Frontend: React + TypeScript + Vite + Axios with local component state
- Backend: FastAPI + Pydantic
- OCR: Tesseract via `pytesseract` + `Pillow`
- Verification: deterministic demo rules
- Persistence: intentionally omitted

This is a working prototype, not a production eligibility system.

## Architecture

### Frontend

The frontend lives in [frontend](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/frontend) and is built around a single workflow page in [HomePage.tsx](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/frontend/src/pages/HomePage.tsx).

Main responsibilities:

- collect the three document uploads
- call the extract API
- show OCR output in an editable review form
- call the verification API
- render the front-desk summary, warnings, raw `271`, and returned JSON summary

The UI is composed of focused presentational components such as:

- [FileUploadSection.tsx](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/frontend/src/components/FileUploadSection.tsx)
- [ExtractionReviewForm.tsx](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/frontend/src/components/ExtractionReviewForm.tsx)
- [VerificationSummary.tsx](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/frontend/src/components/VerificationSummary.tsx)
- [WarningList.tsx](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/frontend/src/components/WarningList.tsx)
- [Raw271Viewer.tsx](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/frontend/src/components/Raw271Viewer.tsx)
- [JsonSummaryViewer.tsx](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/frontend/src/components/JsonSummaryViewer.tsx)

### Backend

The backend lives in [backend/app](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/backend/app).

Entry point:

- [main.py](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/backend/app/main.py)

Routes:

- `GET /api/health` in [health.py](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/backend/app/api/routes/health.py)
- `POST /api/documents/extract` in [documents.py](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/backend/app/api/routes/documents.py)
- `POST /api/verification/verify` in [verification.py](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/backend/app/api/routes/verification.py)

Core services:

- OCR + field parsing: [extraction_service.py](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/backend/app/services/extraction_service.py)
- upload validation: [image_validation_service.py](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/backend/app/services/image_validation_service.py)
- file storage: [storage_service.py](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/backend/app/services/storage_service.py)
- verification orchestration: [verification_service.py](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/backend/app/services/verification_service.py)
- deterministic eligibility rules: [rule_engine.py](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/backend/app/services/rule_engine.py)
- simplified `271` generation: [edi271_generator.py](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/backend/app/services/edi271_generator.py)
- simplified `271` parsing: [edi271_parser.py](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/backend/app/services/edi271_parser.py)
- discrepancy detection: [discrepancy_service.py](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/backend/app/services/discrepancy_service.py)

### Request Flow

1. The user uploads a driver's license, insurance front, and insurance back.
2. The frontend sends `multipart/form-data` to `POST /api/documents/extract`.
3. The backend validates file type and size, saves the uploads locally, runs OCR on each image, and returns structured patient + insurance fields with warnings, confidence, and missing fields.
4. The user edits any incorrect values in the review form.
5. The frontend sends structured JSON to `POST /api/verification/verify`.
6. The backend applies deterministic eligibility rules, generates a simplified `271`, parses it back into structured data, compares returned values for discrepancies, and returns:
   - `summary`
   - `warnings`
   - `raw271`
   - `checkedAt`
7. The frontend renders that result for front-desk staff.

## API Surface

### `POST /api/documents/extract`

Accepts:

- `driver_license`
- `insurance_front`
- `insurance_back`

Returns a structured extraction payload with:

- `patient`
- `insurance`
- `confidence`
- `documentNotes`
- `missingFields`
- `warnings`

### `POST /api/verification/verify`

Accepts:

- `patient`
- `insurance`

Returns:

- `summary`
- `warnings`
- `raw271`
- `checkedAt`

The structured JSON summary is assembled in [verification_service.py](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/backend/app/services/verification_service.py) and displayed in the frontend's "Structured JSON Summary" panel.

## Design Decisions

### Frontend-first workflow

I built the UI flow before introducing real backend behavior so the intake experience could be validated early. This made it easier to settle the request and response shapes before tightening the service implementations.

### Keep the backend modular

The backend separates concerns into services instead of putting OCR, parsing, rule evaluation, `271` handling, and response assembly directly in the route functions. That keeps the routes small and makes the logic easier to test in isolation.

### Use Pydantic contracts end-to-end

The backend request and response models are defined with Pydantic, and the frontend mirrors those shapes in TypeScript. That made the extract and verify contracts explicit and reduced ambiguity between layers.

### Use Tesseract OCR for a real extraction path

Instead of keeping extraction fully mocked, the prototype uses Tesseract so the app can process actual image uploads. The parsing layer on top is intentionally heuristic and optimized for demo-readability rather than full document robustness.

### Omit the database for the prototype

There is no persistence layer in this version. Uploads are saved locally, but extraction and verification results are not stored in a database. For this take-home, that kept the scope focused on the intake flow itself rather than migrations, data modeling for storage, or CRUD behavior that the demo does not yet need.

## Trade-offs

### Real OCR, simplified parsing

The prototype does real OCR, but the field extraction logic is rule-based and document-shape-sensitive. That is enough to demonstrate the workflow, but it is less robust than a production document AI pipeline.

### Simplified `271` format

The app generates and parses a simplified `271`-like message instead of a complete production-grade X12 implementation. This keeps the demo understandable and testable, but it is not a full interchange implementation.

### Deterministic rule engine instead of payer integration

The verification result is driven by demo rules in [rule_engine.py](/Users/yanzhenchen/Desktop/GitHub%20Projects/MDLand/backend/app/services/rule_engine.py), not by a real clearinghouse or payer endpoint. That makes the prototype easy to run locally, but it also means some outcomes are intentionally simulated.

### No background processing

OCR and verification happen inline in the request cycle. That keeps the prototype simple, but a production version would likely move extraction, retries, and third-party communication into async jobs or a queue-based workflow.

### No persistence

Skipping the database reduced setup overhead and let the prototype stay lightweight. The downside is that there is no document history, no verification audit trail, and no stored record of prior runs.

## Known Limitations

- Driver's license OCR is still the weakest part of the pipeline. Low-quality screenshots, glare, cropping, and mixed layouts can still produce incorrect names or addresses.
- Insurance parsing is still heuristic. Some fields, especially group number and provider website, are sensitive to OCR formatting and line breaks.
- The generated `271` is simplified and does not fully match a real production X12 `271`.
- The discrepancy check is limited because the generated `271` mostly reflects the submitted request values.
- Eligibility outcomes are prototype rules, not real payer responses.
- There is no authentication, authorization, encryption-at-rest strategy, PHI retention policy, or audit logging beyond prototype-level local handling.
- Uploaded files are written to the local upload directory configured by `UPLOAD_DIR`.
- There is no database, migration system, or persistent storage model in this version.
- There are backend tests, but there is no frontend unit test suite or browser E2E test suite yet.

## Security And Compliance Notes

This repository is a prototype and should not be treated as production-ready for PHI.

Current state:

- uploads are validated for file type and size
- uploads are stored locally
- no auth is implemented
- no database is used
- no dedicated audit trail is implemented

A production version would need stronger safeguards around access control, storage, retention, transport security, observability, and secrets handling.

## Local Run

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`.

### Backend (macOS)

Install Tesseract first:

```bash
brew install tesseract
```

Then run:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend runs on `http://localhost:8000`.

### Backend (Windows PowerShell)

Install Tesseract OCR for Windows first and make sure the `tesseract` executable is available on your `PATH`.

Then run:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend runs on `http://localhost:8000`.

Health check:

```text
http://localhost:8000/api/health
```

## Testing

Backend tests:

```bash
backend/.venv/bin/pytest backend/app/tests -q
```

Frontend production build:

```bash
cd frontend
npm run build
```

## Suggested Next Steps Towards Production

- replace heuristic OCR parsing with a more robust document extraction pipeline
- implement a more realistic X12 `271` mapping layer
- add persistence for auditability, retries, and verification history, connect to MongoDb/FireBase NoSQL database
- add authentication and role-based access controls
- add frontend tests and browser-level end-to-end coverage
- add async processing for OCR and verification tasks
- improve observability and structured error reporting

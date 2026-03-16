# MDland-patient-eligibility-prototype

Prototype repository for the MDLand hiring take-home

## MVP Demo Scope

The current demo supports this end-to-end flow:

1. Upload a driver's license plus the insurance card front and back.
2. Send the files to a FastAPI backend extract endpoint.
3. Review and edit the returned patient and insurance fields in the React UI.
4. Submit the edited values to a verification endpoint.
5. View a front-desk summary with coverage, copays, pharmacy details, warnings, discrepancies, and raw 271 text.

## Current Implementation

- Frontend: React + TypeScript + Vite + Axios with local component state
- Backend: FastAPI + Pydantic
- Extraction: Tesseract OCR + heuristic field parsing after validating and saving uploads
- Verification: deterministic demo rules plus simplified 271 generation/parsing
- Persistence: intentionally omitted for the demo

## Demo Notes

- This version does not use a database.
- Uploaded files are saved locally in the backend upload directory.
- If this prototype were extended, a database layer could be added later for document history, verification logs, audit trails, and reporting.

## Out of Scope

- Production-grade OCR tuning or document AI extraction
- Real payer or clearinghouse integrations
- Authentication and authorization
- Production deployment hardening
- Background jobs and async processing

## Local Run

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on `http://localhost:5173`.

### Backend

```bash
brew install tesseract
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Runs on `http://localhost:8000`.

# mdland-eligibility-prototype

Prototype repository for the MDLand hiring take-home.

## Phase 0 MVP Scope

The first MVP is a frontend-first eligibility verification workflow for a healthcare intake desk.

### In Scope

The app should support this end-to-end demo flow:

1. Show a single page with three upload inputs.
2. Let a user select:
   - a driver's license
   - an insurance card front image
   - an insurance card back image
3. Let the user trigger an `Extract` action.
4. Show extracted patient and insurance fields in an editable review form.
5. Let the user trigger a `Verify Eligibility` action.
6. Show a front-desk summary with:
   - coverage status
   - copays
   - pharmacy information
   - warnings
   - raw 271 response text

### Initial Delivery Strategy

- Frontend is built first.
- Frontend uses mock data before any real backend integration.
- Backend structure is prepared now, but business logic is intentionally deferred.

### Out of Scope for the MVP

- Real OCR or document extraction
- Real payer or clearinghouse integrations
- Authentication and authorization
- Production deployment hardening
- Background jobs and async processing
- Persistent audit/history workflows

## Planned Stack

- Backend: FastAPI, Pydantic, SQLAlchemy, SQLite, Alembic
- Frontend: React, TypeScript, Axios, local component state
- Explicitly not included right now: Prisma, TanStack Query, React Hook Form, Zod

## Phase 1 Setup Status

Phase 1 focuses on repository scaffolding and project initialization:

- Root project files are initialized
- Frontend build tooling is configured with React + TypeScript + Vite
- Backend dependency and Alembic configuration files are prepared
- Source files under `frontend/src/` and `backend/app/` remain intentionally unimplemented for the next phase

## Next Build Phase

Phase 2 will implement the frontend shell and mocked user flow:

1. Layout and page structure
2. File uploads and optional previews
3. Editable extraction review form
4. Mock verification summary
5. Loading and error states

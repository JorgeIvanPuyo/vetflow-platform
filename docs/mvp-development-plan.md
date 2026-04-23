# MVP Development Plan

## Objective
Build the Vetflow Platform MVP in an ordered, incremental, and testable way, using vertical slices that connect backend and frontend progressively.

The MVP must validate the core veterinary workflow for pilot users while keeping the architecture aligned with a future multi-tenant SaaS product.

---

## Current Status

### Completed
- Monorepo initialized
- Base documentation for Codex created
- Backend running locally with Docker
- PostgreSQL running locally
- Alembic configured and working
- Base multi-tenant structure created
- Tenant and User base models created
- Owners CRUD implemented
- Patients CRUD implemented
- Owner ↔ Patient relationship implemented
- Tenant isolation applied through temporary `X-Tenant-Id` header
- Basic backend tests for owners and patients passing

### In Progress
- Defining execution roadmap for the remaining MVP

### Not Started
- Frontend base
- Search
- Clinical history
- Consultations
- Exams and results
- CI/CD implementation
- Frontend tests
- Pilot hardening

---

## Development Strategy

### Rule
Development must proceed in vertical slices.

Each slice should close with:
1. backend implemented
2. endpoints tested
3. frontend connected
4. manual validation completed
5. docs updated if needed

### Principle
Do not build all backend first and frontend later.
Do not build disconnected UI without real backend integration.

The recommended flow is:
- create the backend capability
- connect it in frontend quickly
- validate manually
- move to the next slice

---

## MVP Phases and Slices

# Phase A — Foundation

## A1. Technical foundation
**Status:** Done

Includes:
- repo structure
- base docs
- FastAPI running
- PostgreSQL in Docker
- Alembic
- base Docker setup

## A2. Multi-tenant base
**Status:** Done

Includes:
- Tenant model
- User model
- tenant-aware strategy
- temporary tenant resolution by header

---

# Phase B — Clinical Core Backend

## B1. Owners and Patients
**Status:** Done

Includes:
- owners CRUD
- patients CRUD
- relationship owner ↔ patient
- tenant-aware filtering
- basic backend tests

## B2. Global Search
**Status:** Pending
**Priority:** High

Goal:
- search across owners and patients

Must include:
- search by owner name
- search by owner phone
- search by patient name
- tenant-aware results
- simple and frontend-friendly response structure

Deliverables:
- backend endpoint
- service/repository support
- tests
- frontend integration

## B3. Clinical History Structure
**Status:** Pending
**Priority:** High

Goal:
- define the patient clinical history structure and traceability base

Must include:
- clinical history view model or event structure
- patient timeline structure
- ability to aggregate consultations and exams under patient history

Deliverables:
- backend models/schemas/routes as needed
- frontend patient history view

## B4. Consultations
**Status:** Pending
**Priority:** High

Goal:
- implement the structured veterinary consultation workflow

Must include:
- anamnesis
- clinical exam
- presumptive diagnosis
- diagnostic plan
- therapeutic plan
- final diagnosis
- indications

Deliverables:
- consultation model(s)
- consultation CRUD/update flows
- patient consultation listing
- frontend consultation form/workflow

## B5. Exams and Results
**Status:** Pending
**Priority:** High

Goal:
- allow veterinary users to request and register exams/results

Must include:
- create exam request
- update exam status
- attach result data
- associate result with patient and consultation

Deliverables:
- backend routes/services/models
- frontend exam/result UI

---

# Phase C — Frontend Experience Layer

## C1. Frontend Base
**Status:** Pending
**Priority:** High

Goal:
- initialize the web app correctly and connect it to the existing backend

Must include:
- Next.js app initialized properly
- mobile-first layout
- base routing
- API client
- environment config
- temporary `X-Tenant-Id` support
- basic navigation

Deliverables:
- app runs locally
- backend communication works
- initial layout and structure ready

## C2. Owners and Patients Frontend
**Status:** Pending
**Priority:** High

Goal:
- connect existing backend owners/patients module to real UI

Must include:
- list owners
- create owner
- list patients
- create patient
- patient detail basic view

Deliverables:
- real frontend screens
- backend integration working
- manual validation of CRUD flows

## C3. Search Frontend
**Status:** Pending
**Priority:** High

Goal:
- expose global search to the user

Must include:
- search input
- result list
- navigation to owner/patient details

---

# Phase D — MVP Hardening

## D1. Validation and UX hardening
**Status:** Pending

Must include:
- better backend error consistency
- useful empty states
- loading states
- user-friendly validation feedback

## D2. Testing hardening
**Status:** Pending

Must include:
- broader backend tests
- key frontend flow coverage
- regression prevention

## D3. CI/CD implementation
**Status:** Pending

Must include:
- GitHub Actions validation workflows
- backend deployment flow to Cloud Run
- frontend deployment flow to Vercel
- path-based execution

---

## Recommended Immediate Sequence

### Step 1
Create and stabilize the frontend base.

### Step 2
Connect frontend to the existing Owners and Patients backend.

### Step 3
Implement backend Global Search.

### Step 4
Connect frontend Search.

### Step 5
Move to Clinical History.

### Step 6
Move to Consultations.

### Step 7
Move to Exams and Results.

---

## Today’s Working Goal

### Target section to complete today
1. Frontend base
2. Frontend connection to Owners and Patients
3. Backend Global Search
4. Frontend Search

If time allows, close the full search section end-to-end.

---

## Out of Scope for Current MVP Stage

Do not work on these yet unless explicitly reprioritized:
- inventory
- scheduling
- prescriptions as a standalone module
- dashboards
- reports
- billing
- native mobile app
- full authentication and RBAC

---

## Operational Rule for Codex

For each new slice:
- read current docs first
- implement only the requested slice
- do not redesign architecture
- do not add postponed modules
- keep backend and frontend aligned
- prefer simple, maintainable solutions

---

## Suggested Progress Tracking

Use this table and update status as work advances:

| Slice | Description | Status |
|------|-------------|--------|
| A1 | Technical foundation | Done |
| A2 | Multi-tenant base | Done |
| B1 | Owners and Patients backend | Done |
| C1 | Frontend base | Pending |
| C2 | Owners and Patients frontend | Pending |
| B2 | Global Search backend | Pending |
| C3 | Global Search frontend | Pending |
| B3 | Clinical History | Pending |
| B4 | Consultations | Pending |
| B5 | Exams and Results | Pending |
| D1 | Validation and UX hardening | Pending |
| D2 | Testing hardening | Pending |
| D3 | CI/CD implementation | Pending |

---

## Next Action
The next correct action is:

**Build the frontend base and connect it to the existing Owners and Patients backend before continuing deeper into backend-only development.**

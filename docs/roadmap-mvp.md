# MVP Roadmap

## Development Strategy
The MVP will be built using vertical slices. Each slice must be completed end-to-end before moving to the next one.

## Slice 0 - Project Foundation
Goal:
- establish repo structure
- define architecture and conventions
- configure local environments
- define CI/CD base
- define database strategy
- prepare Codex guidance docs

Deliverables:
- docs completed
- monorepo structure
- local run instructions
- initial workflows

## Slice 1 - Multi-Tenant Foundation
Goal:
- support 3 pilot users
- define tenants and users
- isolate data per tenant
- establish authentication strategy

Deliverables:
- tenant model
- user model
- tenant-aware backend foundation
- tenant-aware frontend session structure

## Slice 2 - Owners and Patients
Goal:
- CRUD for owners
- CRUD for patients
- relationship owner-patient
- filters and search basics
- alerts for allergies and chronic conditions

Deliverables:
- owner management
- patient management
- patient list and detail views

## Slice 3 - Clinical History
Goal:
- patient timeline
- structured clinical record visualization
- chronological traceability

Deliverables:
- patient clinical summary
- consultation timeline
- exam/event visibility

## Slice 4 - Structured Consultations
Goal:
- guided consultation workflow
- clinical note consistency
- storage of all consultation sections

Deliverables:
- anamnesis
- clinical exam
- presumptive diagnosis
- diagnostic plan
- therapeutic plan
- final diagnosis
- indications

## Slice 5 - Exams and Results
Goal:
- request exams
- attach results
- associate all results to patient history and consultation

Deliverables:
- exam request workflow
- results registration
- exam history

## Slice 6 - Global Search
Goal:
- fast access to owners and patients
- improved navigation and productivity

Deliverables:
- global search input
- search by patient name
- search by owner name
- search by contact reference

## Slice 7 - Hardening
Goal:
- improve validations
- improve UX states
- increase test coverage
- prepare pilot release

Deliverables:
- stable MVP release candidate

## Post-MVP
Deferred modules:
- inventory
- scheduling
- prescriptions
- dashboard
- reports
- settings enhancements
- native mobile app

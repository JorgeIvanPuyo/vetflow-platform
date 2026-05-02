# MVP Roadmap

This roadmap is the current source of truth for the Vetflow MVP. It preserves the original vertical-slice history while reflecting what is actually implemented in the repository today.

Status labels:
- ✅ Completed
- 🟡 In Progress
- ⏳ Next
- 🔵 Planned
- ⚪ Deferred

## Current State

Vetflow is a multi-tenant veterinary clinical platform where each tenant represents a clinic. Users within the same clinic share owners, patients, consultations, exams, preventive care, file references, appointments, follow-ups, inventory, and dashboard data through tenant-scoped backend access.

The MVP currently supports the core clinical workflow end to end: authenticated clinic access, owner and patient management, expanded patient detail, unified clinical history, structured consultations, exams/results, preventive care, clinical files in storage, agenda, follow-ups, dashboard, clinic profile, and MVP inventory.

The main active gap is the consultation therapeutic plan frontend integration with inventory-backed medications. The backend inventory deduction path exists; the remaining MVP work is the user-facing therapeutic plan inventory selector flow.

## Chronological MVP Slices

### ✅ Completed - Slice 0 - Project Foundation

Goal:
- Establish the technical foundation for local development, deployment, documentation, and database evolution.

Completed:
- Monorepo configured.
- FastAPI backend implemented.
- Next.js frontend implemented.
- Base Codex/project documentation created.
- Local Docker environment available.
- PostgreSQL support available.
- Alembic configured for migrations.
- Backend CI/CD configured.
- Backend deployment path to Cloud Run established.
- Frontend deployment path to Vercel established.

### ✅ Completed - Slice 1 - Multi-Tenant Foundation

Goal:
- Support pilot clinics with tenant isolation and authenticated clinic-scoped access.

Completed:
- Tenant model implemented.
- User model implemented.
- Tenant represents the clinic/organization.
- Multiple veterinarians can belong to the same tenant.
- Clinic users share patients and clinical records within the same tenant.
- Multi-tenancy implemented with `tenant_id`.
- Tenant-aware repositories/services across business modules.
- Firebase Authentication integrated.
- Bearer-token authenticated frontend/backend flow.
- Real tenant resolution from authenticated user context.
- User traceability implemented across clinical records.

### ✅ Completed - Slice 2 - Owners and Patients

Goal:
- Provide complete owner and patient management with tenant-aware data isolation.

Completed:
- Owners CRUD.
- Patients CRUD.
- Owner-patient relationship.
- Owner detail view.
- Patient detail fully expanded.
- Safe owner creation, editing, and deletion flows.
- Safe patient creation, editing, and deletion flows.
- Controlled cascade deletion for dependent clinical data.
- Mobile-first owner and patient screens.
- Allergy and chronic condition alerts.

### ✅ Completed - Slice 3 - Clinical History Core

Goal:
- Provide a complete chronological clinical timeline for each patient.

Completed:
- Patient clinical history backend.
- Unified clinical history timeline.
- Timeline integration for:
  - consultations
  - exams/results
  - preventive care records
  - file references
  - follow-ups
- User traceability in timeline records where available.
- Patient detail sections for:
  - complete history
  - information
  - vaccines and deworming
  - file attachments
- Timeline filtering by type.
- PDF export of clinical history with filters.
- Clinic branding integrated in clinical history PDF.

### 🟡 In Progress - Slice 4 - Structured Consultations

Goal:
- Make consultations the main structured clinical workflow.

Completed:
- Full consultation CRUD.
- Stepper consultation flow.
- Draft persistence.
- Step save flow.
- Completed consultation state.
- Medication support.
- Study requests.
- Clinical history integration.
- Consultation detail/edit flow.
- Safe consultation delete.
- Consultation medication to inventory integration in the backend.
- Inventory-backed therapeutic plan support in the backend.
- Backend stock validation and automatic inventory exit movement creation for inventory-backed medications.

Pending:
- Frontend therapeutic plan inventory selector integration.
- Stock validation and stock deduction feedback in the consultation UI.
- User-facing visual flow for automatic stock deduction from therapeutic plan medication use.

### ✅ Completed - Slice 5 - Exams and Results

Goal:
- Request exams, register results, and connect them to clinical history.

Completed:
- Exams CRUD v1.
- Text-based result registration/editing.
- Exams associated with patients.
- Exams can be associated with consultations.
- Frontend exams view and detail flow.
- Exams integrated into clinical history.

### ✅ Completed - Slice 6 - Global Search

Goal:
- Provide fast access to owners and patients.

Completed:
- Tenant-aware backend search.
- Frontend search experience.
- Search by owner name.
- Search by owner phone/contact reference.
- Search by patient name.
- Navigation from search results.

### ✅ Completed - Slice 7 - Preventive Care

Goal:
- Track vaccines, deworming, and other preventive care records.

Completed:
- Preventive care backend records.
- Preventive care frontend creation flow.
- List, create, edit, and delete flows.
- Safe delete confirmation.
- Clinical history timeline integration.
- User traceability.

### ✅ Completed - Slice 8 - Clinical Files

Goal:
- Store clinical files securely and keep file references connected to patient history.

Completed:
- Patient file references.
- File uploads to Google Cloud Storage.
- Storage metadata persistence.
- Signed download URLs.
- Delete with storage cleanup.
- Tenant/patient file association.
- Clinical history timeline integration.
- User traceability.
- File type and size validation.

### ✅ Completed - Slice 9 - Agenda / Appointments

Goal:
- Schedule clinic appointments and assign them to team members.

Completed:
- Appointment CRUD.
- Assignment by veterinarian/team member.
- Date, patient, owner, status, type, and assigned-user filters.
- Clinic team integration.
- Frontend agenda list/detail flow.

### ✅ Completed - Slice 10 - Follow-ups

Goal:
- Track clinical follow-ups and connect them to patient workflows.

Completed:
- Follow-up CRUD.
- Follow-up status updates.
- Cancel and complete flows.
- Optional appointment creation.
- Assignment by veterinarian/team member.
- Patient/owner/date/status/type filters.
- Clinical history integration.

### ✅ Completed - Slice 11 - Dashboard

Goal:
- Show operational clinic metrics using real application data.

Completed:
- Real dashboard backend.
- Real dashboard frontend.
- Operational metrics for appointments, follow-ups, consultations, and current clinic activity.
- Dashboard filters for date range, assigned user, and completed records.

### ✅ Completed - Slice 12 - Clinic Profile

Goal:
- Let each clinic manage visible clinic identity and team context.

Completed:
- Clinic profile endpoint and frontend screen.
- Clinic team listing.
- Clinic branding fields.
- Clinic logo upload to storage.
- Clinic logo delete flow.
- Clinic branding consumed by clinical history PDF export.

### ✅ Completed - Slice 13 - Inventory (MVP Core)

Goal:
- Track clinic inventory and medication stock for MVP operations.

Completed:
- Inventory backend CRUD.
- Inventory item create, list, detail, edit, and deactivate/delete flows.
- Inventory summary.
- Inventory alerts for low stock, expiring soon, and expired items.
- Stock entry registration.
- Stock exit registration.
- Inventory movement history.
- Tenant-aware inventory filtering.
- Inventory frontend module:
  - list
  - summary
  - create
  - detail
  - edit
  - deactivate
  - movement registration
  - movement history

## Next Priorities

### ⏳ Next - Priority 1 - Consultation Therapeutic Plan Inventory Frontend

Goal:
- Complete the user-facing consultation flow for inventory-backed therapeutic plan medications.

Includes:
- Inventory medication selector.
- Stock validation in the consultation UI.
- Automatic stock deduction visual flow.
- Clear feedback when stock changes or is insufficient.

### 🔵 Planned - Priority 2 - Prescriptions Module

Goal:
- Generate prescriptions from clinical work.

Includes:
- Prescription generation.
- Printable/exportable prescription.
- Consultation integration.

### 🔵 Planned - Priority 3 - Notifications / Reminders

Goal:
- Turn follow-up and preventive care dates into user-facing reminders.

Includes:
- Follow-up reminders.
- Vaccine reminders.
- Appointment reminders.

### 🔵 Planned - Priority 4 - Advanced Settings / Clinic Administration

Goal:
- Harden clinic administration for real multi-user clinic operations.

Includes:
- User invitation flow.
- Role management.
- Clinic settings hardening.

### 🔵 Planned - Priority 5 - Hardening / Pilot Stabilization

Goal:
- Stabilize the MVP for pilot usage.

Includes:
- UX polish.
- Bug fixes.
- Edge cases.
- Better validations.
- Broader frontend and backend test coverage.
- Accessibility review.
- Production observability and operational checklist.
- Pilot release checklist.

## Post-MVP

### ⚪ Deferred

- Native mobile app.
- Advanced analytics.
- Financial reporting.
- Supplier module.
- Purchase orders.
- Barcode scanning.
- Advanced inventory valuation.
- WhatsApp notifications.
- Google Calendar sync.

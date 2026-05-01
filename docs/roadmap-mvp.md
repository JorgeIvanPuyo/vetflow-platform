# MVP Roadmap

## Development Strategy
The MVP is being built through vertical slices. Each slice should remain useful end-to-end, but the roadmap now reflects the real current state of the platform rather than the original plan only.

Status labels:
- ✅ Completed
- 🟡 Partial
- ⏳ Pending
- 🔜 Next Priority
- 🧊 Deferred

## MVP Status By Slice

### ✅ Completed - Slice 0 - Project Foundation
Goal:
- Establish the technical foundation for local development, deployment, documentation, and database evolution.

Completed:
- Monorepo configured.
- Backend FastAPI application implemented.
- Frontend Next.js application implemented.
- Base Codex guidance documentation created.
- Local Docker environment available.
- Local and remote PostgreSQL support available.
- Supabase configured as the current production database.
- Alembic configured for migrations.
- Backend CI/CD configured.
- Backend deployed to Cloud Run.
- Frontend deployed to Vercel.

### ✅ Completed - Slice 1 - Multi-Tenant Foundation
Goal:
- Support pilot clinics with strict tenant isolation and real authentication.

Completed:
- Tenant model implemented.
- User model implemented.
- Tenant represents the clinic/organization.
- Multiple veterinarians can belong to the same tenant.
- Multi-tenancy implemented with `tenant_id`.
- Firebase Authentication integrated.
- Real tenant resolution from the authenticated user.
- Frontend and backend authentication with Bearer tokens.
- Temporary frontend `X-Tenant-Id` dependency removed from normal authenticated flows.
- 3 pilot users can be supported manually through Firebase Auth and Supabase users.
- Patients, owners, consultations, exams, preventive care, and file references are shared within the clinic.
- User traceability implemented across clinical records.

### ✅ Completed - Slice 2 - Owners and Patients
Goal:
- Provide complete owner and patient management with tenant-aware data isolation.

Completed:
- Full CRUD for owners.
- Full CRUD for patients.
- Owner-patient relationship implemented.
- Owner detail view implemented.
- Patient detail view implemented.
- Safe owner creation, editing, and deletion flows.
- Safe patient creation, editing, and deletion flows.
- Controlled cascade deletion for dependent clinical data.
- Mobile-first UI/UX improvements for owners and patients.
- Allergy and relevant chronic condition alerts.

### ✅ Completed - Slice 3 - Clinical History
Goal:
- Provide a chronological clinical timeline for each patient.

Completed:
- Basic clinical history implemented.
- Patient clinical timeline implemented.
- Timeline integrates consultations, exams, preventive care records, and file references.
- Timeline includes user traceability where available:
  - Created by.
  - Attended by.
  - Requested by.
- Basic timeline filtering by type.
- Patient detail page includes these sections:
  - Complete history.
  - Information.
  - Vaccines and deworming.
  - File attachments.

### ✅ Completed - Slice 4 - Structured Consultations
Goal:
- Make consultations the main structured clinical workflow.

Completed:
- Full consultation CRUD.
- Multi-step workflow backend.
- Multi-step frontend.
- Draft status.
- Completed status.
- Progressive autosave.
- Medication entries.
- Study requests.
- Safe consultation delete.
- Clinical history integration.
- Consultation detail/edit flow.

### ✅ Completed - Slice 5 - Exams and Results
Goal:
- Request exams, register text results, and connect them to clinical history.

Completed:
- Exams v1 implemented.
- Text-based results implemented.
- Exams associated with patients and consultations.
- Frontend exams view implemented.
- Result editing implemented.
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

### 🟡 Partial - Slice 7 - Hardening
Goal:
- Stabilize the MVP for pilot usage.

Already exists:
- Mobile-first UI.
- Initial design system.
- Login UI.
- Mobile menu.
- Bottom navigation.
- Public deployment is functional.
- End-to-end deployment path is working: Vercel → Cloud Run → Supabase.

Pending:
- Broader validation pass across edge cases.
- Additional frontend and backend test coverage.
- Accessibility review.
- Production observability and operational checklist.
- Pilot release checklist.

## Partial Clinical Submodules

### ✅ Completed - Preventive Care
Scope:
- Vaccines, deworming, and other preventive care records.

Completed:
- Persistent backend support.
- Frontend creation flow.
- List view.
- Create preventive care records.
- Edit preventive care records.
- Delete preventive care records.
- Safe delete confirmation.
- Clinical history timeline integration.
- User traceability.

Deferred:
- Future reminder or next-dose workflow.

### 🟡 Partial - File Attachments
Scope:
- Patient file references and future real file uploads.

Already exists:
- File reference metadata without real upload.
- Patient association.
- Clinical history integration.
- User traceability.

Pending:
- Real uploads.
- Storage provider decision: S3, Firebase Storage, or Google Cloud Storage.
- Secure tenant/patient file linking.
- File preview.
- File download.
- Storage integration.
- File type and size controls.

## Next Priority Slices

### 🔜 Next Priority - Priority 1 - Real File Uploads
Objective:
- Allow real clinical document uploads.

Tasks:
- Define storage provider: S3, Firebase Storage, or Google Cloud Storage.
- Design tenant/patient storage structure.
- Upload PDFs and images.
- Store metadata in `patient_file_references`.
- Allow file preview/download.
- Maintain tenant-aware security.

Suggested storage structure:
- `tenant_id/patients/patient_id/files/file_id/filename`

### 🔜 Next Priority - Priority 2 - Clinical History PDF Export
Objective:
- Allow downloading patient clinical history as a professional PDF with configurable detail.

Tasks:
- Add a simple export selector.
- Add date range filters.
- Add include/exclude options for:
  - Consultations.
  - Exams.
  - Vaccines/deworming.
  - Files/references.
  - Owner data.
  - Complete patient data.
- Generate a readable professional PDF.
- Support summarized and complete clinical history exports.

### 🔜 Next Priority - Priority 3 - Agenda / Scheduling
Objective:
- Add appointment scheduling for clinic workflows.

Tasks:
- Define MVP appointment model.
- Create appointment list/calendar view.
- Link appointments to owners/patients where applicable.
- Maintain tenant-aware access.

### 🔜 Next Priority - Priority 4 - Inventory / Medication Stock
Objective:
- Track medication and inventory stock for clinic operations.

Tasks:
- Define MVP inventory item model.
- Track medication stock.
- Register stock movements.
- Maintain tenant-aware access.

## Post-MVP / Deferred

### 🧊 Deferred
- Advanced settings.
- Roles and permissions.
- Internal user management.
- Advanced dashboard.
- Reports.
- Reminders.
- Prescriptions.
- Native mobile app.

## Current Development Position
The app is already deployed and connected end-to-end through Vercel, Cloud Run, and Supabase.

It already supports authenticated Firebase users, real multi-tenant tenant resolution, and tenant-aware access to owners, patients, clinical history, structured consultations, exams v1, preventive care, and file references.

The current model supports a multi-veterinarian clinic workflow: Tenant represents the clinic, multiple veterinarians can belong to the same tenant, and patients are shared within the clinic while tenant isolation remains enforced.

Structured consultations are completed, preventive care is completed, and user traceability is available across patient, consultation, exam, preventive care, file reference, and clinical history timeline records.

The next development focus should be implementing real file uploads, adding clinical history PDF export, and then expanding into agenda/scheduling and inventory/medication stock.

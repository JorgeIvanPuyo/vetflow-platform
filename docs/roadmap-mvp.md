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
- Multi-tenancy implemented with `tenant_id`.
- Firebase Authentication integrated.
- Real tenant resolution from the authenticated user.
- Frontend and backend authentication with Bearer tokens.
- Temporary frontend `X-Tenant-Id` dependency removed from normal authenticated flows.
- 3 pilot users can be supported manually through Firebase Auth and Supabase users.

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
- Basic timeline filtering by type.
- Patient detail page includes these sections:
  - Complete history.
  - Information.
  - Vaccines and deworming.
  - File attachments.

### 🟡 Partial - Slice 4 - Structured Consultations
Goal:
- Make consultations the main structured clinical workflow.

Already exists:
- Base consultations backend.
- Base consultations frontend.
- Consultation creation.
- Basic consultation editing.
- Clinical history integration.

Pending:
- Refine complete consultation CRUD in backend/frontend if any edge cases remain.
- Improve the consultations frontend module.
- Add safe confirmation before deleting a consultation.
- Improve the clinical workflow for:
  - Anamnesis.
  - Clinical exam.
  - Presumptive diagnosis.
  - Diagnostic plan.
  - Therapeutic plan.
  - Final diagnosis.
  - Indications.
- Improve consultation visualization in patient detail and consultation detail views.

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

### 🟡 Partial - Preventive Care
Scope:
- Vaccines, deworming, and other preventive care records.

Already exists:
- Persistent backend support.
- Frontend creation flow.
- List view.
- Clinical history integration.

Pending:
- Edit preventive care record.
- Delete preventive care record with confirmation.
- Improve module UX.
- Future reminder or next-dose workflow.

### 🟡 Partial - File Attachments
Scope:
- Patient file references and future real file uploads.

Already exists:
- File reference metadata without real upload.
- Patient association.
- Clinical history integration.

Pending:
- Real PDF/image upload.
- Storage provider decision: S3, Firebase Storage, or Google Cloud Storage.
- Secure tenant/patient file linking.
- File visualization and download.
- File type and size controls.

## Next Priority Slices

### 🔜 Next Priority - Priority 1 - Consultations Complete CRUD
Objective:
- Complete consultations as the main clinical module.

Tasks:
- Create, edit, and delete consultations reliably.
- Add safe confirmation before deletion.
- Improve the mobile-first consultation UI.
- Refine clinical forms.
- Improve consultation detail view.
- Maintain clinical history integration.

### 🔜 Next Priority - Priority 2 - Preventive Care Complete CRUD
Objective:
- Complete vaccines and deworming workflows.

Tasks:
- Edit preventive care records.
- Delete preventive care records.
- Add safe confirmation before deletion.
- Improve cards and list views.
- Maintain timeline integration.

### 🔜 Next Priority - Priority 3 - Real File Uploads
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

### 🔜 Next Priority - Priority 4 - Clinical History PDF Export
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

## Post-MVP / Deferred

### 🧊 Deferred
- Agenda / scheduling.
- Inventory.
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

It already supports authenticated Firebase users, real multi-tenant tenant resolution, and tenant-aware access to owners, patients, clinical history, consultations v1, exams v1, preventive care v1, and file references.

The next development focus should be completing consultations, completing preventive care CRUD, implementing real file uploads, and adding clinical history PDF export.

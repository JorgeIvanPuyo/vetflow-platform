# API Contracts

## Objective
Define the initial API surface for Vetflow Platform so frontend and backend can evolve consistently.

## General Rules
- All business endpoints are tenant-aware.
- All authenticated requests must resolve tenant context.
- JSON request/response format unless an endpoint explicitly returns a binary file.
- Use predictable error responses.
- Use REST-style resource naming.

## Base API Prefix
`/api/v1`

## Initial MVP Resources
- tenants
- users
- owners
- patients
- consultations
- exams
- exam-results
- clinical-history
- clinic
- inventory
- search

## Authentication
Initial MVP can start with a simplified auth approach, but all protected endpoints must assume an authenticated user with tenant context.

## Standard Response Shape
Successful read example:
{
  "data": {},
  "meta": {}
}

Successful list example:
{
  "data": [],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 0
  }
}

Error example:
{
  "error": {
    "code": "resource_not_found",
    "message": "Patient not found"
  }
}

## Owners
POST /api/v1/owners
GET /api/v1/owners
GET /api/v1/owners/{owner_id}
PATCH /api/v1/owners/{owner_id}

The owners list accepts optional `search`, `phone`, `page`, and `page_size`
parameters. Pagination is applied when `page_size` is provided; omitting it keeps
the existing unpaginated behavior for backward-compatible selector flows.

## Patients
POST /api/v1/patients
GET /api/v1/patients
GET /api/v1/patients/{patient_id}
PATCH /api/v1/patients/{patient_id}

The patients list accepts optional `owner_id`, `species`, `search`, `page`, and
`page_size` parameters. Pagination is applied when `page_size` is provided;
omitting it keeps the existing unpaginated behavior for backward-compatible
selector and owner-detail flows.

### Clinical history PDF

Both endpoints accept the same filters and section flags, including:

- optional `date_from` and `date_to`
- `include_patient_data`, `include_owner_data`, `include_consultations`,
  `include_exams`, `include_preventive_care`, and `include_file_references`
- `detail_level`: `summary` or `full`
- `page_size`: `letter`, `a4`, or `legal` (default: `letter`)

Endpoints:

- `POST /api/v1/patients/{patient_id}/clinical-history/export-pdf`
  returns `application/pdf` with `Content-Disposition: attachment`.
- `POST /api/v1/patients/{patient_id}/clinical-history/preview-pdf`
  returns the same generated PDF with `Content-Disposition: inline`.

Export and preview use the same tenant-scoped report generation service.

## Consultations
POST /api/v1/consultations
GET /api/v1/consultations
GET /api/v1/patients/{patient_id}/consultations
GET /api/v1/consultations/{consultation_id}
PATCH /api/v1/consultations/{consultation_id}
PATCH /api/v1/consultations/{consultation_id}/step

The tenant-wide consultations list accepts `page` (default `1`), `page_size`
(default `12`, maximum `100`), optional `search`, and optional `status` (`draft`
or `completed`). Search matches patient name, owner name, or consultation reason.
Results are ordered by `visit_date` descending and return lightweight patient,
owner, veterinarian, status, reason, and diagnosis references.

Consultation traceability distinguishes:

- `created_by_user_id`: authenticated user who created or registered the consultation.
- `attending_user_id`: veterinarian clinically responsible for the consultation.

`POST`, `PATCH`, and step `PATCH` accept `attending_user_id`. On create, omission
defaults it to the authenticated user. Updates may change it, but explicit `null`
is rejected with `422`. A supplied value must identify an active user in the same
tenant; unknown, inactive, and cross-tenant values return `404 team_member_not_found`.

## Exams
POST /api/v1/exams
GET /api/v1/patients/{patient_id}/exams
POST /api/v1/exams/{exam_id}/results

## Search
GET /api/v1/search?q=...

## Clinic team

- `GET /api/v1/clinic/team`
- `PATCH /api/v1/clinic/team/{user_id}`

The team-member update payload accepts only `full_name`. This flow does not edit
the member id, email, tenant, or active state. Only an active member in the
authenticated tenant can be updated; otherwise the API returns
`404 team_member_not_found`.

## Inventory tax fields

Inventory item create/update supports separate purchase and sale tax rates:

- `purchase_tax_rate_percentage`
- `sale_tax_rate_percentage`

Both default to `0` for backward compatibility and are validated from 0 to 100.
Inventory responses expose `purchase_tax_amount_ars`,
`purchase_price_with_tax_ars`, `sale_tax_amount_ars`, and
`sale_price_with_tax_ars`.

## Tenant Rule
Every business response must belong only to the authenticated tenant.
No cross-tenant access is allowed.

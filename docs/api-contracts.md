# API Contracts

## Objective
Define the initial API surface for Vetflow Platform so frontend and backend can evolve consistently.

## General Rules
- All business endpoints are tenant-aware.
- All authenticated requests must resolve tenant context.
- JSON request/response format only.
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

## Patients
POST /api/v1/patients
GET /api/v1/patients
GET /api/v1/patients/{patient_id}
PATCH /api/v1/patients/{patient_id}

## Consultations
POST /api/v1/consultations
GET /api/v1/patients/{patient_id}/consultations
GET /api/v1/consultations/{consultation_id}
PATCH /api/v1/consultations/{consultation_id}

## Exams
POST /api/v1/exams
GET /api/v1/patients/{patient_id}/exams
POST /api/v1/exams/{exam_id}/results

## Search
GET /api/v1/search?q=...

## Tenant Rule
Every business response must belong only to the authenticated tenant.
No cross-tenant access is allowed.

# Backend Conventions

## Stack
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Pydantic
- Pytest

## Backend Goals
The backend must be:
- modular
- tenant-aware
- testable
- explicit
- easy to evolve feature by feature

## Suggested Folder Structure
```text
apps/api/
├─ app/
│  ├─ main.py
│  ├─ core/
│  ├─ api/
│  ├─ models/
│  ├─ schemas/
│  ├─ services/
│  ├─ repositories/
│  ├─ db/
│  └─ tests/
├─ alembic/
├─ alembic.ini
├─ requirements.txt
├─ Dockerfile
└─ .env.example
```

## Layer Responsibilities

### API Layer
Responsible for:
- route definitions
- request/response handling
- dependency injection
- status codes
- transport validation

Must NOT contain:
- business rules
- persistence logic

### Service Layer
Responsible for:
- business rules
- workflow orchestration
- tenant-aware operations
- validation beyond transport schema

### Repository Layer
Responsible for:
- database access
- queries
- tenant filtering
- persistence details

### Schema Layer
Responsible for:
- Pydantic request/response schemas
- serialization/deserialization
- input/output contracts

### Model Layer
Responsible for:
- SQLAlchemy models
- relationships
- DB structure mapping

## Core Rules
1. Every tenant-owned entity must include `tenant_id`.
2. No repository query may ignore tenant filtering.
3. Business logic must stay out of routes.
4. Routes should remain thin.
5. Schemas and DB models must be separated.
6. Explicit names are preferred over overly generic abstractions.

## API Design Rules
- Use RESTful conventions.
- Keep endpoints resource-oriented.
- Use plural nouns for collections.
- Return predictable response structures.
- Validate request data strictly.
- Return meaningful error messages.

## Error Handling
- Use structured error responses.
- Do not leak raw internal exceptions.
- Distinguish validation errors, not found errors, authorization errors, and business rule violations.

## Validation
- Validate all external input through Pydantic schemas.
- Validate business invariants in services.
- Avoid relying only on DB constraints for business behavior.

## Testing
At minimum, test:
- service logic
- critical API endpoints
- tenant isolation
- main negative cases

## Migrations
- Use Alembic for schema evolution.
- Do not modify production schemas manually.
- Every DB model change must be reflected in a migration.

## Tenant Awareness
Tenant context must be resolved before accessing business data.
Every service and repository handling tenant-owned resources must receive tenant context explicitly or through a well-defined dependency.

## Naming
- Use clear nouns for models and schemas.
- Use verb-based names for service methods.
- Avoid abbreviations unless universally understood.

## Simplicity Rule
Do not build generic frameworks inside the codebase.
Prefer a straightforward and boring implementation that is easy to maintain.

# Multitenancy Strategy

## Objective
Support multiple veterinary users and future clients from the start, while keeping MVP complexity under control.

## Recommended Strategy
Single database with logical tenant isolation using `tenant_id`.

## Why This Strategy
This approach provides:
- fast MVP delivery
- lower infrastructure complexity
- easier migrations
- simpler operational management
- enough scalability for early-stage growth

## Core Rule
Every business entity that belongs to a customer account must include `tenant_id`.

## Entities That Must Be Tenant-Aware
- users
- owners
- patients
- consultations
- exams
- exam results
- attachments
- future inventory items
- future appointments

## Isolation Principle
No query should return business data without filtering by `tenant_id`.

## Backend Requirements
- tenant context must be resolved on every authenticated request
- service layer must never bypass tenant scoping
- repository/data access layer must apply tenant filters consistently

## Frontend Requirements
- session context must include active tenant
- no cross-tenant switching in MVP unless explicitly designed
- all data fetching must operate under authenticated tenant context

## MVP Assumption
Initial release will support 3 pilot users. The architecture must assume future onboarding of multiple veterinary clients without requiring a full redesign.

## Future Evolution
Potential future improvements:
- tenant-specific branding
- multi-user teams inside a tenant
- role-based permissions
- usage plans and billing
- custom domains

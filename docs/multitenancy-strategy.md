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
- inventory items and movements
- appointments and follow-ups

## Isolation Principle
No query should return business data without filtering by `tenant_id`.

## Backend Requirements
- tenant context must be resolved on every authenticated request
- service layer must never bypass tenant scoping
- repository/data access layer must apply tenant filters consistently
- a consultation `attending_user_id` must reference an active user in the same tenant
- clinical history PDF export and preview must resolve patients and report data only
  within the authenticated tenant

## Frontend Requirements
- session context must include active tenant
- no cross-tenant switching in MVP unless explicitly designed
- all data fetching must operate under authenticated tenant context

## MVP Assumption
Initial release will support 3 pilot users. The architecture must assume future onboarding of multiple veterinary clients without requiring a full redesign.

## Current Team and Branding Rules

- Multiple active users can belong to one tenant and share clinic data.
- Clinic branding is tenant-specific and may be used in generated clinical reports.
- Team display-name edits and responsible-veterinarian assignments are restricted
  to users in the authenticated tenant.

## Future Evolution
Potential future improvements:
- role-based permissions
- usage plans and billing
- custom domains

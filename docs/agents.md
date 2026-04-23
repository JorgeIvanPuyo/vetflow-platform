# Codex Working Rules

## Objective
Codex must implement the project incrementally, safely, and consistently with the architecture and product scope.

## General Principles
1. Do not invent scope outside documented requirements.
2. Follow the MVP roadmap strictly.
3. Work feature by feature using vertical slices.
4. Prefer simple and maintainable solutions over premature complexity.
5. Keep multi-tenancy in mind in every data model and API flow.

## Mandatory Order of Work
1. Read:
   - `README.md`
   - `docs/product-scope.md`
   - `docs/roadmap-mvp.md`
   - `docs/architecture-overview.md`
   - `docs/multitenancy-strategy.md`
2. Implement only the current agreed slice.
3. Ensure local run works.
4. Add or update tests where applicable.
5. Do not modify unrelated modules.
6. Document any important architectural decision.

## Coding Principles
- Keep modules small and focused.
- Prefer explicit naming.
- Avoid hidden coupling.
- Avoid dead code and speculative abstractions.
- Do not implement postponed modules unless requested.

## Backend Rules
- All tenant-owned entities must include `tenant_id`.
- Validate all request payloads strictly.
- Keep business rules out of transport/controller layers.
- Use modular structure and clear separation of responsibilities.
- Avoid writing queries without tenant filters.

## Frontend Rules
- Mobile-first responsive UI.
- Keep components reusable but not over-abstracted.
- Feature-first organization is preferred.
- Prioritize usability and speed for clinical workflows.
- Search and patient access should remain frictionless.

## Delivery Rules
For each slice:
- code must run locally
- tests must pass
- docs must remain aligned with the implementation
- commit scope must be focused and understandable

## Forbidden Behaviors
- Do not redesign the architecture without justification.
- Do not mix MVP scope with post-MVP scope.
- Do not add unnecessary libraries.
- Do not skip tenant-awareness in any business module.
- Do not implement incomplete flows without clearly stating limitations.
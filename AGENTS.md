# AGENTS.md - Codex navigation map

Vetflow is a multi-tenant veterinary clinic platform. The monorepo has a FastAPI backend in `apps/api`, a Next.js frontend in `apps/web`, and canonical project documentation in `docs/`.

## Start Here

1. Read this file.
2. Read `docs/agents.md`.
3. Read only the docs and modules needed for the current slice.

Do not scan the whole repository or all documentation automatically. Keep the slice small, vertical, and focused.

## Mandatory Rules

- Work on a branch, never directly on `main`.
- Before editing, check Git state and compare against `main` when the slice may overlap recent work.
- Respect changes from other collaborators; do not overwrite unrelated work.
- Do not push, merge, commit, or deploy unless the user explicitly asks.
- Backend dependencies are managed only with `uv` from `apps/api/pyproject.toml` and `apps/api/uv.lock`.
- Web dependencies are managed only with `pnpm` from `apps/web/package.json` and `apps/web/pnpm-lock.yaml`.
- For tenant-owned data, always filter by `tenant_id`; cross-tenant endpoints must be explicitly protected.
- Review Alembic migrations before changing persistence.
- Run focused tests first, then broader validation when risk or slice closure requires it.
- Update relevant status/task documentation before closing an iteration.
- Stop any local processes or containers started during the session.

## Canonical Docs

- Assisted workflow: `docs/agents.md`
- Product scope: `docs/product-scope.md`
- Architecture: `docs/architecture-overview.md`
- Backend conventions: `docs/backend-conventions.md`
- Frontend conventions: `docs/frontend-conventions.md`
- API contracts: `docs/api-contracts.md`
- Multi-tenancy: `docs/multitenancy-strategy.md`
- CI/CD: `docs/cicd-strategy.md`

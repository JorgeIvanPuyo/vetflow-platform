# Assisted Development Workflow

This is the shared operating guide for Codex, Claude, and any other AI assistant working on Vetflow. Root files (`AGENTS.md` and `CLAUDE.md`) are short maps; this document is the canonical workflow.

## Repository Shape

- `apps/api`: FastAPI backend, SQLAlchemy models, Alembic migrations, pytest tests.
- `apps/web`: Next.js frontend, TypeScript, Firebase client integration.
- `docs`: product, architecture, conventions, scope, and delivery notes.

Use vertical slices. A change to a domain usually follows the same path across backend and frontend: model/schema/repository/service/router on the API side, and types/service/feature component/page on the web side.

## Before Editing

1. Confirm the branch is not `main`.
2. Run `git status --short`.
3. Compare with `main` when the slice overlaps recent work or when the user asks for branch hygiene.
4. Identify changed files that are not yours and preserve them.
5. Read the root assistant file, this document, and only the docs or modules needed for the slice.

Do not read the full repository by default. Do not redesign recently approved work unless the user explicitly opens that scope.

## Tooling Rules

- Backend dependencies have one source: `apps/api/pyproject.toml` plus `apps/api/uv.lock`.
- Use `uv sync --frozen` for reproducible backend installs.
- Use `uv run ...` for backend commands, tests, and Alembic.
- Production backend images must install without development dependencies.
- Web dependencies have one source: `apps/web/package.json` plus `apps/web/pnpm-lock.yaml`.
- Use `pnpm install --frozen-lockfile` for reproducible web installs.
- Do not add legacy dependency lockfiles, Yarn locks, or duplicate dependency sources.

## Safety Rules

- Never overwrite unrelated user or collaborator changes.
- Keep slices small and avoid opportunistic refactors.
- Do not deploy, merge, push, or commit unless the user explicitly asks.
- Do not use production databases for local validation.
- Do not copy `.env` files, Firebase service account files, or other secrets into images or committed files.
- Stop local servers, background processes, and containers started during the session.

## Architecture Rules

- Every tenant-owned entity must include and query by `tenant_id`.
- Repository queries must filter by `tenant_id`.
- Cross-tenant endpoints are allowed only when explicitly protected, such as superadmin flows.
- Keep business logic out of FastAPI routers.
- Keep persistence changes paired with reviewed Alembic migrations.
- Check existing migrations before modifying models or schema.
- Preserve API response envelopes and frontend API types.

## Validation Rules

Run the narrowest useful checks first, then broaden as risk increases.

Backend:

```bash
cd apps/api
uv sync --frozen
uv run pytest
```

Docker backend:

```bash
cd apps/api
docker compose config
docker compose build api
docker compose run --rm api pytest
docker compose down
```

Frontend:

```bash
cd apps/web
pnpm install --frozen-lockfile
pnpm exec tsc --noEmit
pnpm run lint
pnpm run build
```

Use the full suite when the slice touches shared behavior, contracts, persistence, auth, tenant isolation, CI/CD, or when closing a release-quality iteration.

## Documentation Rules

Update documentation that the slice makes stale. For delivery/status iterations, update the relevant roadmap, backlog, or status document before closing. Do not rewrite unrelated product documentation.

When documenting local development, use `uv`, `pnpm`, and Docker Compose commands that match the versioned files in the repo.

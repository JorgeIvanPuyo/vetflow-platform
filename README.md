# Vetflow Platform

Vetflow es una aplicación web multi-tenant para gestión clínica veterinaria. Permite administrar clínicas, usuarios, propietarios, pacientes, consultas, exámenes, vacunas/desparasitación, archivos clínicos, agenda, seguimientos, dashboard e inventario.

## Stack

- Frontend: Next.js + TypeScript, desplegado en Vercel.
- Backend: FastAPI + SQLAlchemy + Alembic, desplegado en Google Cloud Run.
- Base de datos: PostgreSQL en Supabase.
- Auth: Firebase Authentication.
- Storage clínico: Google Cloud Storage.
- CI/CD: GitHub Actions.
- Desarrollo asistido: Codex y Claude con reglas compartidas en `AGENTS.md`, `CLAUDE.md` y `docs/agents.md`.

## Fuentes De Dependencias

- Backend: `apps/api/pyproject.toml` + `apps/api/uv.lock`, gestionado solo con `uv`.
- Web: `apps/web/package.json` + `apps/web/pnpm-lock.yaml`, gestionado solo con `pnpm`.

No se usan fuentes duplicadas de dependencias.

## Arquitectura General

```text
Frontend Next.js / Vercel
Firebase Auth
Authorization: Bearer token
Backend FastAPI / Cloud Run
PostgreSQL / Supabase
Google Cloud Storage
```

Todos los datos clínicos tenant-owned se filtran por `tenant_id`. Los endpoints cross-tenant deben estar explícitamente protegidos.

## Estructura

```text
vetflow-platform/
├── apps/
│   ├── api/
│   └── web/
├── docs/
├── .github/
├── AGENTS.md
├── CLAUDE.md
└── README.md
```

## Backend Local

```bash
cd apps/api
cp .env.example .env
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health:

```bash
curl http://localhost:8000/health
```

Docker Compose local:

```bash
cd apps/api
docker compose up --build
docker compose exec api alembic upgrade head
docker compose run --rm api pytest
docker compose down
```

Eliminar el volumen local de Postgres es opcional y explícito:

```bash
docker compose down --volumes
```

## Frontend Local

```bash
cd apps/web
cp .env.example .env.local
pnpm install --frozen-lockfile
pnpm run dev
```

Abrir:

```text
http://localhost:3000
```

Vercel debe usar `apps/web` como root del proyecto y `pnpm` como gestor. El comando de instalación esperado es `pnpm install --frozen-lockfile`.

## Validación

Backend:

```bash
cd apps/api
uv sync --frozen
uv run pytest
```

Frontend:

```bash
cd apps/web
pnpm install --frozen-lockfile
pnpm exec tsc --noEmit
pnpm run lint
pnpm run build
```

## Documentación

- `docs/agents.md`: flujo compartido para asistentes IA.
- `docs/product-scope.md`: alcance de producto.
- `docs/architecture-overview.md`: arquitectura.
- `docs/backend-conventions.md`: convenciones backend.
- `docs/frontend-conventions.md`: convenciones frontend.
- `docs/api-contracts.md`: contratos API.
- `docs/multitenancy-strategy.md`: estrategia multi-tenant.
- `docs/cicd-strategy.md`: CI/CD.

## Deploy

Backend: GitHub Actions ejecuta pruebas con `uv`, construye la imagen Docker, la publica en Artifact Registry y despliega a Cloud Run.

Frontend: Vercel despliega desde `apps/web` usando `pnpm`.

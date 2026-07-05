# CLAUDE.md — Mapa de navegación de Vetflow

App web de gestión clínica veterinaria, **multi-tenant** (tenant = clínica). Monorepo: `apps/api` (FastAPI) + `apps/web` (Next.js). Docs de contexto en `docs/`.

> Propósito de este archivo: mapa para saber **qué tocar y por dónde empezar** sin re-explorar. La regla de oro es **arquitectura por capas espejo** — todo módulo existe como una rebanada vertical idéntica en back y front.

---

## Cómo pensar en este repo: rebanadas verticales

Cada dominio (patients, owners, consultations, exams, inventory, appointments, follow-ups, preventive-care, file-references, clinic, dashboard, search, ai) existe como una **rebanada completa** en ambas capas. Para cambiar/añadir una feature, tocas los mismos eslabones:

**Backend** (`apps/api/app/`), flujo de una request:
```
api/<modulo>.py        → router: define endpoints, DI de tenant + db, arma respuesta {data, meta}
  └ services/<modulo>.py   → lógica de negocio, build_*_response()
      └ repositories/<modulo>.py → queries SQLAlchemy (SIEMPRE filtran por tenant_id)
          └ models/<modulo>.py   → tablas SQLAlchemy
schemas/<modulo>.py    → Pydantic (Create/Update/Response)
```

**Frontend** (`apps/web/src/`):
```
app/<ruta>/page.tsx          → route Next (App Router), casi siempre solo renderiza un <Screen/>
  └ features/<modulo>/components/*.tsx → UI real (screens, detalles, forms, helpers)
      └ services/<modulo>.ts   → llamadas a la API vía `api` client
          └ lib/api.ts         → fetch client (auth Bearer, reintentos, errores)
types/api.ts                 → tipos compartidos de request/response
```

Regla: **para tocar el módulo X, busca `X` en esas rutas.** Los nombres de archivo coinciden entre capas (`patient.py` ↔ `patients.ts`).

---

## Contratos y convenciones clave

- **Prefijo API**: todo bajo `/api/v1` (definido en `core/config.py` → `api_v1_prefix`). Health también en `/health`.
- **Envoltura de respuesta**: los endpoints devuelven `{"data": ..., "meta": ...}`. Listas usan `schemas/common.py::ListMeta`. El front espera `ApiItemResponse<T>` / `ApiListResponse<T>` (ver `types/api.ts`).
- **Errores**: back lanza `core/errors.py::AppError(status_code, code, message)` → JSON `{"error": {code, message}}`. Front los mapea en `lib/api.ts::getApiErrorMessage`.
- **Multi-tenant**: cada endpoint depende de `get_tenant_context` (`core/tenant.py`). TODA query de repositorio filtra por `tenant_id`. Nunca escribir queries sin ese filtro. **Excepción**: el módulo `admin` (usuarios) es cross-tenant a propósito y va protegido por `require_superadmin` (`core/tenant.py`) — nunca exponer datos cross-tenant fuera de endpoints así protegidos.
- **Roles**: `users.role` (`core/roles.py::Role`) con 3 valores: `superadmin` (ve módulo Usuarios), `medico_veterinario` (default, uso clínico), `contador` (ve módulo Contabilidad). Se leen de la BD, NO de Firebase. `TenantContext.role` los transporta. El primer superadmin se asigna manualmente: `UPDATE users SET role='superadmin' WHERE email='...';`. En dev, `get_tenant_context` acepta `X-User-Email` para resolver un usuario real (con rol) sin Firebase.
- **Auth**: front usa Firebase Auth (`lib/firebase.ts`, `features/auth/auth-context.tsx`), manda `Authorization: Bearer <idToken>`. Back valida con firebase-admin (`core/firebase.py`), resuelve `users.email` → `users.tenant_id`.
  - **Fallback dev**: si `APP_ENV=development` y NO hay header `Authorization`, el back acepta el header `X-Tenant-Id: <uuid>` (ver `_resolve_development_tenant`). Útil para probar sin Firebase.
- **Trazabilidad**: consultas/registros guardan `created_by_user_id`; front resuelve nombres con `lib/user-traceability.ts`.

---

## Endpoints por módulo (ver `apps/api/app/api/<modulo>.py`)

| Módulo | Router prefix | Notas |
|---|---|---|
| health | `/health` (+ raíz) | + `debug/db-check` |
| auth | `/auth` | `/me` (usuario actual + rol, leído de BD) |
| admin | `/admin` | `/users` (listar cross-tenant + filtros), `/users/invite` (crea fila + cuenta Firebase), `/tenants` — todo gated por `require_superadmin` |
| owners | `/owners` | CRUD |
| patients | `/patients` | CRUD, `/photo`, `/clinical-history`, `/clinical-history/export-pdf` y `/preview-pdf` |
| consultations | (sin prefix) | `/consultations`, `/patients/{id}/consultations`, `/patients/{id}/clinical-history`, pasos de workflow, `ai-summary` |
| exams | (sin prefix) | `/exams`, `/patients/{id}/exams`, `/consultations/{id}/exams` |
| preventive-care | (sin prefix) | vacunas/desparasitación por paciente |
| file-references | (sin prefix) | archivos clínicos en GCS, `download-url` |
| appointments | `/appointments` | agenda |
| follow-ups | `/follow-ups` | seguimientos, `/complete`, `/cancel` |
| inventory | `/inventory` | `/items`, `/summary`, movimientos `entry`/`exit`, IVA compra/venta |
| clinic | `/clinic` | `/profile`, `/logo`, `/team` (branding y equipo) |
| dashboard | `/dashboard/summary` | métricas operativas |
| search | `/search` | búsqueda global |
| ai | `/ai` | `rewrite-clinical-note`, `generate-consultation-summary` (gated por `AI_FEATURES_ENABLED`) |

## Rutas frontend (`apps/web/src/app/`)
- Nav principal: `/` (dashboard), `/owners`, `/patients`, `/agenda`, `/inventory`, `/settings` (ver `components/layout/navigation-items.ts`). Ítems gateados por rol: `/users` (superadmin), `/accounting` (contador, placeholder "en construcción"). El rol viene de `features/auth/current-user-context.tsx` (`useCurrentUser` → `/auth/me`); la nav se filtra con `filterNavigationByRole`.
- **Alias/legacy**: `/inventario` y `/ajustes` → `redirect()` a `/inventory` y `/settings`. `/follow-ups` renderiza `AgendaScreen` con tab `follow_ups`.
- Detalles dinámicos: `/patients/[id]`, `/owners/[id]`, `/consultations/[id]`, `/exams/[id]`, `/agenda/[id]`, `/follow-ups/[id]`, `/inventory/[id]`, `/inventory/new`, `/patients/[id]/consultations/new`.

---

## Correr localmente (NO ejecutado aún — faltan .env, venv, node_modules)

- **DB**: `cd apps/api && docker compose up -d db` (Postgres 15 en :5432, user/pass/db = `vetflow`). El servicio `api` de compose monta `firebase-service-account.json` que no existe → correr el API fuera de Docker.
- **API** (gestionado con **uv**, ver `pyproject.toml`): crear `apps/api/.env` desde `.env.example` (dejar Firebase vacío para usar fallback dev). Luego, desde `apps/api`:
  `uv sync` (crea `.venv` e instala deps + grupo `dev` con pytest/httpx)
  `uv run alembic upgrade head` (migraciones en `alembic/versions/`, 10 revisiones)
  `uv run uvicorn app.main:app --reload --port 8000`
  - `requirements.txt` sigue existiendo **solo** para el `Dockerfile`/Cloud Run; al cambiar deps, actualizar **ambos** (`pyproject.toml` y `requirements.txt`).
- **Web**: crear `apps/web/.env.local` desde `.env.example` (`NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`). `npm install && npm run dev` (:3000). CORS del back ya permite localhost:3000.
- Firebase real es necesario para login en el front; sin él, usar el fallback `X-Tenant-Id` probando la API directo.

## Tests
- Backend: `pytest` desde `apps/api`. Usan **SQLite in-memory** (`tests/conftest.py`), crean `Base.metadata`, overridean `get_db` y fixtures de `tenant`. No requieren Postgres ni Firebase.
- No hay tests de frontend configurados.

## Stack / deploy
- Front: Next.js 14 (App Router) + TS + Firebase SDK + lucide-react → Vercel (root `apps/web`).
- Back: FastAPI + SQLAlchemy 2.0 + Alembic + psycopg2 + reportlab (PDF) + google-cloud-storage → Cloud Run.
- DB: Postgres (Supabase en prod). Storage clínico: GCS. CI/CD: GitHub Actions.

## Al añadir un módulo nuevo (checklist)
1. Back: `models/` → `schemas/` → `repositories/` (filtrar tenant_id) → `services/` → `api/` router.
2. Registrar router en `app/main.py` (dentro de `api_v1_router`).
3. Migración Alembic nueva en `alembic/versions/` + `alembic upgrade head`.
4. Front: `types/api.ts` → `services/<modulo>.ts` → `features/<modulo>/components/` → `app/<ruta>/page.tsx`.
5. Si va en el menú, agregar a `components/layout/navigation-items.ts`.
6. Tests en `apps/api/app/tests/test_<modulo>.py`.

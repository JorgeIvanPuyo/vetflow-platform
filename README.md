
# Vetflow Platform

Vetflow es una aplicación web para gestión clínica veterinaria. Permite
administrar clínicas, veterinarios, propietarios, pacientes, consultas,
exámenes, vacunas/desparasitación, archivos clínicos e historia clínica.

## Stack principal

-   Frontend: Next.js + TypeScript
-   Backend: FastAPI + SQLAlchemy + Alembic
-   Base de datos: PostgreSQL en Supabase
-   Auth: Firebase Authentication
-   Storage clínico: Google Cloud Storage
-   Backend deploy: Google Cloud Run
-   Frontend deploy: Vercel
-   CI/CD: GitHub Actions
-   Desarrollo asistido: Codex

## Arquitectura general

Frontend Next.js / Vercel\
↓ Firebase Auth\
↓ Authorization: Bearer token\
Backend FastAPI / Cloud Run\
↓ valida token Firebase\
↓ resuelve usuario y tenant\
PostgreSQL / Supabase\
↓ metadata\
Google Cloud Storage\
↓ archivos clínicos

## Multi-tenant

Modelo:

-   Tenant = Clínica / Organización
-   User = Veterinario / Usuario

Varios veterinarios pueden pertenecer a la misma clínica y ver los
mismos pacientes, propietarios e historia clínica.

Relación:

Firebase user email\
→ users.email en Supabase\
→ users.tenant_id\
→ acceso a datos del tenant

Todos los datos clínicos se filtran por tenant_id.

## Módulos implementados

-   Autenticación con Firebase
-   Multi-tenant por clínica
-   CRUD de propietarios
-   CRUD de pacientes
-   Historia clínica por paciente
-   Consultas estructuradas
-   Exámenes y resultados
-   Vacunas/desparasitación
-   Archivos clínicos con Google Cloud Storage
-   Búsqueda global
-   Trazabilidad de usuario

## Estructura del proyecto

vetflow-platform/\
├── apps/\
│ ├── api/\
│ └── web/\
├── docs/\
├── .github/\
└── README.md

## Backend local

Entrar a:

cd apps/api

Crear `.env`:

APP_ENV=development\
APP_PORT=8000

DATABASE_URL=postgresql://...

FIREBASE_PROJECT_ID=vetflow-platform\
FIREBASE_SERVICE_ACCOUNT_JSON_PATH=/app/firebase-service-account.json\
GOOGLE_APPLICATION_CREDENTIALS=/app/firebase-service-account.json

CLINICAL_FILES_BUCKET_NAME=vetflow-clinical-files-prod\
MAX_CLINICAL_FILE_SIZE_MB=25

Levantar:

docker compose up --build

Migraciones:

docker compose exec api alembic upgrade head

Health:

curl http://localhost:8000/health

## Frontend local

Entrar a:

cd apps/web

Crear `.env.local`:

NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

NEXT_PUBLIC_FIREBASE_API_KEY=\
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=\
NEXT_PUBLIC_FIREBASE_PROJECT_ID=\
NEXT_PUBLIC_FIREBASE_APP_ID=\
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=\
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=

Instalar:

npm install

Correr:

npm run dev

Abrir:

http://localhost:3000

## Tests

Backend:

docker compose run --rm api pytest

Frontend:

npm run build

## Base de datos

PostgreSQL en Supabase.

Migraciones:

alembic upgrade head

## Usuarios y clínicas

Flujo:

1.  Crear usuario en Firebase.
2.  Crear clínica en tenants.
3.  Crear usuario en users.
4.  Asociar tenant_id.

## Storage clínico

Bucket:

vetflow-clinical-files-prod

Estructura:

tenants/{tenant_id}/patients/{patient_id}/files/{file_reference_id}/{filename}

Bucket privado.

Descarga mediante signed URLs.

## Deploy

### Backend

GitHub Actions:

-   tests
-   build Docker
-   push Artifact Registry
-   deploy Cloud Run

### Frontend

Vercel.

Root:

apps/web

## Documentación

docs/

-   agents.md
-   api-contracts.md
-   architecture-overview.md
-   backend-conventions.md
-   frontend-conventions.md
-   multitenancy-strategy.md
-   mvp-development-plan.md
-   roadmap-mvp.md
-   clinical-file-storage-architecture.md

## Desarrollo con Codex

Flujo:

1.  Definir slice.
2.  Crear prompt.
3.  Backend primero.
4.  Tests.
5.  Frontend.
6.  Validación manual.
7.  Commit.
8.  Push.
9.  Deploy.

## Estado actual

Desplegado y funcional:

-   Frontend Vercel
-   Backend Cloud Run
-   DB Supabase
-   Auth Firebase
-   Storage GCS
-   Multi-tenant por clínica
-   CI/CD automático

## Próximas prioridades

1.  Exportación PDF de historia clínica
2.  Agenda
3.  Inventario
4.  Ajustes avanzados

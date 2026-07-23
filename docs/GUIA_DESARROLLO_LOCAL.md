# Desarrollo local de Vetflow

Esta guía explica cómo iniciar Vetflow en local usando:

- Backend y PostgreSQL 17 en Docker.
- Un backup de la base de datos para cargar los datos iniciales.
- Frontend ejecutado con `pnpm`.

> **Importante:** el backup puede contener datos sensibles. Debe mantenerse fuera del repositorio, no compartirse y utilizarse únicamente en un entorno local aislado. Las integraciones externas deben permanecer deshabilitadas durante el desarrollo.

## Requisitos

- Docker y Docker Compose.
- Node.js y `pnpm`.
- El backup de PostgreSQL en formato `.dump`.
- El archivo `apps/api/firebase-service-account.json`, cuando la autenticación local lo requiera.

## 1. Configurar PostgreSQL 17

En `apps/api/docker-compose.yml`, el servicio `db` debe utilizar PostgreSQL 17:

```yaml
db:
  image: postgres:17
  environment:
    POSTGRES_USER: vetflow
    POSTGRES_PASSWORD: vetflow
    POSTGRES_DB: vetflow
  ports:
    - "5432:5432"
  volumes:
    - postgres_vetflow_data:/var/lib/postgresql/data
```

La API debe conectarse a la base mediante:

```text
postgresql://vetflow:vetflow@db:5432/vetflow
```

## 2. Levantar la base de datos

Desde `apps/api`:

```bash
docker compose up -d db
```

Confirma que PostgreSQL esté disponible:

```bash
docker compose exec db pg_isready -U vetflow -d vetflow
```

## 3. Restaurar el backup

Este paso se ejecuta solamente al preparar la base local por primera vez o cuando se desea reemplazarla por un backup más reciente.

Restaura exclusivamente el esquema `public`, evitando cargar los esquemas internos de Supabase:

```bash
docker compose exec -T db pg_restore \
  -U vetflow \
  -d vetflow \
  --schema=public \
  --no-owner \
  --no-privileges \
  --exit-on-error \
  < /ruta/al/backup/vetflow_supabase_YYYYMMDD_HHMMSS.dump
```

Verifica que las tablas se hayan restaurado:

```bash
docker compose exec -T db psql -U vetflow -d vetflow \
  -c "\dt public.*"
```

## 4. Levantar el backend

Desde `apps/api`:

```bash
docker compose up -d api
```

Ejecuta las migraciones pendientes después de restaurar el backup:

```bash
docker compose exec api alembic upgrade head
```

Revisa los logs si necesitas confirmar el inicio de la API:

```bash
docker compose logs -f api
```

La API queda disponible en:

```text
http://localhost:8000
```

La documentación interactiva de FastAPI puede consultarse en:

```text
http://localhost:8000/docs
```

## 5. Levantar el frontend

En otra terminal, desde `apps/web`:

```bash
pnpm install
pnpm run dev
```

El frontend queda disponible normalmente en:

```text
http://localhost:3000
```

## Flujo diario

Después de haber restaurado la base una vez, no es necesario volver a cargar el backup. Para iniciar el entorno:

Terminal 1:

```bash
cd apps/api
docker compose up -d
docker compose logs -f api
```

Terminal 2:

```bash
cd apps/web
pnpm run dev
```

Para detener los contenedores sin borrar los datos locales:

```bash
cd apps/api
docker compose down
```

> No uses `docker compose down -v` en el flujo diario: la opción `-v` elimina el volumen y todos los datos de la base local.

## Reemplazar la base con un backup más reciente

Si necesitas descartar la base local y restaurar un backup actualizado:

```bash
cd apps/api
docker compose down -v
docker compose up -d db
```

Después, repite los pasos de restauración, migraciones y arranque del backend descritos anteriormente.

# Vetflow API

FastAPI backend for Vetflow Platform.

## Dependency Source

Backend dependencies are managed only with `uv`:

- `pyproject.toml`
- `uv.lock`

Runtime dependencies live in `[project].dependencies`. Development and test dependencies live in `[dependency-groups].dev`.

## Local Run

Create `.env` from `.env.example`. Leave Firebase credentials empty when using the development tenant fallback, or set non-production Firebase values only when explicitly testing Firebase-backed auth locally.

```bash
cd apps/api
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run tests:

```bash
cd apps/api
uv run pytest
```

## Docker Run

Local Compose keeps the database separate from production with `DATABASE_URL` fixed to the Compose Postgres service. AI features and clinical file storage stay disabled. Firebase variables are optional through Compose interpolation (`FIREBASE_PROJECT_ID`, `FIREBASE_SERVICE_ACCOUNT_JSON`, `FIREBASE_SERVICE_ACCOUNT_JSON_PATH`), but local tests should run without production credentials.

```bash
cd apps/api
docker compose up --build
docker compose exec api alembic upgrade head
docker compose down
```

Run Compose tests with an empty interpolation file if your local `.env` contains Firebase values:

```bash
touch /tmp/vetflow-empty-compose.env
docker compose --env-file /tmp/vetflow-empty-compose.env run --rm api pytest
```

To remove the local database volume, run this explicit optional command:

```bash
docker compose down --volumes
```

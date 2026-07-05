# Vetflow API

Initial FastAPI backend for Vetflow Platform.

## Current Scope
- executable FastAPI app
- PostgreSQL-ready SQLAlchemy session setup
- health endpoints at `/health` and `/api/v1/health`
- Docker and docker-compose local setup
- tenant-aware foundation for future business modules

## Local Run (uv)

Dependencies are managed with [uv](https://docs.astral.sh/uv/) via `pyproject.toml`.

```bash
cd apps/api
uv sync                                   # create .venv + install deps (incl. dev group)
uv run alembic upgrade head               # apply migrations (creates tables)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run tests with `uv run pytest`.

> `requirements.txt` is kept only for the Docker image / Cloud Run build.
> When adding or bumping a dependency, update **both** `pyproject.toml` and `requirements.txt`.

## Docker Run
```bash
cd apps/api
docker-compose up --build
```

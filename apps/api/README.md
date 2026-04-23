# Vetflow API

Initial FastAPI backend for Vetflow Platform.

## Current Scope
- executable FastAPI app
- PostgreSQL-ready SQLAlchemy session setup
- health endpoints at `/health` and `/api/v1/health`
- Docker and docker-compose local setup
- tenant-aware foundation for future business modules

## Local Run
```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Docker Run
```bash
cd apps/api
docker-compose up --build
```

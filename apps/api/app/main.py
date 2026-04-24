from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.consultations import router as consultations_router
from app.api.debug import router as debug_router
from app.api.exams import router as exams_router
from app.api.health import router as health_router
from app.api.owners import router as owners_router
from app.api.patients import router as patients_router
from app.api.search import router as search_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers

settings = get_settings()

app = FastAPI(title="Vetflow API", version="0.1.0")
register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://vetflow-platform.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_v1_router = APIRouter(prefix=settings.api_v1_prefix)
api_v1_router.include_router(health_router)
api_v1_router.include_router(debug_router)
api_v1_router.include_router(owners_router)
api_v1_router.include_router(patients_router)
api_v1_router.include_router(consultations_router)
api_v1_router.include_router(exams_router)
api_v1_router.include_router(search_router)

app.include_router(health_router)
app.include_router(api_v1_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Vetflow API is running"}

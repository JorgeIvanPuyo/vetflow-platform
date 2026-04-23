import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.app_env = os.getenv("APP_ENV", "development")
        self.app_port = int(os.getenv("APP_PORT", "8000"))
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://vetflow:vetflow@localhost:5432/vetflow",
        )
        self.api_v1_prefix = "/api/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()

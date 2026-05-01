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
        self.firebase_project_id = os.getenv("FIREBASE_PROJECT_ID")
        self.firebase_service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
        self.firebase_service_account_json_path = os.getenv(
            "FIREBASE_SERVICE_ACCOUNT_JSON_PATH"
        )
        self.clinical_files_bucket_name = os.getenv("CLINICAL_FILES_BUCKET_NAME")
        self.max_clinical_file_size_mb = int(
            os.getenv("MAX_CLINICAL_FILE_SIZE_MB", "25")
        )
        self.api_v1_prefix = "/api/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()

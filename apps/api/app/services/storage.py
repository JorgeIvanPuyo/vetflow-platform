from __future__ import annotations

from datetime import timedelta

from app.core.config import get_settings
from app.core.errors import AppError


class ClinicalFileStorageService:
    def __init__(self, bucket_name: str | None = None) -> None:
        settings = get_settings()
        self.bucket_name = bucket_name or settings.clinical_files_bucket_name

    def upload_clinical_file(
        self,
        *,
        object_path: str,
        content: bytes,
        content_type: str,
    ) -> None:
        bucket = self._get_bucket()
        blob = bucket.blob(object_path)
        blob.upload_from_string(content, content_type=content_type)

    def delete_clinical_file(self, *, bucket_name: str, object_path: str) -> None:
        bucket = self._get_bucket(bucket_name)
        blob = bucket.blob(object_path)
        blob.delete()

    def generate_signed_download_url(
        self,
        *,
        bucket_name: str,
        object_path: str,
        expires_in_seconds: int,
    ) -> str:
        bucket = self._get_bucket(bucket_name)
        blob = bucket.blob(object_path)
        return blob.generate_signed_url(
            expiration=timedelta(seconds=expires_in_seconds),
            method="GET",
        )

    def _get_bucket(self, bucket_name: str | None = None):
        resolved_bucket_name = bucket_name or self.bucket_name
        if not resolved_bucket_name:
            raise AppError(
                503,
                "storage_not_configured",
                "Clinical file storage is not configured",
            )

        try:
            from google.cloud import storage
        except ImportError as exc:
            raise AppError(
                503,
                "storage_not_configured",
                "Clinical file storage dependency is not installed",
            ) from exc

        client = storage.Client()
        return client.bucket(resolved_bucket_name)


def get_storage_service() -> ClinicalFileStorageService:
    return ClinicalFileStorageService()

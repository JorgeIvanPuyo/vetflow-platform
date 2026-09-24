from __future__ import annotations

import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Any, Protocol

from app.core.config import get_settings
from app.core.errors import AppError


LOCAL_STORAGE_BUCKET_NAME = "local-vetflow"


class ObjectStorageService(Protocol):
    bucket_name: str | None

    def upload_clinical_file(
        self, *, object_path: str, content: bytes, content_type: str
    ) -> None: ...

    def delete_clinical_file(self, *, bucket_name: str, object_path: str) -> None: ...

    def download_object_bytes(self, *, bucket_name: str, object_path: str) -> bytes: ...


class ClinicalFileStorageService:
    def __init__(self, bucket_name: str | None = None) -> None:
        settings = get_settings()
        self.bucket_name = bucket_name or settings.clinical_files_bucket_name
        self._credentials: Any | None = None
        self._client: Any | None = None

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

    def download_object_bytes(self, *, bucket_name: str, object_path: str) -> bytes:
        bucket = self._get_bucket(bucket_name)
        blob = bucket.blob(object_path)
        return blob.download_as_bytes()

    def generate_signed_download_url(
        self,
        *,
        bucket_name: str,
        object_path: str,
        expires_in_seconds: int,
    ) -> str:
        bucket = self._get_bucket(bucket_name)
        blob = bucket.blob(object_path)
        kwargs: dict[str, Any] = {
            "expiration": timedelta(seconds=expires_in_seconds),
            "method": "GET",
        }
        credentials = self._get_credentials()
        if credentials is not None:
            kwargs["credentials"] = credentials

        return blob.generate_signed_url(**kwargs)

    def _get_bucket(self, bucket_name: str | None = None):
        resolved_bucket_name = bucket_name or self.bucket_name
        if not resolved_bucket_name:
            raise AppError(
                503,
                "storage_not_configured",
                "Clinical file storage is not configured",
            )

        client = self._get_client()
        return client.bucket(resolved_bucket_name)

    def _get_client(self):
        if self._client is not None:
            return self._client

        try:
            from google.cloud import storage
        except ImportError as exc:
            raise AppError(
                503,
                "storage_not_configured",
                "Clinical file storage dependency is not installed",
            ) from exc

        credentials = self._get_credentials()
        if credentials is None:
            self._client = storage.Client()
            return self._client

        self._client = storage.Client(
            credentials=credentials,
            project=getattr(credentials, "project_id", None),
        )
        return self._client

    def _get_credentials(self):
        if self._credentials is not None:
            return self._credentials

        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        settings = get_settings()

        if credentials_path:
            self._credentials = self._load_credentials_from_file(credentials_path)
            return self._credentials

        if settings.firebase_service_account_json:
            self._credentials = self._load_credentials_from_json(
                settings.firebase_service_account_json,
            )
            return self._credentials

        return None

    def _load_credentials_from_file(self, credentials_path: str):
        try:
            from google.oauth2 import service_account
        except ImportError as exc:
            raise AppError(
                503,
                "storage_not_configured",
                "Clinical file storage credential dependency is not installed",
            ) from exc

        try:
            return service_account.Credentials.from_service_account_file(
                credentials_path,
            )
        except Exception as exc:
            raise AppError(
                503,
                "storage_not_configured",
                "Clinical file storage credentials could not be loaded",
            ) from exc

    def _load_credentials_from_json(self, credentials_json: str):
        try:
            from google.oauth2 import service_account
        except ImportError as exc:
            raise AppError(
                503,
                "storage_not_configured",
                "Clinical file storage credential dependency is not installed",
            ) from exc

        try:
            credentials_info = json.loads(credentials_json)
            return service_account.Credentials.from_service_account_info(
                credentials_info,
            )
        except Exception as exc:
            raise AppError(
                503,
                "storage_not_configured",
                "Clinical file storage credentials could not be loaded",
            ) from exc


class LocalFileStorageService:
    def __init__(self, root_path: str | None = None) -> None:
        settings = get_settings()
        self.bucket_name = LOCAL_STORAGE_BUCKET_NAME
        self.root_path = Path(root_path or settings.local_file_storage_path).resolve()

    def upload_clinical_file(
        self,
        *,
        object_path: str,
        content: bytes,
        content_type: str,
    ) -> None:
        del content_type
        destination = self._resolve_path(self.bucket_name, object_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

    def delete_clinical_file(self, *, bucket_name: str, object_path: str) -> None:
        destination = self._resolve_path(bucket_name, object_path)
        destination.unlink(missing_ok=True)

    def download_object_bytes(self, *, bucket_name: str, object_path: str) -> bytes:
        destination = self._resolve_path(bucket_name, object_path)
        if not destination.is_file():
            raise AppError(404, "storage_object_not_found", "Stored file not found")
        return destination.read_bytes()

    def _resolve_path(self, bucket_name: str, object_path: str) -> Path:
        if bucket_name != self.bucket_name:
            raise AppError(404, "storage_object_not_found", "Stored file not found")
        relative_path = Path(object_path)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise AppError(400, "invalid_storage_path", "Invalid storage object path")
        bucket_root = (self.root_path / self.bucket_name).resolve()
        destination = (bucket_root / relative_path).resolve()
        if not destination.is_relative_to(bucket_root):
            raise AppError(400, "invalid_storage_path", "Invalid storage object path")
        return destination


def get_storage_service() -> ClinicalFileStorageService:
    return ClinicalFileStorageService()


def get_purchase_attachment_storage_service() -> ObjectStorageService:
    settings = get_settings()
    if settings.clinical_files_bucket_name:
        return ClinicalFileStorageService()
    if settings.app_env == "development":
        return LocalFileStorageService()
    return ClinicalFileStorageService()

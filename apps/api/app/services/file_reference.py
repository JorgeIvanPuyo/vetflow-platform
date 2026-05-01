import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.patient import Patient
from app.models.patient_file_reference import PatientFileReference
from app.repositories.file_reference import FileReferenceRepository
from app.repositories.patient import PatientRepository
from app.schemas.file_reference import FileReferenceCreate, FileReferenceUpdate
from app.services.storage import ClinicalFileStorageService


ALLOWED_CLINICAL_FILE_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}
ALLOWED_CLINICAL_FILE_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
SIGNED_URL_EXPIRES_IN_SECONDS = 900
logger = logging.getLogger(__name__)


class FileReferenceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.file_reference_repository = FileReferenceRepository(db)
        self.patient_repository = PatientRepository(db)

    def create_file_reference(
        self,
        tenant_id: uuid.UUID,
        patient_id: uuid.UUID,
        payload: FileReferenceCreate,
        *,
        created_by_user_id: uuid.UUID | None = None,
    ) -> PatientFileReference:
        self._get_patient_for_tenant(tenant_id, patient_id)

        file_reference = PatientFileReference(
            tenant_id=tenant_id,
            patient_id=patient_id,
            created_by_user_id=created_by_user_id,
            **payload.model_dump(),
        )
        self.file_reference_repository.create(file_reference)
        self.db.commit()
        return file_reference

    def upload_clinical_file(
        self,
        tenant_id: uuid.UUID,
        patient_id: uuid.UUID,
        *,
        name: str,
        file_type: str,
        description: str | None,
        original_filename: str | None,
        content_type: str | None,
        content: bytes | None,
        created_by_user_id: uuid.UUID | None,
        storage_service: ClinicalFileStorageService,
    ) -> PatientFileReference:
        self._get_patient_for_tenant(tenant_id, patient_id)
        settings = get_settings()
        bucket_name = storage_service.bucket_name
        if not bucket_name:
            raise AppError(
                503,
                "storage_not_configured",
                "Clinical file storage is not configured",
            )

        self._validate_upload_fields(name, file_type)
        safe_filename = self._validate_file(
            original_filename=original_filename,
            content_type=content_type,
            content=content,
            max_size_mb=settings.max_clinical_file_size_mb,
        )

        file_reference = PatientFileReference(
            tenant_id=tenant_id,
            patient_id=patient_id,
            created_by_user_id=created_by_user_id,
            name=name.strip(),
            file_type=file_type.strip(),
            description=description.strip() if description else None,
            original_filename=original_filename,
            content_type=content_type,
            size_bytes=len(content or b""),
        )
        self.file_reference_repository.create(file_reference)
        object_path = self._build_object_path(
            tenant_id=tenant_id,
            patient_id=patient_id,
            file_reference_id=file_reference.id,
            safe_filename=safe_filename,
        )

        try:
            storage_service.upload_clinical_file(
                object_path=object_path,
                content=content or b"",
                content_type=content_type or "application/octet-stream",
            )
            self.file_reference_repository.update(
                file_reference,
                {
                    "bucket_name": bucket_name,
                    "object_path": object_path,
                    "uploaded_at": datetime.now(timezone.utc),
                },
            )
            self.db.commit()
        except AppError:
            self.db.rollback()
            raise
        except Exception as exc:
            logger.exception(
                "Clinical file upload failed. exception_class=%s message=%s "
                "bucket_name=%s object_path=%s content_type=%s size_bytes=%s",
                exc.__class__.__name__,
                str(exc),
                bucket_name,
                object_path,
                content_type,
                len(content or b""),
                extra={
                    "exception_class": exc.__class__.__name__,
                    "exception_message": str(exc),
                    "bucket_name": bucket_name,
                    "object_path": object_path,
                    "content_type": content_type,
                    "size_bytes": len(content or b""),
                },
            )
            self.db.rollback()
            raise AppError(
                502,
                "storage_upload_failed",
                "Clinical file upload failed",
            ) from exc

        return file_reference

    def list_patient_file_references(
        self,
        tenant_id: uuid.UUID,
        patient_id: uuid.UUID,
    ) -> tuple[list[PatientFileReference], int]:
        self._get_patient_for_tenant(tenant_id, patient_id)
        return self.file_reference_repository.list_by_patient(tenant_id, patient_id)

    def get_file_reference(
        self,
        tenant_id: uuid.UUID,
        file_reference_id: uuid.UUID,
    ) -> PatientFileReference:
        file_reference = self.file_reference_repository.get_by_id(
            tenant_id,
            file_reference_id,
        )
        if file_reference is None:
            raise AppError(
                404,
                "file_reference_not_found",
                "File reference not found",
            )
        return file_reference

    def update_file_reference(
        self,
        tenant_id: uuid.UUID,
        file_reference_id: uuid.UUID,
        payload: FileReferenceUpdate,
    ) -> PatientFileReference:
        file_reference = self.get_file_reference(tenant_id, file_reference_id)
        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates and updates["name"] is None:
            raise AppError(422, "validation_error", "name cannot be null")
        if "file_type" in updates and updates["file_type"] is None:
            raise AppError(422, "validation_error", "file_type cannot be null")

        updated_file_reference = self.file_reference_repository.update(
            file_reference,
            updates,
        )
        self.db.commit()
        return updated_file_reference

    def delete_file_reference(
        self,
        tenant_id: uuid.UUID,
        file_reference_id: uuid.UUID,
        *,
        storage_service: ClinicalFileStorageService | None = None,
    ) -> None:
        file_reference = self.get_file_reference(tenant_id, file_reference_id)
        if file_reference.object_path:
            if not file_reference.bucket_name:
                raise AppError(
                    409,
                    "storage_not_configured",
                    "File reference storage metadata is incomplete",
                )
            if storage_service is None:
                storage_service = ClinicalFileStorageService()

            try:
                storage_service.delete_clinical_file(
                    bucket_name=file_reference.bucket_name,
                    object_path=file_reference.object_path,
                )
            except AppError:
                raise
            except Exception as exc:
                raise AppError(
                    502,
                    "storage_delete_failed",
                    "Clinical file delete failed",
                ) from exc

        self.file_reference_repository.delete(file_reference)
        self.db.commit()

    def get_file_download_url(
        self,
        tenant_id: uuid.UUID,
        file_reference_id: uuid.UUID,
        *,
        storage_service: ClinicalFileStorageService,
        expires_in_seconds: int = SIGNED_URL_EXPIRES_IN_SECONDS,
    ) -> tuple[str, int]:
        file_reference = self.get_file_reference(tenant_id, file_reference_id)
        if not file_reference.bucket_name or not file_reference.object_path:
            raise AppError(
                404,
                "file_reference_not_found",
                "Uploaded file not found for this reference",
            )

        try:
            download_url = storage_service.generate_signed_download_url(
                bucket_name=file_reference.bucket_name,
                object_path=file_reference.object_path,
                expires_in_seconds=expires_in_seconds,
            )
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                502,
                "storage_download_url_failed",
                "Clinical file download URL generation failed",
            ) from exc

        return download_url, expires_in_seconds

    def _get_patient_for_tenant(
        self,
        tenant_id: uuid.UUID,
        patient_id: uuid.UUID,
    ) -> Patient:
        patient = self.patient_repository.get_by_id(tenant_id, patient_id)
        if patient is None:
            patient_any_tenant = self.db.get(Patient, patient_id)
            if patient_any_tenant is not None:
                raise AppError(
                    409,
                    "invalid_cross_tenant_access",
                    "Patient does not belong to the provided tenant",
                )
            raise AppError(404, "patient_not_found", "Patient not found")
        return patient

    def _validate_upload_fields(self, name: str, file_type: str) -> None:
        if not name or not name.strip():
            raise AppError(422, "validation_error", "name is required")
        if not file_type or not file_type.strip():
            raise AppError(422, "validation_error", "file_type is required")

    def _validate_file(
        self,
        *,
        original_filename: str | None,
        content_type: str | None,
        content: bytes | None,
        max_size_mb: int,
    ) -> str:
        if not original_filename or content is None:
            raise AppError(400, "missing_file", "File is required")

        extension = Path(original_filename).suffix.lower()
        if (
            content_type not in ALLOWED_CLINICAL_FILE_CONTENT_TYPES
            or extension not in ALLOWED_CLINICAL_FILE_EXTENSIONS
        ):
            raise AppError(415, "invalid_file_type", "Invalid clinical file type")

        max_size_bytes = max_size_mb * 1024 * 1024
        if len(content) > max_size_bytes:
            raise AppError(413, "file_too_large", "Clinical file is too large")

        return self._safe_filename(original_filename)

    def _safe_filename(self, filename: str) -> str:
        name = Path(filename).name.strip()
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", name)
        name = name.strip(".-")
        return name or "clinical-file"

    def _build_object_path(
        self,
        *,
        tenant_id: uuid.UUID,
        patient_id: uuid.UUID,
        file_reference_id: uuid.UUID,
        safe_filename: str,
    ) -> str:
        return (
            f"tenants/{tenant_id}/patients/{patient_id}/files/"
            f"{file_reference_id}/{safe_filename}"
        )

import uuid
from pathlib import Path
import re

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.clinic import ClinicRepository
from app.repositories.user import UserRepository
from app.schemas.clinic import ClinicProfileUpdate
from app.services.storage import ClinicalFileStorageService


ALLOWED_CLINIC_LOGO_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
}
ALLOWED_CLINIC_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_CLINIC_LOGO_SIZE_BYTES = 5 * 1024 * 1024
SIGNED_LOGO_URL_EXPIRES_IN_SECONDS = 900


class ClinicService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.clinic_repository = ClinicRepository(db)
        self.user_repository = UserRepository(db)

    def get_profile(self, tenant_id: uuid.UUID) -> Tenant:
        tenant = self.clinic_repository.get_profile(tenant_id)
        if tenant is None:
            raise AppError(404, "clinic_not_found", "Clinic profile not found")
        return tenant

    def update_profile(
        self,
        tenant_id: uuid.UUID,
        payload: ClinicProfileUpdate,
    ) -> Tenant:
        tenant = self.get_profile(tenant_id)
        updates = payload.model_dump(exclude_unset=True)
        updated_tenant = self.clinic_repository.update_profile(tenant, updates)
        self.db.commit()
        return updated_tenant

    def list_team(self, tenant_id: uuid.UUID) -> list[User]:
        self.get_profile(tenant_id)
        return self.user_repository.list_active_by_tenant(tenant_id)

    def upload_logo(
        self,
        tenant_id: uuid.UUID,
        *,
        original_filename: str | None,
        content_type: str | None,
        content: bytes | None,
        storage_service: ClinicalFileStorageService,
    ) -> Tenant:
        tenant = self.get_profile(tenant_id)
        bucket_name = storage_service.bucket_name
        if not bucket_name:
            raise AppError(
                503,
                "storage_not_configured",
                "Clinical file storage is not configured",
            )

        safe_filename = self._validate_logo_file(
            original_filename=original_filename,
            content_type=content_type,
            content=content,
        )
        object_path = self._build_logo_object_path(tenant_id, safe_filename)

        if tenant.logo_object_path:
            try:
                storage_service.delete_clinical_file(
                    bucket_name=bucket_name,
                    object_path=tenant.logo_object_path,
                )
            except AppError:
                raise
            except Exception as exc:
                raise AppError(
                    502,
                    "clinic_logo_delete_failed",
                    "Clinic logo delete failed",
                ) from exc

        try:
            storage_service.upload_clinical_file(
                object_path=object_path,
                content=content or b"",
                content_type=content_type or "application/octet-stream",
            )
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                502,
                "clinic_logo_upload_failed",
                "Clinic logo upload failed",
            ) from exc

        updated_tenant = self.clinic_repository.update_profile(
            tenant,
            {
                "logo_url": f"gs://{bucket_name}/{object_path}",
                "logo_object_path": object_path,
            },
        )
        self.db.commit()
        return updated_tenant

    def delete_logo(
        self,
        tenant_id: uuid.UUID,
        *,
        storage_service: ClinicalFileStorageService,
    ) -> Tenant:
        tenant = self.get_profile(tenant_id)
        bucket_name = storage_service.bucket_name

        if tenant.logo_object_path:
            if not bucket_name:
                raise AppError(
                    503,
                    "storage_not_configured",
                    "Clinical file storage is not configured",
                )
            try:
                storage_service.delete_clinical_file(
                    bucket_name=bucket_name,
                    object_path=tenant.logo_object_path,
                )
            except AppError:
                raise
            except Exception as exc:
                raise AppError(
                    502,
                    "clinic_logo_delete_failed",
                    "Clinic logo delete failed",
                ) from exc

        updated_tenant = self.clinic_repository.update_profile(
            tenant,
            {
                "logo_url": None,
                "logo_object_path": None,
            },
        )
        self.db.commit()
        return updated_tenant

    def build_profile_response(
        self,
        tenant: Tenant,
        *,
        storage_service: ClinicalFileStorageService | None = None,
    ) -> dict:
        logo_url = tenant.logo_url
        if tenant.logo_object_path and storage_service and storage_service.bucket_name:
            try:
                logo_url = storage_service.generate_signed_download_url(
                    bucket_name=storage_service.bucket_name,
                    object_path=tenant.logo_object_path,
                    expires_in_seconds=SIGNED_LOGO_URL_EXPIRES_IN_SECONDS,
                )
            except Exception:
                logo_url = tenant.logo_url

        return {
            "id": tenant.id,
            "name": tenant.name,
            "display_name": tenant.display_name or tenant.name,
            "logo_url": logo_url,
            "phone": tenant.phone,
            "email": tenant.email,
            "address": tenant.address,
            "notes": tenant.notes,
        }

    def _validate_logo_file(
        self,
        *,
        original_filename: str | None,
        content_type: str | None,
        content: bytes | None,
    ) -> str:
        if not original_filename or content is None:
            raise AppError(400, "missing_file", "File is required")

        extension = Path(original_filename).suffix.lower()
        if (
            content_type not in ALLOWED_CLINIC_LOGO_CONTENT_TYPES
            or extension not in ALLOWED_CLINIC_LOGO_EXTENSIONS
        ):
            raise AppError(415, "invalid_logo_type", "Invalid clinic logo type")

        if len(content) > MAX_CLINIC_LOGO_SIZE_BYTES:
            raise AppError(413, "logo_too_large", "Clinic logo is too large")

        return self._safe_filename(original_filename)

    def _safe_filename(self, filename: str) -> str:
        name = Path(filename).name.strip()
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", name)
        name = name.strip(".-")
        return name or "clinic-logo"

    def _build_logo_object_path(
        self,
        tenant_id: uuid.UUID,
        safe_filename: str,
    ) -> str:
        return f"tenants/{tenant_id}/branding/logo/{tenant_id}-{safe_filename}"

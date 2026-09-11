import uuid
from pathlib import Path
import re

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.tenant import Tenant
from app.models.tenant_preference import TenantPreference
from app.models.user import User
from app.repositories.clinic import ClinicRepository
from app.repositories.service import ServiceRepository
from app.repositories.user import UserRepository
from app.schemas.clinic import ClinicProfileUpdate, ClinicTeamMemberUpdate, TenantPreferenceUpdate
from app.services.catalog_items import CatalogItemService
from app.services.regional_settings import ensure_operational_money_settings
from app.services.storage import ClinicalFileStorageService


ALLOWED_CLINIC_LOGO_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
}
ALLOWED_CLINIC_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_CLINIC_LOGO_SIZE_BYTES = 5 * 1024 * 1024
SIGNED_LOGO_URL_EXPIRES_IN_SECONDS = 900
SUPPORTED_REGIONAL_SETTINGS = {("USD", "es-PA"), ("ARS", "es-AR")}
DEFAULT_DURATION_OPTIONS = [15, 30, 45, 60]


class ClinicService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.clinic_repository = ClinicRepository(db)
        self.service_repository = ServiceRepository(db)
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

    def get_preferences(self, tenant_id: uuid.UUID) -> TenantPreference:
        self.get_profile(tenant_id)
        preferences = self.clinic_repository.get_preferences(tenant_id)
        if preferences is not None:
            return preferences

        ensure_operational_money_settings(self.clinic_repository, tenant_id)
        self.db.commit()
        preferences = self.clinic_repository.get_preferences(tenant_id)
        if preferences is None:  # pragma: no cover - defensive invariant
            raise RuntimeError("Tenant preferences were not persisted")
        return preferences

    def update_preferences(
        self,
        tenant_id: uuid.UUID,
        payload: TenantPreferenceUpdate,
    ) -> TenantPreference:
        preferences = self.get_preferences(tenant_id)
        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            if value is None:
                raise AppError(422, "validation_error", f"{field} cannot be null")

        resolved = {
            "currency_code": updates.get("currency_code", preferences.currency_code),
            "locale": updates.get("locale", preferences.locale),
            "default_appointment_duration_minutes": updates.get(
                "default_appointment_duration_minutes",
                preferences.default_appointment_duration_minutes,
            ),
            "appointment_duration_options": updates.get(
                "appointment_duration_options",
                preferences.appointment_duration_options,
            ),
        }
        self._validate_preferences(resolved)
        if (
            resolved["currency_code"] != preferences.currency_code
            and self.clinic_repository.has_monetary_activity(tenant_id)
        ):
            raise AppError(
                409,
                "currency_change_locked",
                "La moneda no puede cambiar cuando ya existen precios, compras o ventas. Crea un proceso explícito de conversión antes de cambiarla.",
            )
        updated_preferences = self.clinic_repository.update_preferences(
            preferences,
            updates,
        )
        self.db.commit()
        return updated_preferences

    def get_configuration(
        self,
        tenant_id: uuid.UUID,
        *,
        include_preferences: bool,
        include_services: bool,
        include_catalogs: bool = False,
    ) -> dict:
        self.get_profile(tenant_id)
        return {
            "preferences": self.get_preferences(tenant_id) if include_preferences else None,
            "services": self.service_repository.list(
                tenant_id,
                include_inactive=False,
                bookable_only=False,
            )
            if include_services
            else None,
            "catalogs": CatalogItemService(self.db).list_active_grouped(tenant_id)
            if include_catalogs
            else None,
        }

    def list_team(self, tenant_id: uuid.UUID) -> list[User]:
        self.get_profile(tenant_id)
        return self.user_repository.list_active_by_tenant(tenant_id)

    def update_team_member(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: ClinicTeamMemberUpdate,
    ) -> User:
        self.get_profile(tenant_id)
        user = self.user_repository.get_by_id(tenant_id, user_id)
        if user is None or not user.is_active:
            raise AppError(
                404,
                "team_member_not_found",
                "Clinic team member not found",
            )

        updated_user = self.user_repository.update_full_name(user, payload.full_name)
        self.db.commit()
        return updated_user

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
            "timezone": tenant.timezone or "America/Panama",
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

    def _validate_preferences(self, values: dict) -> None:
        currency_code = values["currency_code"]
        locale = values["locale"]
        if (currency_code, locale) not in SUPPORTED_REGIONAL_SETTINGS:
            raise AppError(
                422,
                "unsupported_regional_preferences",
                "Unsupported currency_code and locale combination",
            )

        options = values["appointment_duration_options"]
        if (
            not isinstance(options, list)
            or not options
            or any(not isinstance(option, int) for option in options)
            or any(option <= 0 or option > 480 for option in options)
        ):
            raise AppError(
                422,
                "invalid_appointment_duration_options",
                "Appointment duration options must be positive minute values",
            )
        if len(set(options)) != len(options):
            raise AppError(
                422,
                "invalid_appointment_duration_options",
                "Appointment duration options must be unique",
            )
        if values["default_appointment_duration_minutes"] not in options:
            raise AppError(
                422,
                "invalid_default_appointment_duration",
                "Default appointment duration must be included in appointment duration options",
            )

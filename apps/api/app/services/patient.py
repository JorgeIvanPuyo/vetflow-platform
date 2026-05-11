import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.consultation import Consultation
from app.models.exam import Exam
from app.models.follow_up import FollowUp
from app.models.owner import Owner
from app.models.patient import Patient
from app.models.patient_file_reference import PatientFileReference
from app.models.patient_preventive_care import PatientPreventiveCare
from app.repositories.owner import OwnerRepository
from app.repositories.patient import PatientRepository
from app.schemas.patient import PatientCreate, PatientRead, PatientUpdate
from app.services.storage import ClinicalFileStorageService


ALLOWED_PATIENT_PHOTO_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
}
ALLOWED_PATIENT_PHOTO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_PATIENT_PHOTO_SIZE_BYTES = 5 * 1024 * 1024
SIGNED_PATIENT_PHOTO_URL_EXPIRES_IN_SECONDS = 900
logger = logging.getLogger(__name__)


class PatientService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.owner_repository = OwnerRepository(db)
        self.patient_repository = PatientRepository(db)

    def create_patient(
        self,
        tenant_id: uuid.UUID,
        payload: PatientCreate,
        *,
        created_by_user_id: uuid.UUID | None = None,
    ) -> Patient:
        owner = self.owner_repository.get_by_id(tenant_id, payload.owner_id)
        if owner is None:
            owner_any_tenant = self.db.get(Owner, payload.owner_id)
            if owner_any_tenant is not None:
                raise AppError(
                    409,
                    "invalid_cross_tenant_access",
                    "Owner does not belong to the provided tenant",
                )
            raise AppError(
                404,
                "owner_not_found",
                "Owner not found for the provided tenant",
            )

        patient = Patient(
            tenant_id=tenant_id,
            created_by_user_id=created_by_user_id,
            **payload.model_dump(),
        )
        self.patient_repository.create(patient)
        self.db.commit()
        return patient

    def list_patients(
        self,
        tenant_id: uuid.UUID,
        *,
        owner_id: uuid.UUID | None = None,
        species: str | None = None,
        search: str | None = None,
    ) -> tuple[list[Patient], int]:
        return self.patient_repository.list(
            tenant_id,
            owner_id=owner_id,
            species=species,
            search=search,
        )

    def get_patient(self, tenant_id: uuid.UUID, patient_id: uuid.UUID) -> Patient:
        patient = self.patient_repository.get_by_id(tenant_id, patient_id)
        if patient is None:
            raise AppError(404, "patient_not_found", "Patient not found")
        return patient

    def update_patient(
        self, tenant_id: uuid.UUID, patient_id: uuid.UUID, payload: PatientUpdate
    ) -> Patient:
        patient = self.get_patient(tenant_id, patient_id)
        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates and updates["name"] is None:
            raise AppError(422, "validation_error", "name cannot be null")
        if "species" in updates and updates["species"] is None:
            raise AppError(422, "validation_error", "species cannot be null")

        if "owner_id" in updates and updates["owner_id"] is None:
            raise AppError(422, "validation_error", "owner_id cannot be null")

        new_owner_id = updates.get("owner_id")
        if new_owner_id is not None:
            owner = self.owner_repository.get_by_id(tenant_id, new_owner_id)
            if owner is None:
                owner_any_tenant = self.db.get(Owner, new_owner_id)
                if owner_any_tenant is not None:
                    raise AppError(
                        409,
                        "invalid_cross_tenant_access",
                        "Owner does not belong to the provided tenant",
                    )
                raise AppError(404, "owner_not_found", "Owner not found")

        updated_patient = self.patient_repository.update(patient, updates)
        self.db.commit()
        return updated_patient

    def upload_patient_photo(
        self,
        tenant_id: uuid.UUID,
        patient_id: uuid.UUID,
        *,
        original_filename: str | None,
        content_type: str | None,
        content: bytes | None,
        storage_service: ClinicalFileStorageService,
    ) -> Patient:
        patient = self._get_patient_for_tenant(tenant_id, patient_id)
        bucket_name = storage_service.bucket_name
        if not bucket_name:
            raise AppError(
                503,
                "storage_not_configured",
                "Clinical file storage is not configured",
            )

        safe_filename = self._validate_photo_file(
            original_filename=original_filename,
            content_type=content_type,
            content=content,
        )
        object_path = self._build_photo_object_path(
            tenant_id=tenant_id,
            patient_id=patient_id,
            safe_filename=safe_filename,
        )

        if patient.photo_object_path:
            try:
                storage_service.delete_clinical_file(
                    bucket_name=patient.photo_bucket_name or bucket_name,
                    object_path=patient.photo_object_path,
                )
            except AppError:
                raise
            except Exception as exc:
                raise AppError(
                    502,
                    "patient_photo_delete_failed",
                    "Patient photo delete failed",
                ) from exc

        try:
            storage_service.upload_clinical_file(
                object_path=object_path,
                content=content or b"",
                content_type=content_type or "application/octet-stream",
            )
            updated_patient = self.patient_repository.update(
                patient,
                {
                    "photo_url": f"gs://{bucket_name}/{object_path}",
                    "photo_bucket_name": bucket_name,
                    "photo_object_path": object_path,
                    "photo_original_filename": original_filename,
                    "photo_content_type": content_type,
                    "photo_size_bytes": len(content or b""),
                    "photo_uploaded_at": datetime.now(timezone.utc),
                },
            )
            self.db.commit()
        except AppError:
            self.db.rollback()
            raise
        except Exception as exc:
            logger.exception(
                "Patient photo upload failed. exception_class=%s message=%s "
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
                "patient_photo_upload_failed",
                "Patient photo upload failed",
            ) from exc

        return updated_patient

    def delete_patient_photo(
        self,
        tenant_id: uuid.UUID,
        patient_id: uuid.UUID,
        *,
        storage_service: ClinicalFileStorageService,
    ) -> Patient:
        patient = self._get_patient_for_tenant(tenant_id, patient_id)
        if patient.photo_object_path:
            bucket_name = patient.photo_bucket_name or storage_service.bucket_name
            if not bucket_name:
                raise AppError(
                    503,
                    "storage_not_configured",
                    "Clinical file storage is not configured",
                )
            try:
                storage_service.delete_clinical_file(
                    bucket_name=bucket_name,
                    object_path=patient.photo_object_path,
                )
            except AppError:
                raise
            except Exception as exc:
                raise AppError(
                    502,
                    "patient_photo_delete_failed",
                    "Patient photo delete failed",
                ) from exc

        updated_patient = self.patient_repository.update(
            patient,
            self._photo_clear_updates(),
        )
        self.db.commit()
        return updated_patient

    def delete_patient(
        self,
        tenant_id: uuid.UUID,
        patient_id: uuid.UUID,
        *,
        storage_service: ClinicalFileStorageService | None = None,
    ) -> None:
        patient = self.get_patient(tenant_id, patient_id)
        if patient.photo_object_path:
            bucket_name = patient.photo_bucket_name or (
                storage_service.bucket_name if storage_service else None
            )
            if not bucket_name:
                raise AppError(
                    503,
                    "storage_not_configured",
                    "Clinical file storage is not configured",
                )
            if storage_service is None:
                storage_service = ClinicalFileStorageService()
            try:
                storage_service.delete_clinical_file(
                    bucket_name=bucket_name,
                    object_path=patient.photo_object_path,
                )
            except AppError:
                raise
            except Exception as exc:
                raise AppError(
                    502,
                    "patient_photo_delete_failed",
                    "Patient photo delete failed",
                ) from exc

        self.db.execute(
            delete(PatientFileReference).where(
                PatientFileReference.tenant_id == tenant_id,
                PatientFileReference.patient_id == patient_id,
            )
        )
        self.db.execute(
            delete(FollowUp).where(
                FollowUp.tenant_id == tenant_id,
                FollowUp.patient_id == patient_id,
            )
        )
        self.db.execute(
            delete(PatientPreventiveCare).where(
                PatientPreventiveCare.tenant_id == tenant_id,
                PatientPreventiveCare.patient_id == patient_id,
            )
        )
        self.db.execute(
            delete(Exam).where(
                Exam.tenant_id == tenant_id,
                Exam.patient_id == patient_id,
            )
        )
        self.db.execute(
            delete(Consultation).where(
                Consultation.tenant_id == tenant_id,
                Consultation.patient_id == patient_id,
            )
        )
        self.patient_repository.delete(patient)
        self.db.commit()

    def build_patient_response(
        self,
        patient: Patient,
        *,
        storage_service: ClinicalFileStorageService | None = None,
    ) -> dict:
        data = PatientRead.model_validate(patient).model_dump(mode="json")
        data["photo_url"] = self._build_signed_photo_url(
            patient,
            storage_service=storage_service,
        )
        return data

    def build_patient_list_response(
        self,
        patients: list[Patient],
        *,
        storage_service: ClinicalFileStorageService | None = None,
    ) -> list[dict]:
        return [
            self.build_patient_response(patient, storage_service=storage_service)
            for patient in patients
        ]

    def _build_signed_photo_url(
        self,
        patient: Patient,
        *,
        storage_service: ClinicalFileStorageService | None,
    ) -> str | None:
        if not patient.photo_object_path:
            return None

        photo_url = patient.photo_url
        bucket_name = patient.photo_bucket_name or (
            storage_service.bucket_name if storage_service else None
        )
        if bucket_name and storage_service:
            try:
                return storage_service.generate_signed_download_url(
                    bucket_name=bucket_name,
                    object_path=patient.photo_object_path,
                    expires_in_seconds=SIGNED_PATIENT_PHOTO_URL_EXPIRES_IN_SECONDS,
                )
            except Exception:
                logger.exception(
                    "Patient photo signed URL generation failed. patient_id=%s "
                    "tenant_id=%s bucket_name=%s object_path=%s",
                    patient.id,
                    patient.tenant_id,
                    bucket_name,
                    patient.photo_object_path,
                )
                return photo_url

        return photo_url

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

    def _validate_photo_file(
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
            content_type not in ALLOWED_PATIENT_PHOTO_CONTENT_TYPES
            or extension not in ALLOWED_PATIENT_PHOTO_EXTENSIONS
        ):
            raise AppError(
                415,
                "invalid_patient_photo_type",
                "Invalid patient photo type",
            )

        if len(content) > MAX_PATIENT_PHOTO_SIZE_BYTES:
            raise AppError(
                413,
                "patient_photo_too_large",
                "Patient photo is too large",
            )

        return self._safe_filename(original_filename)

    def _safe_filename(self, filename: str) -> str:
        name = Path(filename).name.strip()
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", name)
        name = name.strip(".-")
        return name or "patient-photo"

    def _build_photo_object_path(
        self,
        *,
        tenant_id: uuid.UUID,
        patient_id: uuid.UUID,
        safe_filename: str,
    ) -> str:
        return (
            f"tenants/{tenant_id}/patients/{patient_id}/profile-photo/"
            f"{patient_id}-{safe_filename}"
        )

    def _photo_clear_updates(self) -> dict:
        return {
            "photo_url": None,
            "photo_bucket_name": None,
            "photo_object_path": None,
            "photo_original_filename": None,
            "photo_content_type": None,
            "photo_size_bytes": None,
            "photo_uploaded_at": None,
        }

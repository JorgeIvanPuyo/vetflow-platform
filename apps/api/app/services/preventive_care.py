import uuid

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.patient import Patient
from app.models.patient_preventive_care import PatientPreventiveCare
from app.repositories.patient import PatientRepository
from app.repositories.preventive_care import PreventiveCareRepository
from app.schemas.preventive_care import (
    PREVENTIVE_CARE_TYPES,
    PreventiveCareCreate,
    PreventiveCareUpdate,
)


class PreventiveCareService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.patient_repository = PatientRepository(db)
        self.preventive_care_repository = PreventiveCareRepository(db)

    def create_preventive_care(
        self,
        tenant_id: uuid.UUID,
        patient_id: uuid.UUID,
        payload: PreventiveCareCreate,
        *,
        created_by_user_id: uuid.UUID | None = None,
    ) -> PatientPreventiveCare:
        self._get_patient_for_tenant(tenant_id, patient_id)
        self._validate_care_type(payload.care_type)

        record = PatientPreventiveCare(
            tenant_id=tenant_id,
            patient_id=patient_id,
            created_by_user_id=created_by_user_id,
            **payload.model_dump(),
        )
        self.preventive_care_repository.create(record)
        self.db.commit()
        return record

    def list_patient_preventive_care(
        self,
        tenant_id: uuid.UUID,
        patient_id: uuid.UUID,
    ) -> tuple[list[PatientPreventiveCare], int]:
        self._get_patient_for_tenant(tenant_id, patient_id)
        return self.preventive_care_repository.list_by_patient(tenant_id, patient_id)

    def get_preventive_care(
        self,
        tenant_id: uuid.UUID,
        record_id: uuid.UUID,
    ) -> PatientPreventiveCare:
        record = self.preventive_care_repository.get_by_id(tenant_id, record_id)
        if record is None:
            raise AppError(
                404,
                "preventive_care_not_found",
                "Preventive care record not found",
            )
        return record

    def update_preventive_care(
        self,
        tenant_id: uuid.UUID,
        record_id: uuid.UUID,
        payload: PreventiveCareUpdate,
    ) -> PatientPreventiveCare:
        record = self.get_preventive_care(tenant_id, record_id)
        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates and updates["name"] is None:
            raise AppError(422, "validation_error", "name cannot be null")
        if "care_type" in updates:
            self._validate_care_type(updates["care_type"])
        if "applied_at" in updates and updates["applied_at"] is None:
            raise AppError(422, "validation_error", "applied_at cannot be null")

        updated_record = self.preventive_care_repository.update(record, updates)
        self.db.commit()
        return updated_record

    def delete_preventive_care(
        self,
        tenant_id: uuid.UUID,
        record_id: uuid.UUID,
    ) -> None:
        record = self.get_preventive_care(tenant_id, record_id)
        self.preventive_care_repository.delete(record)
        self.db.commit()

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

    def _validate_care_type(self, care_type: str | None) -> None:
        if care_type is None:
            raise AppError(422, "invalid_care_type", "care_type cannot be null")
        if care_type not in PREVENTIVE_CARE_TYPES:
            raise AppError(422, "invalid_care_type", "Invalid preventive care type")

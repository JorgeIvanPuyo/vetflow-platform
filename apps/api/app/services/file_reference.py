import uuid

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.patient import Patient
from app.models.patient_file_reference import PatientFileReference
from app.repositories.file_reference import FileReferenceRepository
from app.repositories.patient import PatientRepository
from app.schemas.file_reference import FileReferenceCreate, FileReferenceUpdate


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
    ) -> PatientFileReference:
        self._get_patient_for_tenant(tenant_id, patient_id)

        file_reference = PatientFileReference(
            tenant_id=tenant_id,
            patient_id=patient_id,
            **payload.model_dump(),
        )
        self.file_reference_repository.create(file_reference)
        self.db.commit()
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
    ) -> None:
        file_reference = self.get_file_reference(tenant_id, file_reference_id)
        self.file_reference_repository.delete(file_reference)
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

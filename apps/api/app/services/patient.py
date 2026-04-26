import uuid

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.consultation import Consultation
from app.models.exam import Exam
from app.models.owner import Owner
from app.models.patient import Patient
from app.models.patient_file_reference import PatientFileReference
from app.models.patient_preventive_care import PatientPreventiveCare
from app.repositories.owner import OwnerRepository
from app.repositories.patient import PatientRepository
from app.schemas.patient import PatientCreate, PatientUpdate


class PatientService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.owner_repository = OwnerRepository(db)
        self.patient_repository = PatientRepository(db)

    def create_patient(self, tenant_id: uuid.UUID, payload: PatientCreate) -> Patient:
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

        patient = Patient(tenant_id=tenant_id, **payload.model_dump())
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

    def delete_patient(self, tenant_id: uuid.UUID, patient_id: uuid.UUID) -> None:
        patient = self.get_patient(tenant_id, patient_id)
        self.db.execute(
            delete(PatientFileReference).where(
                PatientFileReference.tenant_id == tenant_id,
                PatientFileReference.patient_id == patient_id,
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

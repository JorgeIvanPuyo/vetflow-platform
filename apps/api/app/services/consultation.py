import uuid

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.consultation import Consultation
from app.models.exam import Exam
from app.models.patient import Patient
from app.repositories.consultation import ConsultationRepository
from app.repositories.exam import ExamRepository
from app.repositories.patient import PatientRepository
from app.schemas.consultation import ConsultationCreate, ConsultationUpdate


class ConsultationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.consultation_repository = ConsultationRepository(db)
        self.exam_repository = ExamRepository(db)
        self.patient_repository = PatientRepository(db)

    def create_consultation(
        self, tenant_id: uuid.UUID, payload: ConsultationCreate
    ) -> Consultation:
        patient = self.patient_repository.get_by_id(tenant_id, payload.patient_id)
        if patient is None:
            patient_any_tenant = self.db.get(Patient, payload.patient_id)
            if patient_any_tenant is not None:
                raise AppError(
                    409,
                    "invalid_cross_tenant_access",
                    "Patient does not belong to the provided tenant",
                )
            raise AppError(
                404,
                "patient_not_found",
                "Patient not found for the provided tenant",
            )

        consultation = Consultation(tenant_id=tenant_id, **payload.model_dump())
        self.consultation_repository.create(consultation)
        self.db.commit()
        return consultation

    def get_consultation(
        self, tenant_id: uuid.UUID, consultation_id: uuid.UUID
    ) -> Consultation:
        consultation = self.consultation_repository.get_by_id(
            tenant_id,
            consultation_id,
        )
        if consultation is None:
            raise AppError(404, "consultation_not_found", "Consultation not found")
        return consultation

    def update_consultation(
        self,
        tenant_id: uuid.UUID,
        consultation_id: uuid.UUID,
        payload: ConsultationUpdate,
    ) -> Consultation:
        consultation = self.get_consultation(tenant_id, consultation_id)
        updates = payload.model_dump(exclude_unset=True)
        if "visit_date" in updates and updates["visit_date"] is None:
            raise AppError(422, "validation_error", "visit_date cannot be null")
        if "reason" in updates and updates["reason"] is None:
            raise AppError(422, "validation_error", "reason cannot be null")

        updated_consultation = self.consultation_repository.update(
            consultation,
            updates,
        )
        self.db.commit()
        return updated_consultation

    def list_patient_consultations(
        self, tenant_id: uuid.UUID, patient_id: uuid.UUID
    ) -> tuple[list[Consultation], int]:
        self._get_patient_for_tenant(tenant_id, patient_id)
        return self.consultation_repository.list_by_patient(tenant_id, patient_id)

    def get_patient_clinical_history(
        self, tenant_id: uuid.UUID, patient_id: uuid.UUID
    ) -> tuple[Patient, list[Consultation], list[Exam]]:
        patient = self._get_patient_for_tenant(tenant_id, patient_id)
        consultations, _ = self.consultation_repository.list_by_patient(
            tenant_id,
            patient_id,
        )
        exams, _ = self.exam_repository.list_by_patient(tenant_id, patient_id)
        return patient, consultations, exams

    def _get_patient_for_tenant(
        self, tenant_id: uuid.UUID, patient_id: uuid.UUID
    ) -> Patient:
        patient = self.patient_repository.get_by_id(tenant_id, patient_id)
        if patient is None:
            raise AppError(404, "patient_not_found", "Patient not found")
        return patient

import uuid

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.consultation import Consultation
from app.models.exam import Exam
from app.models.patient import Patient
from app.repositories.consultation import ConsultationRepository
from app.repositories.exam import ExamRepository
from app.repositories.patient import PatientRepository
from app.schemas.exam import EXAM_STATUSES, ExamCreate, ExamUpdate


class ExamService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.exam_repository = ExamRepository(db)
        self.patient_repository = PatientRepository(db)
        self.consultation_repository = ConsultationRepository(db)

    def create_exam(
        self,
        tenant_id: uuid.UUID,
        payload: ExamCreate,
        *,
        requested_by_user_id: uuid.UUID | None = None,
    ) -> Exam:
        self._get_patient_for_tenant(tenant_id, payload.patient_id)

        if payload.consultation_id is not None:
            consultation = self._get_consultation_for_tenant(
                tenant_id,
                payload.consultation_id,
            )
            if consultation.patient_id != payload.patient_id:
                raise AppError(
                    409,
                    "consultation_patient_mismatch",
                    "Consultation does not belong to the provided patient",
                )

        exam = Exam(
            tenant_id=tenant_id,
            requested_by_user_id=requested_by_user_id,
            status="requested",
            **payload.model_dump(),
        )
        self.exam_repository.create(exam)
        self.db.commit()
        return exam

    def get_exam(self, tenant_id: uuid.UUID, exam_id: uuid.UUID) -> Exam:
        exam = self.exam_repository.get_by_id(tenant_id, exam_id)
        if exam is None:
            raise AppError(404, "exam_not_found", "Exam not found")
        return exam

    def update_exam(
        self, tenant_id: uuid.UUID, exam_id: uuid.UUID, payload: ExamUpdate
    ) -> Exam:
        exam = self.get_exam(tenant_id, exam_id)
        updates = payload.model_dump(exclude_unset=True)

        if "exam_type" in updates and updates["exam_type"] is None:
            raise AppError(422, "validation_error", "exam_type cannot be null")
        if "status" in updates:
            self._validate_status(updates["status"])

        updated_exam = self.exam_repository.update(exam, updates)
        self.db.commit()
        return updated_exam

    def list_patient_exams(
        self, tenant_id: uuid.UUID, patient_id: uuid.UUID
    ) -> tuple[list[Exam], int]:
        self._get_patient_for_tenant(tenant_id, patient_id)
        return self.exam_repository.list_by_patient(tenant_id, patient_id)

    def list_consultation_exams(
        self, tenant_id: uuid.UUID, consultation_id: uuid.UUID
    ) -> tuple[list[Exam], int]:
        self._get_consultation_for_tenant(tenant_id, consultation_id)
        return self.exam_repository.list_by_consultation(tenant_id, consultation_id)

    def _get_patient_for_tenant(
        self, tenant_id: uuid.UUID, patient_id: uuid.UUID
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

    def _get_consultation_for_tenant(
        self, tenant_id: uuid.UUID, consultation_id: uuid.UUID
    ) -> Consultation:
        consultation = self.consultation_repository.get_by_id(
            tenant_id,
            consultation_id,
        )
        if consultation is None:
            consultation_any_tenant = self.db.get(Consultation, consultation_id)
            if consultation_any_tenant is not None:
                raise AppError(
                    409,
                    "invalid_cross_tenant_access",
                    "Consultation does not belong to the provided tenant",
                )
            raise AppError(404, "consultation_not_found", "Consultation not found")
        return consultation

    def _validate_status(self, status: str | None) -> None:
        if status is None:
            raise AppError(422, "invalid_exam_status", "status cannot be null")
        if status not in EXAM_STATUSES:
            raise AppError(422, "invalid_exam_status", "Invalid exam status")

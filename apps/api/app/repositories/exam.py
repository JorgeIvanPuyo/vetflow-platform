import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.exam import Exam


class ExamRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, exam: Exam) -> Exam:
        self.db.add(exam)
        self.db.flush()
        self.db.refresh(exam)
        return exam

    def get_by_id(self, tenant_id: uuid.UUID, exam_id: uuid.UUID) -> Exam | None:
        statement = select(Exam).where(
            Exam.id == exam_id,
            Exam.tenant_id == tenant_id,
        )
        return self.db.scalar(statement)

    def list_by_patient(
        self, tenant_id: uuid.UUID, patient_id: uuid.UUID
    ) -> tuple[list[Exam], int]:
        statement = (
            select(Exam)
            .where(
                Exam.tenant_id == tenant_id,
                Exam.patient_id == patient_id,
            )
            .order_by(Exam.requested_at.desc())
        )
        exams = list(self.db.scalars(statement).all())

        count_statement = select(func.count()).select_from(Exam).where(
            Exam.tenant_id == tenant_id,
            Exam.patient_id == patient_id,
        )
        total = self.db.scalar(count_statement) or 0
        return exams, total

    def list_by_consultation(
        self, tenant_id: uuid.UUID, consultation_id: uuid.UUID
    ) -> tuple[list[Exam], int]:
        statement = (
            select(Exam)
            .where(
                Exam.tenant_id == tenant_id,
                Exam.consultation_id == consultation_id,
            )
            .order_by(Exam.requested_at.desc())
        )
        exams = list(self.db.scalars(statement).all())

        count_statement = select(func.count()).select_from(Exam).where(
            Exam.tenant_id == tenant_id,
            Exam.consultation_id == consultation_id,
        )
        total = self.db.scalar(count_statement) or 0
        return exams, total

    def update(self, exam: Exam, updates: dict) -> Exam:
        for field, value in updates.items():
            setattr(exam, field, value)

        self.db.add(exam)
        self.db.flush()
        self.db.refresh(exam)
        return exam

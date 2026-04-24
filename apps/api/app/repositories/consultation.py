import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.consultation import Consultation


class ConsultationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, consultation: Consultation) -> Consultation:
        self.db.add(consultation)
        self.db.flush()
        self.db.refresh(consultation)
        return consultation

    def get_by_id(
        self, tenant_id: uuid.UUID, consultation_id: uuid.UUID
    ) -> Consultation | None:
        statement = select(Consultation).where(
            Consultation.id == consultation_id,
            Consultation.tenant_id == tenant_id,
        )
        return self.db.scalar(statement)

    def list_by_patient(
        self, tenant_id: uuid.UUID, patient_id: uuid.UUID
    ) -> tuple[list[Consultation], int]:
        statement = (
            select(Consultation)
            .where(
                Consultation.tenant_id == tenant_id,
                Consultation.patient_id == patient_id,
            )
            .order_by(Consultation.visit_date.desc())
        )
        consultations = list(self.db.scalars(statement).all())

        count_statement = select(func.count()).select_from(Consultation).where(
            Consultation.tenant_id == tenant_id,
            Consultation.patient_id == patient_id,
        )
        total = self.db.scalar(count_statement) or 0
        return consultations, total

    def update(self, consultation: Consultation, updates: dict) -> Consultation:
        for field, value in updates.items():
            setattr(consultation, field, value)

        self.db.add(consultation)
        self.db.flush()
        self.db.refresh(consultation)
        return consultation

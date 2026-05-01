import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.patient_preventive_care import PatientPreventiveCare


class PreventiveCareRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, record: PatientPreventiveCare) -> PatientPreventiveCare:
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def get_by_id(
        self, tenant_id: uuid.UUID, record_id: uuid.UUID
    ) -> PatientPreventiveCare | None:
        statement = select(PatientPreventiveCare).where(
            PatientPreventiveCare.id == record_id,
            PatientPreventiveCare.tenant_id == tenant_id,
        ).options(selectinload(PatientPreventiveCare.created_by_user))
        return self.db.scalar(statement)

    def list_by_patient(
        self, tenant_id: uuid.UUID, patient_id: uuid.UUID
    ) -> tuple[list[PatientPreventiveCare], int]:
        statement = (
            select(PatientPreventiveCare)
            .where(
                PatientPreventiveCare.tenant_id == tenant_id,
                PatientPreventiveCare.patient_id == patient_id,
            )
            .options(selectinload(PatientPreventiveCare.created_by_user))
            .order_by(PatientPreventiveCare.applied_at.desc())
        )
        records = list(self.db.scalars(statement).all())

        count_statement = select(func.count()).select_from(PatientPreventiveCare).where(
            PatientPreventiveCare.tenant_id == tenant_id,
            PatientPreventiveCare.patient_id == patient_id,
        )
        total = self.db.scalar(count_statement) or 0
        return records, total

    def update(
        self,
        record: PatientPreventiveCare,
        updates: dict,
    ) -> PatientPreventiveCare:
        for field, value in updates.items():
            setattr(record, field, value)

        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def delete(self, record: PatientPreventiveCare) -> None:
        self.db.delete(record)
        self.db.flush()

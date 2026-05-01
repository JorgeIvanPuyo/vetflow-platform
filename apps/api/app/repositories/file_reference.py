import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.patient_file_reference import PatientFileReference


class FileReferenceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, file_reference: PatientFileReference) -> PatientFileReference:
        self.db.add(file_reference)
        self.db.flush()
        self.db.refresh(file_reference)
        return file_reference

    def get_by_id(
        self, tenant_id: uuid.UUID, file_reference_id: uuid.UUID
    ) -> PatientFileReference | None:
        statement = select(PatientFileReference).where(
            PatientFileReference.id == file_reference_id,
            PatientFileReference.tenant_id == tenant_id,
        ).options(selectinload(PatientFileReference.created_by_user))
        return self.db.scalar(statement)

    def list_by_patient(
        self, tenant_id: uuid.UUID, patient_id: uuid.UUID
    ) -> tuple[list[PatientFileReference], int]:
        statement = (
            select(PatientFileReference)
            .where(
                PatientFileReference.tenant_id == tenant_id,
                PatientFileReference.patient_id == patient_id,
            )
            .options(selectinload(PatientFileReference.created_by_user))
            .order_by(PatientFileReference.created_at.desc())
        )
        file_references = list(self.db.scalars(statement).all())

        count_statement = select(func.count()).select_from(PatientFileReference).where(
            PatientFileReference.tenant_id == tenant_id,
            PatientFileReference.patient_id == patient_id,
        )
        total = self.db.scalar(count_statement) or 0
        return file_references, total

    def update(
        self,
        file_reference: PatientFileReference,
        updates: dict,
    ) -> PatientFileReference:
        for field, value in updates.items():
            setattr(file_reference, field, value)

        self.db.add(file_reference)
        self.db.flush()
        self.db.refresh(file_reference)
        return file_reference

    def delete(self, file_reference: PatientFileReference) -> None:
        self.db.delete(file_reference)
        self.db.flush()

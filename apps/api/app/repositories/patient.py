import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.patient import Patient


class PatientRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, patient: Patient) -> Patient:
        self.db.add(patient)
        self.db.flush()
        self.db.refresh(patient)
        return patient

    def get_by_id(self, tenant_id: uuid.UUID, patient_id: uuid.UUID) -> Patient | None:
        statement = select(Patient).where(
            Patient.id == patient_id,
            Patient.tenant_id == tenant_id,
        ).options(selectinload(Patient.created_by_user))
        return self.db.scalar(statement)

    def list(
        self,
        tenant_id: uuid.UUID,
        *,
        owner_id: uuid.UUID | None = None,
        species: str | None = None,
        search: str | None = None,
    ) -> tuple[list[Patient], int]:
        statement: Select[tuple[Patient]] = select(Patient).where(
            Patient.tenant_id == tenant_id
        ).options(selectinload(Patient.created_by_user))

        if owner_id:
            statement = statement.where(Patient.owner_id == owner_id)
        if species:
            statement = statement.where(Patient.species.ilike(species))
        if search:
            statement = statement.where(Patient.name.ilike(f"%{search}%"))

        statement = statement.order_by(Patient.created_at.desc())
        patients = list(self.db.scalars(statement).all())

        count_statement = select(func.count()).select_from(Patient).where(
            Patient.tenant_id == tenant_id
        )
        if owner_id:
            count_statement = count_statement.where(Patient.owner_id == owner_id)
        if species:
            count_statement = count_statement.where(Patient.species.ilike(species))
        if search:
            count_statement = count_statement.where(Patient.name.ilike(f"%{search}%"))

        total = self.db.scalar(count_statement) or 0
        return patients, total

    def update(self, patient: Patient, updates: dict) -> Patient:
        for field, value in updates.items():
            setattr(patient, field, value)

        self.db.add(patient)
        self.db.flush()
        self.db.refresh(patient)
        return patient

    def delete(self, patient: Patient) -> None:
        self.db.delete(patient)
        self.db.flush()

    def exists_for_owner(self, tenant_id: uuid.UUID, owner_id: uuid.UUID) -> bool:
        statement = select(Patient.id).where(
            Patient.tenant_id == tenant_id,
            Patient.owner_id == owner_id,
        )
        return self.db.scalar(statement) is not None

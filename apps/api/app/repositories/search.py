import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.owner import Owner
from app.models.patient import Patient


class SearchRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def search_owners(self, tenant_id: uuid.UUID, query: str, limit: int) -> list[Owner]:
        statement = (
            select(Owner)
            .where(
                Owner.tenant_id == tenant_id,
                or_(
                    Owner.full_name.ilike(f"%{query}%"),
                    Owner.phone.ilike(f"%{query}%"),
                ),
            )
            .order_by(Owner.full_name.asc())
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def search_patients(
        self, tenant_id: uuid.UUID, query: str, limit: int
    ) -> list[tuple[Patient, str]]:
        statement = (
            select(Patient, Owner.full_name)
            .join(Owner, Patient.owner_id == Owner.id)
            .where(
                Patient.tenant_id == tenant_id,
                Owner.tenant_id == tenant_id,
                Patient.name.ilike(f"%{query}%"),
            )
            .order_by(Patient.name.asc())
            .limit(limit)
        )
        return list(self.db.execute(statement).all())

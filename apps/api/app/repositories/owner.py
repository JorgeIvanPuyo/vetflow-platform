import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.owner import Owner


class OwnerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, owner: Owner) -> Owner:
        self.db.add(owner)
        self.db.flush()
        self.db.refresh(owner)
        return owner

    def get_by_id(self, tenant_id: uuid.UUID, owner_id: uuid.UUID) -> Owner | None:
        statement = select(Owner).where(
            Owner.id == owner_id,
            Owner.tenant_id == tenant_id,
        )
        return self.db.scalar(statement)

    def list(
        self,
        tenant_id: uuid.UUID,
        *,
        search: str | None = None,
        phone: str | None = None,
    ) -> tuple[list[Owner], int]:
        statement: Select[tuple[Owner]] = select(Owner).where(Owner.tenant_id == tenant_id)

        if search:
            statement = statement.where(Owner.full_name.ilike(f"%{search}%"))
        if phone:
            statement = statement.where(Owner.phone.ilike(f"%{phone}%"))

        statement = statement.order_by(Owner.created_at.desc())
        owners = list(self.db.scalars(statement).all())

        count_statement = select(func.count()).select_from(Owner).where(
            Owner.tenant_id == tenant_id
        )
        if search:
            count_statement = count_statement.where(Owner.full_name.ilike(f"%{search}%"))
        if phone:
            count_statement = count_statement.where(Owner.phone.ilike(f"%{phone}%"))

        total = self.db.scalar(count_statement) or 0
        return owners, total

    def update(self, owner: Owner, updates: dict) -> Owner:
        for field, value in updates.items():
            setattr(owner, field, value)

        self.db.add(owner)
        self.db.flush()
        self.db.refresh(owner)
        return owner

    def delete(self, owner: Owner) -> None:
        self.db.delete(owner)
        self.db.flush()

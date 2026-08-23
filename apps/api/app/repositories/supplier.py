from __future__ import annotations

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.supplier import Supplier


class SupplierRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, supplier: Supplier) -> Supplier:
        self.db.add(supplier)
        self.db.flush()
        self.db.refresh(supplier)
        return supplier

    def get_by_id(self, tenant_id: uuid.UUID, supplier_id: uuid.UUID) -> Supplier | None:
        statement = (
            select(Supplier)
            .where(
                Supplier.id == supplier_id,
                Supplier.tenant_id == tenant_id,
            )
            .options(selectinload(Supplier.created_by_user))
        )
        return self.db.scalar(statement)

    def get_active_by_normalized_name(
        self,
        tenant_id: uuid.UUID,
        normalized_name: str,
    ) -> Supplier | None:
        statement = select(Supplier).where(
            Supplier.tenant_id == tenant_id,
            Supplier.normalized_name == normalized_name,
            Supplier.is_active.is_(True),
        )
        return self.db.scalar(statement)

    def list(self, tenant_id: uuid.UUID, *, include_inactive: bool) -> list[Supplier]:
        statement: Select[tuple[Supplier]] = (
            select(Supplier)
            .where(Supplier.tenant_id == tenant_id)
            .options(selectinload(Supplier.created_by_user))
        )
        if not include_inactive:
            statement = statement.where(Supplier.is_active.is_(True))
        return list(
            self.db.scalars(statement.order_by(func.lower(Supplier.name).asc())).all()
        )

    def update(self, supplier: Supplier, updates: dict) -> Supplier:
        for field, value in updates.items():
            setattr(supplier, field, value)
        self.db.add(supplier)
        self.db.flush()
        self.db.refresh(supplier)
        return supplier

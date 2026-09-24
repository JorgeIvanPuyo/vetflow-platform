from __future__ import annotations

import uuid

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.supplier import Supplier
from app.models.user import User


class SupplierRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, supplier: Supplier) -> Supplier:
        self.db.add(supplier)
        self.db.flush()
        self.db.refresh(supplier)
        return supplier

    def get_by_id(
        self,
        tenant_id: uuid.UUID,
        supplier_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> Supplier | None:
        statement = (
            select(Supplier)
            .where(
                Supplier.tenant_id == tenant_id,
                Supplier.id == supplier_id,
            )
            .options(
                selectinload(
                    Supplier.created_by_user.and_(User.tenant_id == tenant_id)
                )
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def get_by_normalized_name(
        self,
        tenant_id: uuid.UUID,
        normalized_name: str,
        *,
        active_only: bool = False,
    ) -> Supplier | None:
        statement = select(Supplier).where(
            Supplier.tenant_id == tenant_id,
            Supplier.normalized_name == normalized_name,
        )
        if active_only:
            statement = statement.where(Supplier.is_active.is_(True))
        return self.db.scalars(
            statement.order_by(Supplier.is_active.desc(), Supplier.updated_at.desc())
        ).first()

    def get_active_by_normalized_name(
        self,
        tenant_id: uuid.UUID,
        normalized_name: str,
    ) -> Supplier | None:
        return self.get_by_normalized_name(
            tenant_id,
            normalized_name,
            active_only=True,
        )

    def get_by_tax_id(self, tenant_id: uuid.UUID, tax_id: str) -> Supplier | None:
        return self.db.scalar(
            select(Supplier).where(
                Supplier.tenant_id == tenant_id,
                Supplier.tax_id == tax_id,
            )
        )

    def list(
        self,
        tenant_id: uuid.UUID,
        *,
        search: str | None,
        is_active: bool | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_direction: str,
    ) -> tuple[list[Supplier], int]:
        filters = [Supplier.tenant_id == tenant_id]
        if is_active is not None:
            filters.append(Supplier.is_active == is_active)
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    Supplier.name.ilike(pattern),
                    Supplier.tax_id.ilike(pattern),
                    Supplier.email.ilike(pattern),
                )
            )

        sort_column = Supplier.name if sort_by == "name" else Supplier.updated_at
        order = asc(sort_column) if sort_direction == "asc" else desc(sort_column)
        statement = (
            select(Supplier)
            .where(*filters)
            .options(
                selectinload(
                    Supplier.created_by_user.and_(User.tenant_id == tenant_id)
                )
            )
            .order_by(order, Supplier.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = list(self.db.scalars(statement).all())
        total = int(
            self.db.scalar(select(func.count()).select_from(Supplier).where(*filters)) or 0
        )
        return rows, total

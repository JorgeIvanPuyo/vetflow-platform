from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import asc, desc, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.inventory_item import InventoryItem
from app.models.sale import Sale, SaleItem
from app.models.user import User


class SaleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, sale: Sale) -> Sale:
        self.db.add(sale)
        self.db.flush()
        return sale

    def save(self, sale: Sale) -> Sale:
        self.db.add(sale)
        self.db.flush()
        return sale

    def replace_items(self, sale: Sale, items: list[SaleItem]) -> None:
        sale.items.clear()
        self.db.flush()
        sale.items.extend(items)
        self.db.add(sale)
        self.db.flush()

    def get_by_id(self, tenant_id: uuid.UUID, sale_id: uuid.UUID, *, for_update: bool = False) -> Sale | None:
        statement = (
            select(Sale)
            .where(Sale.id == sale_id, Sale.tenant_id == tenant_id)
            .options(
                selectinload(Sale.items.and_(SaleItem.tenant_id == tenant_id)),
                selectinload(Sale.created_by_user.and_(User.tenant_id == tenant_id)),
                selectinload(Sale.cancelled_by_user.and_(User.tenant_id == tenant_id)),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list_inventory_items(self, tenant_id: uuid.UUID, ids: list[uuid.UUID]) -> list[InventoryItem]:
        if not ids:
            return []
        return list(self.db.scalars(select(InventoryItem).where(InventoryItem.tenant_id == tenant_id, InventoryItem.id.in_(ids))).all())

    def list(
        self,
        tenant_id: uuid.UUID,
        *,
        search: str | None,
        owner_id: uuid.UUID | None,
        patient_id: uuid.UUID | None,
        status: str | None,
        line_type: str | None,
        date_from: date | None,
        date_to: date | None,
        created_by_user_id: uuid.UUID | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_direction: str,
    ) -> tuple[list[tuple[Sale, int]], int]:
        filters = [Sale.tenant_id == tenant_id]
        if search:
            pattern = f"%{search}%"
            line_match = exists(select(SaleItem.id).where(SaleItem.tenant_id == tenant_id, SaleItem.sale_id == Sale.id, SaleItem.description_snapshot.ilike(pattern)))
            filters.append(or_(Sale.owner_name_snapshot.ilike(pattern), Sale.patient_name_snapshot.ilike(pattern), line_match))
        if owner_id:
            filters.append(Sale.owner_id == owner_id)
        if patient_id:
            filters.append(Sale.patient_id == patient_id)
        if status:
            filters.append(Sale.status == status)
        if line_type:
            filters.append(exists(select(SaleItem.id).where(SaleItem.tenant_id == tenant_id, SaleItem.sale_id == Sale.id, SaleItem.line_type == line_type)))
        if date_from:
            filters.append(Sale.sale_date >= date_from)
        if date_to:
            filters.append(Sale.sale_date <= date_to)
        if created_by_user_id:
            filters.append(Sale.created_by_user_id == created_by_user_id)

        item_count = select(func.count(SaleItem.id)).where(SaleItem.tenant_id == tenant_id, SaleItem.sale_id == Sale.id).correlate(Sale).scalar_subquery()
        sort_columns = {"sale_date": Sale.sale_date, "created_at": Sale.created_at, "total_ars": Sale.total_ars, "status": Sale.status}
        order = asc if sort_direction == "asc" else desc
        statement = (
            select(Sale, item_count.label("item_count"))
            .where(*filters)
            .options(selectinload(Sale.created_by_user.and_(User.tenant_id == tenant_id)))
            .order_by(order(sort_columns[sort_by]), order(Sale.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        count_statement = select(func.count(Sale.id)).where(*filters)
        rows = self.db.execute(statement).all()
        return [(row[0], int(row[1] or 0)) for row in rows], int(self.db.scalar(count_statement) or 0)

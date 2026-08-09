from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.inventory_item import InventoryItem
from app.models.purchase import Purchase, PurchaseItem
from app.models.supplier import Supplier
from app.models.user import User


class PurchaseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_inventory_items_by_ids(
        self, tenant_id: uuid.UUID, inventory_item_ids: list[uuid.UUID]
    ) -> list[InventoryItem]:
        if not inventory_item_ids:
            return []
        statement = select(InventoryItem).where(
            InventoryItem.tenant_id == tenant_id,
            InventoryItem.id.in_(inventory_item_ids),
        )
        return list(self.db.scalars(statement).all())

    def create(self, purchase: Purchase) -> Purchase:
        self.db.add(purchase)
        self.db.flush()
        return purchase

    def get_by_id(
        self,
        tenant_id: uuid.UUID,
        purchase_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> Purchase | None:
        statement = (
            select(Purchase)
            .where(Purchase.id == purchase_id, Purchase.tenant_id == tenant_id)
            .options(
                selectinload(
                    Purchase.items.and_(PurchaseItem.tenant_id == tenant_id)
                ),
                selectinload(
                    Purchase.created_by_user.and_(User.tenant_id == tenant_id)
                ),
                selectinload(
                    Purchase.cancelled_by_user.and_(User.tenant_id == tenant_id)
                ),
                selectinload(Purchase.supplier.and_(Supplier.tenant_id == tenant_id)),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list(
        self,
        tenant_id: uuid.UUID,
        *,
        search: str | None,
        supplier: str | None,
        supplier_id: uuid.UUID | None,
        status: str | None,
        document_type: str | None,
        date_from: date | None,
        date_to: date | None,
        created_by_user_id: uuid.UUID | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_direction: str,
    ) -> tuple[list[tuple[Purchase, int]], int]:
        item_count = (
            select(func.count(PurchaseItem.id))
            .where(
                PurchaseItem.purchase_id == Purchase.id,
                PurchaseItem.tenant_id == tenant_id,
            )
            .correlate(Purchase)
            .scalar_subquery()
        )
        statement = (
            select(Purchase, item_count.label("item_count"))
            .where(Purchase.tenant_id == tenant_id)
            .options(
                selectinload(
                    Purchase.created_by_user.and_(User.tenant_id == tenant_id)
                )
            )
        )
        count_statement = select(func.count(Purchase.id)).where(Purchase.tenant_id == tenant_id)

        filters = []
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    Purchase.supplier_name.ilike(pattern),
                    Purchase.document_number.ilike(pattern),
                )
            )
        if supplier:
            filters.append(func.lower(Purchase.supplier_name) == supplier.lower())
        if supplier_id:
            filters.append(Purchase.supplier_id == supplier_id)
        if status:
            filters.append(Purchase.status == status)
        if document_type:
            filters.append(Purchase.document_type == document_type)
        if date_from:
            filters.append(Purchase.purchase_date >= date_from)
        if date_to:
            filters.append(Purchase.purchase_date <= date_to)
        if created_by_user_id:
            filters.append(Purchase.created_by_user_id == created_by_user_id)
        if filters:
            statement = statement.where(*filters)
            count_statement = count_statement.where(*filters)

        sort_columns = {
            "purchase_date": Purchase.purchase_date,
            "created_at": Purchase.created_at,
            "total_ars": Purchase.total_ars,
            "supplier_name": func.lower(Purchase.supplier_name),
        }
        order = asc if sort_direction == "asc" else desc
        statement = statement.order_by(order(sort_columns[sort_by]), order(Purchase.id))
        statement = statement.offset((page - 1) * page_size).limit(page_size)
        rows = self.db.execute(statement).all()
        return [(row[0], int(row[1] or 0)) for row in rows], int(
            self.db.scalar(count_statement) or 0
        )

    def replace_items(self, purchase: Purchase, items: list[PurchaseItem]) -> None:
        purchase.items.clear()
        self.db.flush()
        purchase.items.extend(items)
        self.db.add(purchase)
        self.db.flush()

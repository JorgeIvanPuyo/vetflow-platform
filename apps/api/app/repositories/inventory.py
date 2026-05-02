from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import Select, asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement


class InventoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_item(self, item: InventoryItem) -> InventoryItem:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_item_by_id(
        self,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> InventoryItem | None:
        statement = (
            select(InventoryItem)
            .where(
                InventoryItem.id == item_id,
                InventoryItem.tenant_id == tenant_id,
            )
            .options(selectinload(InventoryItem.created_by_user))
        )
        return self.db.scalar(statement)

    def list_items(
        self,
        tenant_id: uuid.UUID,
        *,
        q: str | None,
        category: str | None,
        supplier: str | None,
        status: str | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> tuple[list[InventoryItem], int]:
        statement: Select[tuple[InventoryItem]] = (
            select(InventoryItem)
            .where(InventoryItem.tenant_id == tenant_id)
            .options(selectinload(InventoryItem.created_by_user))
        )
        count_statement = select(func.count()).select_from(InventoryItem).where(
            InventoryItem.tenant_id == tenant_id,
        )

        statement = self._apply_item_filters(
            statement,
            q=q,
            category=category,
            supplier=supplier,
            status=status,
        )
        count_statement = self._apply_item_filters(
            count_statement,
            q=q,
            category=category,
            supplier=supplier,
            status=status,
        )

        sort_column = self._get_sort_column(sort_by)
        order_by = desc(sort_column) if sort_order == "desc" else asc(sort_column)
        offset = (page - 1) * page_size

        items = list(
            self.db.scalars(
                statement.order_by(order_by, InventoryItem.name.asc()).offset(offset).limit(page_size)
            ).all()
        )
        total = int(self.db.scalar(count_statement) or 0)
        return items, total

    def update_item(self, item: InventoryItem, updates: dict) -> InventoryItem:
        for field, value in updates.items():
            setattr(item, field, value)
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def summarize_items(self, tenant_id: uuid.UUID) -> dict[str, int]:
        today = date.today()
        expiring_limit = today + timedelta(days=30)
        base = InventoryItem.tenant_id == tenant_id
        active = InventoryItem.is_active.is_(True)
        low_stock = InventoryItem.current_stock <= InventoryItem.minimum_stock
        expired = InventoryItem.expiration_date.is_not(None) & (InventoryItem.expiration_date < today)
        expiring_soon = (
            InventoryItem.expiration_date.is_not(None)
            & (InventoryItem.expiration_date >= today)
            & (InventoryItem.expiration_date <= expiring_limit)
        )

        return {
            "total_items": int(
                self.db.scalar(
                    select(func.count()).select_from(InventoryItem).where(base, active)
                )
                or 0
            ),
            "low_stock_count": int(
                self.db.scalar(
                    select(func.count()).select_from(InventoryItem).where(base, active, low_stock)
                )
                or 0
            ),
            "expiring_soon_count": int(
                self.db.scalar(
                    select(func.count()).select_from(InventoryItem).where(
                        base,
                        active,
                        expiring_soon,
                    )
                )
                or 0
            ),
            "expired_count": int(
                self.db.scalar(
                    select(func.count()).select_from(InventoryItem).where(base, active, expired)
                )
                or 0
            ),
        }

    def create_movement(self, movement: InventoryMovement) -> InventoryMovement:
        self.db.add(movement)
        self.db.flush()
        self.db.refresh(movement)
        return movement

    def list_movements(
        self,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
        movement_type: str | None,
    ) -> tuple[list[InventoryMovement], int]:
        statement: Select[tuple[InventoryMovement]] = (
            select(InventoryMovement)
            .where(
                InventoryMovement.tenant_id == tenant_id,
                InventoryMovement.inventory_item_id == item_id,
            )
            .options(selectinload(InventoryMovement.created_by_user))
        )
        count_statement = select(func.count()).select_from(InventoryMovement).where(
            InventoryMovement.tenant_id == tenant_id,
            InventoryMovement.inventory_item_id == item_id,
        )
        if movement_type is not None:
            statement = statement.where(InventoryMovement.movement_type == movement_type)
            count_statement = count_statement.where(
                InventoryMovement.movement_type == movement_type
            )

        offset = (page - 1) * page_size
        movements = list(
            self.db.scalars(
                statement.order_by(InventoryMovement.created_at.desc()).offset(offset).limit(page_size)
            ).all()
        )
        total = int(self.db.scalar(count_statement) or 0)
        return movements, total

    def _apply_item_filters(
        self,
        statement,
        *,
        q: str | None,
        category: str | None,
        supplier: str | None,
        status: str | None,
    ):
        today = date.today()
        expiring_limit = today + timedelta(days=30)

        if q:
            pattern = f"%{q.strip().lower()}%"
            statement = statement.where(
                or_(
                    func.lower(InventoryItem.name).like(pattern),
                    func.lower(func.coalesce(InventoryItem.subcategory, "")).like(pattern),
                    func.lower(func.coalesce(InventoryItem.supplier, "")).like(pattern),
                    func.lower(func.coalesce(InventoryItem.lot_number, "")).like(pattern),
                )
            )
        if category is not None:
            statement = statement.where(InventoryItem.category == category)
        if supplier is not None:
            statement = statement.where(func.lower(InventoryItem.supplier) == supplier.lower())
        if status == "low_stock":
            statement = statement.where(
                InventoryItem.is_active.is_(True),
                InventoryItem.current_stock <= InventoryItem.minimum_stock,
            )
        elif status == "expiring_soon":
            statement = statement.where(
                InventoryItem.is_active.is_(True),
                InventoryItem.expiration_date.is_not(None),
                InventoryItem.expiration_date >= today,
                InventoryItem.expiration_date <= expiring_limit,
            )
        elif status == "expired":
            statement = statement.where(
                InventoryItem.is_active.is_(True),
                InventoryItem.expiration_date.is_not(None),
                InventoryItem.expiration_date < today,
            )
        elif status == "inactive":
            statement = statement.where(InventoryItem.is_active.is_(False))
        else:
            statement = statement.where(InventoryItem.is_active.is_(True))
        return statement

    def _get_sort_column(self, sort_by: str):
        mapping = {
            "name": InventoryItem.name,
            "current_stock": InventoryItem.current_stock,
            "expiration_date": InventoryItem.expiration_date,
            "created_at": InventoryItem.created_at,
            "updated_at": InventoryItem.updated_at,
        }
        return mapping[sort_by]

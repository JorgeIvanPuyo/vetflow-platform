from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import Select, asc, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.inventory_code_sequence import InventoryCodeSequence
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

    def get_next_internal_code(
        self,
        tenant_id: uuid.UUID,
        category: str,
        prefix: str,
    ) -> str:
        sequence = self._get_code_sequence_for_update(tenant_id, category)
        if sequence is None:
            try:
                with self.db.begin_nested():
                    sequence = InventoryCodeSequence(
                        tenant_id=tenant_id,
                        category=category,
                        last_value=0,
                    )
                    self.db.add(sequence)
                    self.db.flush()
            except IntegrityError:
                sequence = None

        if sequence is None:
            sequence = self._get_code_sequence_for_update(tenant_id, category)
        if sequence is None:
            raise RuntimeError("Inventory code sequence could not be created")

        sequence.last_value += 1
        self.db.add(sequence)
        self.db.flush()
        return f"{prefix}-{sequence.last_value:05d}"

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
        search: str | None,
        category: str | None,
        brand: str | None,
        supplier: str | None,
        status: str | None,
        stock_status: str | None,
        is_active: bool | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_direction: str,
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
            search=search,
            category=category,
            brand=brand,
            supplier=supplier,
            status=status,
            stock_status=stock_status,
            is_active=is_active,
        )
        count_statement = self._apply_item_filters(
            count_statement,
            search=search,
            category=category,
            brand=brand,
            supplier=supplier,
            status=status,
            stock_status=stock_status,
            is_active=is_active,
        )

        sort_column = self._get_sort_column(sort_by)
        order_by = desc(sort_column) if sort_direction == "desc" else asc(sort_column)
        offset = (page - 1) * page_size

        items = list(
            self.db.scalars(
                statement.order_by(order_by, InventoryItem.id.asc()).offset(offset).limit(page_size)
            ).all()
        )
        total = int(self.db.scalar(count_statement) or 0)
        return items, total

    def get_filter_options(self, tenant_id: uuid.UUID) -> dict[str, list[str]]:
        brand_values = (
            select(func.distinct(InventoryItem.brand).label("value"))
            .where(
                InventoryItem.tenant_id == tenant_id,
                InventoryItem.is_active.is_(True),
                InventoryItem.brand.is_not(None),
                func.trim(InventoryItem.brand) != "",
            )
            .subquery()
        )
        supplier_values = (
            select(func.distinct(InventoryItem.supplier).label("value"))
            .where(
                InventoryItem.tenant_id == tenant_id,
                InventoryItem.is_active.is_(True),
                InventoryItem.supplier.is_not(None),
                func.trim(InventoryItem.supplier) != "",
            )
            .subquery()
        )
        brand_statement = select(brand_values.c.value).order_by(
            func.lower(brand_values.c.value).asc()
        )
        supplier_statement = select(supplier_values.c.value).order_by(
            func.lower(supplier_values.c.value).asc()
        )
        return {
            "brands": self._normalize_filter_option_values(
                self.db.scalars(brand_statement).all()
            ),
            "suppliers": self._normalize_filter_option_values(
                self.db.scalars(supplier_statement).all()
            ),
        }

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
        search: str | None,
        category: str | None,
        brand: str | None,
        supplier: str | None,
        status: str | None,
        stock_status: str | None,
        is_active: bool | None,
    ):
        today = date.today()
        expiring_limit = today + timedelta(days=30)

        if search:
            pattern = f"%{search.strip().lower()}%"
            statement = statement.where(
                or_(
                    func.lower(InventoryItem.name).like(pattern),
                    func.lower(InventoryItem.internal_code).like(pattern),
                )
            )
        if category is not None:
            statement = statement.where(InventoryItem.category == category)
        if brand is not None:
            statement = statement.where(func.lower(func.trim(InventoryItem.brand)) == brand.lower())
        if supplier is not None:
            statement = statement.where(
                func.lower(func.trim(InventoryItem.supplier)) == supplier.lower()
            )

        if stock_status == "in_stock":
            statement = statement.where(InventoryItem.current_stock > InventoryItem.minimum_stock)
        elif stock_status == "low_stock":
            statement = statement.where(
                InventoryItem.current_stock > 0,
                InventoryItem.current_stock <= InventoryItem.minimum_stock,
            )
        elif stock_status == "out_of_stock":
            statement = statement.where(InventoryItem.current_stock == 0)
        elif stock_status == "negative":
            statement = statement.where(InventoryItem.current_stock < 0)

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
        elif status == "active":
            statement = statement.where(InventoryItem.is_active.is_(True))
        elif is_active is not None:
            statement = statement.where(InventoryItem.is_active.is_(is_active))
        else:
            statement = statement.where(InventoryItem.is_active.is_(True))
        return statement

    def _get_sort_column(self, sort_by: str):
        mapping = {
            "name": func.lower(InventoryItem.name),
            "internal_code": func.lower(InventoryItem.internal_code),
            "current_stock": InventoryItem.current_stock,
            "sale_price_ars": InventoryItem.sale_price_ars,
            "updated_at": InventoryItem.updated_at,
            "created_at": InventoryItem.created_at,
        }
        return mapping[sort_by]

    def _normalize_filter_option_values(self, values) -> list[str]:
        options_by_key: dict[str, str] = {}
        for value in values:
            if not value:
                continue
            option = value.strip()
            if not option:
                continue
            key = option.lower()
            options_by_key.setdefault(key, option)
        return sorted(
            options_by_key.values(),
            key=lambda option: option.casefold(),
        )

    def _get_code_sequence_for_update(
        self,
        tenant_id: uuid.UUID,
        category: str,
    ) -> InventoryCodeSequence | None:
        return self.db.scalar(
            select(InventoryCodeSequence)
            .where(
                InventoryCodeSequence.tenant_id == tenant_id,
                InventoryCodeSequence.category == category,
            )
            .with_for_update()
        )

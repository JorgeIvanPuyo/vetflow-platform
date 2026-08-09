from __future__ import annotations

import uuid
from datetime import date, timedelta
from datetime import datetime

from sqlalchemy import Select, and_, asc, case, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, selectinload

from app.models.inventory_bulk_operation import (
    InventoryBulkOperation,
    InventoryBulkOperationItem,
)
from app.models.inventory_code_sequence import InventoryCodeSequence
from app.models.inventory_import import InventoryImport, InventoryImportRow
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

    def get_item_by_id_for_update(
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
            .with_for_update()
        )
        return self.db.scalar(statement)

    def list_items_by_ids_for_update(
        self,
        tenant_id: uuid.UUID,
        item_ids: list[uuid.UUID],
    ) -> list[InventoryItem]:
        if not item_ids:
            return []
        statement = (
            select(InventoryItem)
            .where(
                InventoryItem.tenant_id == tenant_id,
                InventoryItem.id.in_(item_ids),
            )
            .order_by(InventoryItem.id.asc())
            .with_for_update()
        )
        return list(self.db.scalars(statement).all())

    def list_items_for_import_matching(
        self,
        tenant_id: uuid.UUID,
        *,
        internal_codes: set[str],
        names: set[str],
    ) -> list[InventoryItem]:
        conditions = []
        if internal_codes:
            conditions.append(func.lower(InventoryItem.internal_code).in_(internal_codes))
        if names:
            conditions.append(func.lower(func.trim(InventoryItem.name)).in_(names))
        if not conditions:
            return []
        statement = select(InventoryItem).where(
            InventoryItem.tenant_id == tenant_id,
            or_(*conditions),
        )
        return list(self.db.scalars(statement).all())

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
        statement = self._build_item_list_statement(
            tenant_id,
            search=search,
            category=category,
            brand=brand,
            supplier=supplier,
            status=status,
            stock_status=stock_status,
            is_active=is_active,
            sort_by=sort_by,
            sort_direction=sort_direction,
        ).options(selectinload(InventoryItem.created_by_user))
        count_statement = self._build_item_count_statement(
            tenant_id,
            search=search,
            category=category,
            brand=brand,
            supplier=supplier,
            status=status,
            stock_status=stock_status,
            is_active=is_active,
        )

        offset = (page - 1) * page_size
        items = list(self.db.scalars(statement.offset(offset).limit(page_size)).all())
        total = int(self.db.scalar(count_statement) or 0)
        return items, total

    def list_items_for_export(
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
        sort_by: str,
        sort_direction: str,
        limit: int,
    ) -> tuple[list[InventoryItem], int]:
        statement = self._build_item_list_statement(
            tenant_id,
            search=search,
            category=category,
            brand=brand,
            supplier=supplier,
            status=status,
            stock_status=stock_status,
            is_active=is_active,
            sort_by=sort_by,
            sort_direction=sort_direction,
        ).limit(limit)
        count_statement = self._build_item_count_statement(
            tenant_id,
            search=search,
            category=category,
            brand=brand,
            supplier=supplier,
            status=status,
            stock_status=stock_status,
            is_active=is_active,
        )
        return list(self.db.scalars(statement).all()), int(self.db.scalar(count_statement) or 0)

    def list_items_by_ids_for_export(
        self,
        tenant_id: uuid.UUID,
        item_ids: list[uuid.UUID],
    ) -> list[InventoryItem]:
        if not item_ids:
            return []
        statement = select(InventoryItem).where(
            InventoryItem.tenant_id == tenant_id,
            InventoryItem.id.in_(item_ids),
        )
        items_by_id = {item.id: item for item in self.db.scalars(statement).all()}
        return [items_by_id[item_id] for item_id in item_ids if item_id in items_by_id]

    def list_items_by_ids_for_bulk(
        self,
        tenant_id: uuid.UUID,
        item_ids: list[uuid.UUID],
        *,
        excluded_ids: set[uuid.UUID] | None = None,
        for_update: bool = False,
    ) -> list[InventoryItem]:
        if not item_ids:
            return []
        statement = select(InventoryItem).where(
            InventoryItem.tenant_id == tenant_id,
            InventoryItem.id.in_(item_ids),
        )
        if excluded_ids:
            statement = statement.where(InventoryItem.id.not_in(excluded_ids))
        if for_update:
            statement = statement.with_for_update()
        items_by_id = {item.id: item for item in self.db.scalars(statement).all()}
        ordered_ids = sorted(items_by_id) if for_update else item_ids
        return [items_by_id[item_id] for item_id in ordered_ids if item_id in items_by_id]

    def list_items_for_bulk_filter(
        self,
        tenant_id: uuid.UUID,
        *,
        search: str | None,
        category: str | None,
        brand: str | None,
        supplier: str | None,
        stock_status: str | None,
        is_active: bool | None,
        excluded_ids: set[uuid.UUID],
        limit: int,
        for_update: bool = False,
    ) -> tuple[list[InventoryItem], int]:
        statement = self._build_item_list_statement(
            tenant_id,
            search=search,
            category=category,
            brand=brand,
            supplier=supplier,
            status=None,
            stock_status=stock_status,
            is_active=is_active,
            sort_by="id",
            sort_direction="asc",
        )
        count_statement = self._build_item_count_statement(
            tenant_id,
            search=search,
            category=category,
            brand=brand,
            supplier=supplier,
            status=None,
            stock_status=stock_status,
            is_active=is_active,
        )
        if excluded_ids:
            statement = statement.where(InventoryItem.id.not_in(excluded_ids))
            count_statement = count_statement.where(InventoryItem.id.not_in(excluded_ids))
        if for_update:
            statement = statement.with_for_update()
        return list(self.db.scalars(statement.limit(limit)).all()), int(
            self.db.scalar(count_statement) or 0
        )

    def create_bulk_operation(
        self,
        operation: InventoryBulkOperation,
    ) -> InventoryBulkOperation:
        self.db.add(operation)
        self.db.flush()
        self.db.refresh(operation)
        return operation

    def create_bulk_operation_items(
        self,
        rows: list[InventoryBulkOperationItem],
    ) -> list[InventoryBulkOperationItem]:
        self.db.add_all(rows)
        self.db.flush()
        return rows

    def get_bulk_operation_by_id(
        self,
        tenant_id: uuid.UUID,
        operation_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> InventoryBulkOperation | None:
        statement = (
            select(InventoryBulkOperation)
            .where(
                InventoryBulkOperation.tenant_id == tenant_id,
                InventoryBulkOperation.id == operation_id,
            )
            .options(
                selectinload(InventoryBulkOperation.created_by_user),
                selectinload(InventoryBulkOperation.reversed_by_user),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list_bulk_operations(
        self,
        tenant_id: uuid.UUID,
        *,
        status: str | None,
        operation_type: str | None,
        created_by_user_id: uuid.UUID | None,
        date_from: datetime | None,
        date_to: datetime | None,
        page: int,
        page_size: int,
    ) -> tuple[list[InventoryBulkOperation], int]:
        statement = (
            select(InventoryBulkOperation)
            .where(InventoryBulkOperation.tenant_id == tenant_id)
            .options(
                selectinload(InventoryBulkOperation.created_by_user),
                selectinload(InventoryBulkOperation.reversed_by_user),
            )
        )
        count_statement = select(func.count()).select_from(InventoryBulkOperation).where(
            InventoryBulkOperation.tenant_id == tenant_id
        )
        if status is not None:
            statement = statement.where(InventoryBulkOperation.status == status)
            count_statement = count_statement.where(InventoryBulkOperation.status == status)
        if operation_type is not None:
            statement = statement.where(InventoryBulkOperation.operation_type == operation_type)
            count_statement = count_statement.where(InventoryBulkOperation.operation_type == operation_type)
        if created_by_user_id is not None:
            statement = statement.where(InventoryBulkOperation.created_by_user_id == created_by_user_id)
            count_statement = count_statement.where(InventoryBulkOperation.created_by_user_id == created_by_user_id)
        if date_from is not None:
            statement = statement.where(InventoryBulkOperation.created_at >= date_from)
            count_statement = count_statement.where(InventoryBulkOperation.created_at >= date_from)
        if date_to is not None:
            statement = statement.where(InventoryBulkOperation.created_at <= date_to)
            count_statement = count_statement.where(InventoryBulkOperation.created_at <= date_to)
        offset = (page - 1) * page_size
        statement = (
            statement.order_by(InventoryBulkOperation.created_at.desc(), InventoryBulkOperation.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(self.db.scalars(statement).all()), int(self.db.scalar(count_statement) or 0)

    def list_bulk_operation_items(
        self,
        tenant_id: uuid.UUID,
        operation_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
    ) -> tuple[list[InventoryBulkOperationItem], int]:
        statement = (
            select(InventoryBulkOperationItem)
            .where(
                InventoryBulkOperationItem.tenant_id == tenant_id,
                InventoryBulkOperationItem.operation_id == operation_id,
            )
            .options(selectinload(InventoryBulkOperationItem.inventory_item))
            .order_by(InventoryBulkOperationItem.created_at.asc(), InventoryBulkOperationItem.id.asc())
        )
        count_statement = select(func.count()).select_from(InventoryBulkOperationItem).where(
            InventoryBulkOperationItem.tenant_id == tenant_id,
            InventoryBulkOperationItem.operation_id == operation_id,
        )
        if status is not None:
            statement = statement.where(InventoryBulkOperationItem.status == status)
            count_statement = count_statement.where(InventoryBulkOperationItem.status == status)
        offset = (page - 1) * page_size
        return list(self.db.scalars(statement.offset(offset).limit(page_size)).all()), int(
            self.db.scalar(count_statement) or 0
        )

    def list_bulk_operation_change_items(
        self,
        tenant_id: uuid.UUID,
        operation_id: uuid.UUID,
        *,
        statuses: set[str],
    ) -> list[InventoryBulkOperationItem]:
        statement = (
            select(InventoryBulkOperationItem)
            .where(
                InventoryBulkOperationItem.tenant_id == tenant_id,
                InventoryBulkOperationItem.operation_id == operation_id,
                InventoryBulkOperationItem.status.in_(statuses),
            )
            .order_by(InventoryBulkOperationItem.inventory_item_id.asc())
        )
        return list(self.db.scalars(statement).all())

    def get_dashboard_catalog_metrics(
        self,
        tenant_id: uuid.UUID,
        *,
        category: str | None,
        brand: str | None,
        supplier: str | None,
        is_active: bool | None,
    ) -> dict:
        filters = self._dashboard_item_filters(
            tenant_id,
            category=category,
            brand=brand,
            supplier=supplier,
            is_active=is_active,
        )
        purchase_cost_with_tax = (
            func.coalesce(InventoryItem.purchase_price_ars, 0)
            * (1 + (func.coalesce(InventoryItem.purchase_tax_rate_percentage, 0) / 100))
        )
        statement = select(
            func.count(InventoryItem.id).label("total_products"),
            func.count(InventoryItem.id).filter(InventoryItem.is_active.is_(True)).label("active_products"),
            func.count(InventoryItem.id).filter(InventoryItem.is_active.is_(False)).label("inactive_products"),
            func.count(InventoryItem.id)
            .filter(InventoryItem.current_stock > InventoryItem.minimum_stock)
            .label("in_stock_products"),
            func.count(InventoryItem.id)
            .filter(
                InventoryItem.current_stock > 0,
                InventoryItem.current_stock <= InventoryItem.minimum_stock,
            )
            .label("low_stock_products"),
            func.count(InventoryItem.id).filter(InventoryItem.current_stock == 0).label("out_of_stock_products"),
            func.count(InventoryItem.id).filter(InventoryItem.current_stock < 0).label("negative_stock_products"),
            func.coalesce(func.sum(InventoryItem.current_stock * purchase_cost_with_tax), 0).label("estimated_cost_value_ars"),
            func.coalesce(
                func.sum(InventoryItem.current_stock * func.coalesce(InventoryItem.sale_price_ars, 0)),
                0,
            ).label("estimated_sale_value_ars"),
            func.count(InventoryItem.id)
            .filter(InventoryItem.is_active.is_(False), InventoryItem.current_stock != 0)
            .label("inactive_with_stock_products"),
            func.count(InventoryItem.id)
            .filter(InventoryItem.is_active.is_(True), InventoryItem.purchase_price_ars.is_(None))
            .label("missing_purchase_cost_products"),
            func.count(InventoryItem.id)
            .filter(InventoryItem.is_active.is_(True), InventoryItem.sale_price_ars.is_(None))
            .label("missing_sale_price_products"),
            func.count(InventoryItem.id)
            .filter(or_(InventoryItem.brand.is_(None), func.trim(InventoryItem.brand) == ""))
            .label("missing_brand_products"),
            func.count(InventoryItem.id)
            .filter(or_(InventoryItem.supplier.is_(None), func.trim(InventoryItem.supplier) == ""))
            .label("missing_supplier_products"),
        ).where(*filters)
        row = self.db.execute(statement).mappings().one()
        return dict(row)

    def list_dashboard_attention_items(
        self,
        tenant_id: uuid.UUID,
        *,
        category: str | None,
        brand: str | None,
        supplier: str | None,
        is_active: bool | None,
        limit: int,
    ) -> list[InventoryItem]:
        filters = self._dashboard_item_filters(
            tenant_id,
            category=category,
            brand=brand,
            supplier=supplier,
            is_active=is_active,
        )
        alert_condition = or_(
            InventoryItem.current_stock < 0,
            InventoryItem.current_stock == 0,
            and_(InventoryItem.current_stock > 0, InventoryItem.current_stock <= InventoryItem.minimum_stock),
            and_(InventoryItem.is_active.is_(False), InventoryItem.current_stock != 0),
            and_(InventoryItem.is_active.is_(True), InventoryItem.purchase_price_ars.is_(None)),
            and_(InventoryItem.is_active.is_(True), InventoryItem.sale_price_ars.is_(None)),
            InventoryItem.brand.is_(None),
            func.trim(InventoryItem.brand) == "",
            InventoryItem.supplier.is_(None),
            func.trim(InventoryItem.supplier) == "",
        )
        priority_order = case(
            (InventoryItem.current_stock < 0, 0),
            (
                or_(
                    InventoryItem.current_stock == 0,
                    and_(InventoryItem.is_active.is_(True), InventoryItem.sale_price_ars.is_(None)),
                    and_(InventoryItem.is_active.is_(True), InventoryItem.purchase_price_ars.is_(None)),
                ),
                1,
            ),
            (
                or_(
                    and_(InventoryItem.current_stock > 0, InventoryItem.current_stock <= InventoryItem.minimum_stock),
                    and_(InventoryItem.is_active.is_(False), InventoryItem.current_stock != 0),
                ),
                2,
            ),
            else_=3,
        )
        statement = (
            select(InventoryItem)
            .where(*filters, alert_condition)
            .order_by(priority_order.asc(), InventoryItem.current_stock.asc(), func.lower(InventoryItem.name).asc(), InventoryItem.id.asc())
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def get_dashboard_movement_metrics(
        self,
        tenant_id: uuid.UUID,
        *,
        date_from: datetime,
        date_to: datetime,
    ) -> dict:
        statement = select(
            func.count(InventoryMovement.id).label("total_movements"),
            func.count(InventoryMovement.id)
            .filter(InventoryMovement.movement_type.in_(
                [
                    "initial_stock",
                    "manual_entry",
                    "purchase",
                    "customer_return",
                    "adjustment_in",
                    "transfer_in",
                    "entry",
                ]
            ))
            .label("entry_movements"),
            func.count(InventoryMovement.id)
            .filter(InventoryMovement.movement_type.in_(
                [
                    "manual_exit",
                    "sale",
                    "clinical_consumption",
                    "supplier_return",
                    "purchase_return",
                    "adjustment_out",
                    "expiration",
                    "loss",
                    "breakage",
                    "transfer_out",
                    "exit",
                ]
            ))
            .label("exit_movements"),
            func.count(InventoryMovement.id)
            .filter(InventoryMovement.movement_type.in_(["adjustment_in", "adjustment_out", "adjustment"]))
            .label("adjustment_movements"),
            func.count(InventoryMovement.id)
            .filter(InventoryMovement.movement_type == "reversal")
            .label("reversal_movements"),
            func.count(InventoryMovement.id)
            .filter(InventoryMovement.movement_type == "clinical_consumption")
            .label("clinical_consumption_movements"),
        ).where(
            InventoryMovement.tenant_id == tenant_id,
            InventoryMovement.created_at >= date_from,
            InventoryMovement.created_at <= date_to,
        )
        row = self.db.execute(statement).mappings().one()
        return dict(row)

    def list_dashboard_recent_movements(
        self,
        tenant_id: uuid.UUID,
        *,
        date_from: datetime,
        date_to: datetime,
        limit: int,
    ) -> list[InventoryMovement]:
        statement = (
            select(InventoryMovement)
            .join(
                InventoryItem,
                (InventoryItem.id == InventoryMovement.inventory_item_id)
                & (InventoryItem.tenant_id == tenant_id),
            )
            .where(
                InventoryMovement.tenant_id == tenant_id,
                InventoryMovement.created_at >= date_from,
                InventoryMovement.created_at <= date_to,
            )
            .options(
                selectinload(InventoryMovement.inventory_item),
                selectinload(InventoryMovement.created_by_user),
                selectinload(InventoryMovement.reverses_movement),
                selectinload(InventoryMovement.reversed_by_movement),
            )
            .order_by(InventoryMovement.created_at.desc(), InventoryMovement.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def list_dashboard_recent_imports(
        self,
        tenant_id: uuid.UUID,
        *,
        date_from: datetime,
        date_to: datetime,
        limit: int,
    ) -> list[InventoryImport]:
        statement = (
            select(InventoryImport)
            .where(
                InventoryImport.tenant_id == tenant_id,
                InventoryImport.created_at >= date_from,
                InventoryImport.created_at <= date_to,
            )
            .options(selectinload(InventoryImport.created_by_user))
            .order_by(InventoryImport.created_at.desc(), InventoryImport.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def list_dashboard_recent_bulk_operations(
        self,
        tenant_id: uuid.UUID,
        *,
        date_from: datetime,
        date_to: datetime,
        limit: int,
    ) -> list[InventoryBulkOperation]:
        statement = (
            select(InventoryBulkOperation)
            .where(
                InventoryBulkOperation.tenant_id == tenant_id,
                InventoryBulkOperation.created_at >= date_from,
                InventoryBulkOperation.created_at <= date_to,
            )
            .options(
                selectinload(InventoryBulkOperation.created_by_user),
                selectinload(InventoryBulkOperation.reversed_by_user),
            )
            .order_by(InventoryBulkOperation.created_at.desc(), InventoryBulkOperation.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def _dashboard_item_filters(
        self,
        tenant_id: uuid.UUID,
        *,
        category: str | None,
        brand: str | None,
        supplier: str | None,
        is_active: bool | None,
    ) -> list:
        filters = [InventoryItem.tenant_id == tenant_id]
        if category is not None:
            filters.append(InventoryItem.category == category)
        if brand is not None:
            filters.append(func.lower(func.trim(InventoryItem.brand)) == brand.lower())
        if supplier is not None:
            filters.append(func.lower(func.trim(InventoryItem.supplier)) == supplier.lower())
        if is_active is not None:
            filters.append(InventoryItem.is_active.is_(is_active))
        return filters

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

    def create_import(self, inventory_import: InventoryImport) -> InventoryImport:
        self.db.add(inventory_import)
        self.db.flush()
        self.db.refresh(inventory_import)
        return inventory_import

    def create_import_rows(self, rows: list[InventoryImportRow]) -> list[InventoryImportRow]:
        self.db.add_all(rows)
        self.db.flush()
        return rows

    def get_import_by_id(
        self,
        tenant_id: uuid.UUID,
        import_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> InventoryImport | None:
        statement = (
            select(InventoryImport)
            .where(
                InventoryImport.id == import_id,
                InventoryImport.tenant_id == tenant_id,
            )
            .options(
                selectinload(InventoryImport.rows),
                selectinload(InventoryImport.created_by_user),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list_imports(
        self,
        tenant_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[InventoryImport], int]:
        offset = (page - 1) * page_size
        statement = (
            select(InventoryImport)
            .where(InventoryImport.tenant_id == tenant_id)
            .options(selectinload(InventoryImport.created_by_user))
            .order_by(InventoryImport.created_at.desc(), InventoryImport.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        count_statement = (
            select(func.count())
            .select_from(InventoryImport)
            .where(InventoryImport.tenant_id == tenant_id)
        )
        return list(self.db.scalars(statement).all()), int(self.db.scalar(count_statement) or 0)

    def has_confirmed_import_with_hash(
        self,
        tenant_id: uuid.UUID,
        *,
        file_hash: str,
        mode: str,
        exclude_import_id: uuid.UUID | None = None,
    ) -> bool:
        statement = select(InventoryImport.id).where(
            InventoryImport.tenant_id == tenant_id,
            InventoryImport.file_hash == file_hash,
            InventoryImport.mode == mode,
            InventoryImport.status == "confirmed",
        )
        if exclude_import_id is not None:
            statement = statement.where(InventoryImport.id != exclude_import_id)
        return self.db.scalar(statement) is not None

    def get_movement_by_id(
        self,
        tenant_id: uuid.UUID,
        movement_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> InventoryMovement | None:
        statement = (
            select(InventoryMovement)
            .join(
                InventoryItem,
                (InventoryItem.id == InventoryMovement.inventory_item_id)
                & (InventoryItem.tenant_id == tenant_id),
            )
            .where(
                InventoryMovement.id == movement_id,
                InventoryMovement.tenant_id == tenant_id,
            )
            .options(
                selectinload(InventoryMovement.inventory_item),
                selectinload(InventoryMovement.created_by_user),
                selectinload(InventoryMovement.reverses_movement),
                selectinload(InventoryMovement.reversed_by_movement),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def get_reversal_for_movement(
        self,
        tenant_id: uuid.UUID,
        movement_id: uuid.UUID,
    ) -> InventoryMovement | None:
        statement = (
            select(InventoryMovement)
            .where(
                InventoryMovement.tenant_id == tenant_id,
                InventoryMovement.reverses_movement_id == movement_id,
            )
            .options(
                selectinload(InventoryMovement.inventory_item),
                selectinload(InventoryMovement.created_by_user),
                selectinload(InventoryMovement.reverses_movement),
            )
        )
        return self.db.scalar(statement)

    def list_purchase_movements_for_update(
        self,
        tenant_id: uuid.UUID,
        *,
        purchase_id: uuid.UUID,
        operation_id: uuid.UUID,
    ) -> list[InventoryMovement]:
        statement = (
            select(InventoryMovement)
            .join(
                InventoryItem,
                (InventoryItem.id == InventoryMovement.inventory_item_id)
                & (InventoryItem.tenant_id == tenant_id),
            )
            .where(
                InventoryMovement.tenant_id == tenant_id,
                InventoryMovement.movement_type == "purchase",
                InventoryMovement.source_type == "purchase",
                InventoryMovement.source_id == str(purchase_id),
                InventoryMovement.operation_id == operation_id,
            )
            .order_by(
                InventoryMovement.inventory_item_id.asc(),
                InventoryMovement.id.asc(),
            )
            .with_for_update()
        )
        return list(self.db.scalars(statement).all())

    def list_reversals_for_movements(
        self,
        tenant_id: uuid.UUID,
        movement_ids: list[uuid.UUID],
    ) -> list[InventoryMovement]:
        if not movement_ids:
            return []
        statement = select(InventoryMovement).where(
            InventoryMovement.tenant_id == tenant_id,
            InventoryMovement.reverses_movement_id.in_(movement_ids),
        )
        return list(self.db.scalars(statement).all())

    def list_movements(
        self,
        tenant_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
        inventory_item_id: uuid.UUID | None = None,
        movement_type: str | None,
        search: str | None = None,
        created_by_user_id: uuid.UUID | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        operation_id: uuid.UUID | None = None,
        reversal_status: str = "all",
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_direction: str = "desc",
    ) -> tuple[list[InventoryMovement], int]:
        statement: Select[tuple[InventoryMovement]] = (
            select(InventoryMovement)
            .join(
                InventoryItem,
                (InventoryItem.id == InventoryMovement.inventory_item_id)
                & (InventoryItem.tenant_id == tenant_id),
            )
            .where(InventoryMovement.tenant_id == tenant_id)
            .options(
                selectinload(InventoryMovement.inventory_item),
                selectinload(InventoryMovement.created_by_user),
                selectinload(InventoryMovement.reverses_movement),
                selectinload(InventoryMovement.reversed_by_movement),
            )
        )
        count_statement = (
            select(func.count())
            .select_from(InventoryMovement)
            .join(
                InventoryItem,
                (InventoryItem.id == InventoryMovement.inventory_item_id)
                & (InventoryItem.tenant_id == tenant_id),
            )
            .where(InventoryMovement.tenant_id == tenant_id)
        )
        statement = self._apply_movement_filters(
            statement,
            tenant_id=tenant_id,
            inventory_item_id=inventory_item_id,
            movement_type=movement_type,
            search=search,
            created_by_user_id=created_by_user_id,
            source_type=source_type,
            source_id=source_id,
            operation_id=operation_id,
            reversal_status=reversal_status,
            date_from=date_from,
            date_to=date_to,
        )
        count_statement = self._apply_movement_filters(
            count_statement,
            tenant_id=tenant_id,
            inventory_item_id=inventory_item_id,
            movement_type=movement_type,
            search=search,
            created_by_user_id=created_by_user_id,
            source_type=source_type,
            source_id=source_id,
            operation_id=operation_id,
            reversal_status=reversal_status,
            date_from=date_from,
            date_to=date_to,
        )

        offset = (page - 1) * page_size
        first_sort = (
            InventoryMovement.created_at.asc()
            if sort_direction == "asc"
            else InventoryMovement.created_at.desc()
        )
        second_sort = (
            InventoryMovement.id.asc()
            if sort_direction == "asc"
            else InventoryMovement.id.desc()
        )
        movements = list(
            self.db.scalars(
                statement.order_by(first_sort, second_sort).offset(offset).limit(page_size)
            ).all()
        )
        total = int(self.db.scalar(count_statement) or 0)
        return movements, total

    def _build_item_list_statement(
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
        sort_by: str,
        sort_direction: str,
    ):
        statement: Select[tuple[InventoryItem]] = select(InventoryItem).where(
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
        return self._apply_item_sort(statement, sort_by=sort_by, sort_direction=sort_direction)

    def _build_item_count_statement(
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
    ):
        statement = select(func.count()).select_from(InventoryItem).where(
            InventoryItem.tenant_id == tenant_id,
        )
        return self._apply_item_filters(
            statement,
            search=search,
            category=category,
            brand=brand,
            supplier=supplier,
            status=status,
            stock_status=stock_status,
            is_active=is_active,
        )

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

    def _apply_item_sort(
        self,
        statement,
        *,
        sort_by: str,
        sort_direction: str,
    ):
        sort_column = self._get_sort_column(sort_by)
        order_by = desc(sort_column) if sort_direction == "desc" else asc(sort_column)
        return statement.order_by(order_by, InventoryItem.id.asc())

    def _apply_movement_filters(
        self,
        statement,
        *,
        tenant_id: uuid.UUID,
        inventory_item_id: uuid.UUID | None,
        movement_type: str | None,
        search: str | None,
        created_by_user_id: uuid.UUID | None,
        source_type: str | None,
        source_id: str | None,
        operation_id: uuid.UUID | None,
        reversal_status: str,
        date_from: datetime | None,
        date_to: datetime | None,
    ):
        if inventory_item_id is not None:
            statement = statement.where(InventoryMovement.inventory_item_id == inventory_item_id)
        if movement_type is not None:
            statement = statement.where(InventoryMovement.movement_type == movement_type)
        if created_by_user_id is not None:
            statement = statement.where(InventoryMovement.created_by_user_id == created_by_user_id)
        if source_type is not None:
            statement = statement.where(InventoryMovement.source_type == source_type)
        if source_id is not None:
            statement = statement.where(InventoryMovement.source_id == source_id)
        if operation_id is not None:
            statement = statement.where(InventoryMovement.operation_id == operation_id)
        if date_from is not None:
            statement = statement.where(InventoryMovement.created_at >= date_from)
        if date_to is not None:
            statement = statement.where(InventoryMovement.created_at <= date_to)
        if search:
            pattern = f"%{search.strip().lower()}%"
            statement = statement.where(
                or_(
                    func.lower(InventoryItem.name).like(pattern),
                    func.lower(InventoryItem.internal_code).like(pattern),
                    func.lower(func.coalesce(InventoryMovement.reason, "")).like(pattern),
                    func.lower(func.coalesce(InventoryMovement.source_id, "")).like(pattern),
                )
            )

        reversal = aliased(InventoryMovement)
        reversal_exists = (
            select(reversal.id)
            .where(
                reversal.tenant_id == tenant_id,
                reversal.reverses_movement_id == InventoryMovement.id,
            )
            .exists()
        )
        if reversal_status == "active":
            statement = statement.where(
                InventoryMovement.movement_type != "reversal",
                ~reversal_exists,
            )
        elif reversal_status == "reversed":
            statement = statement.where(
                InventoryMovement.movement_type != "reversal",
                reversal_exists,
            )
        elif reversal_status == "reversal":
            statement = statement.where(InventoryMovement.movement_type == "reversal")

        return statement

    def _get_sort_column(self, sort_by: str):
        mapping = {
            "name": func.lower(InventoryItem.name),
            "internal_code": func.lower(InventoryItem.internal_code),
            "current_stock": InventoryItem.current_stock,
            "sale_price_ars": InventoryItem.sale_price_ars,
            "updated_at": InventoryItem.updated_at,
            "created_at": InventoryItem.created_at,
            "id": InventoryItem.id,
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

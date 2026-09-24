from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.tenant import TenantContext
from app.models.inventory_bulk_operation import (
    InventoryBulkOperation,
    InventoryBulkOperationItem,
)
from app.models.inventory_item import InventoryItem
from app.repositories.inventory import InventoryRepository
from app.schemas.inventory import (
    InventoryBulkOperationConfirmCreate,
    InventoryBulkOperationPreviewCreate,
    InventoryBulkOperationReverseCreate,
    InventoryBulkSelectionCreate,
)
from app.services.inventory import (
    HUNDRED,
    InventoryService,
    ZERO,
)


MAX_BULK_SELECTED_IDS = 500
MAX_BULK_EXCLUDED_IDS = 500
MAX_BULK_PRODUCTS = 2_000
PREVIEW_TTL_HOURS = 24
PRICE_PERCENTAGE_LIMIT = Decimal("1000")
CHANGE_STATUSES = {"pending", "changed"}


class InventoryBulkOperationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.inventory_repository = InventoryRepository(db)
        self.inventory_service = InventoryService(db)

    def preview_operation(
        self,
        tenant: TenantContext,
        payload: InventoryBulkOperationPreviewCreate,
    ) -> InventoryBulkOperation:
        items, excluded_count, filters_json = self._resolve_selection(
            tenant.tenant_id,
            payload.selection,
        )
        rounding_increment = self.inventory_service._resolve_pricing_defaults(
            tenant.tenant_id
        )["rounding_increment"]
        rows = [
            self._build_preview_row(
                tenant.tenant_id,
                item,
                payload,
                rounding_increment=rounding_increment,
            )
            for item in items
        ]
        counts = self._count_rows(rows, excluded_count=excluded_count)
        operation = InventoryBulkOperation(
            tenant_id=tenant.tenant_id,
            created_by_user_id=tenant.user_id,
            operation_type=payload.operation.operation_type,
            selection_mode=payload.selection.selection_mode,
            filters_json=filters_json,
            request_json=self._json_ready(payload.model_dump(mode="json")),
            status="preview",
            selected_count=counts["selected_count"],
            affected_count=counts["affected_count"],
            unchanged_count=counts["unchanged_count"],
            invalid_count=counts["invalid_count"],
            excluded_count=counts["excluded_count"],
            reversed_count=0,
            conflict_count=0,
            expires_at=datetime.now(UTC) + timedelta(hours=PREVIEW_TTL_HOURS),
        )
        self.inventory_repository.create_bulk_operation(operation)
        operation_rows = [
            InventoryBulkOperationItem(operation_id=operation.id, **row)
            for row in rows
        ]
        self.inventory_repository.create_bulk_operation_items(operation_rows)
        self.db.commit()
        return self.get_operation(tenant.tenant_id, operation.id)

    def confirm_operation(
        self,
        tenant: TenantContext,
        operation_id: uuid.UUID,
        payload: InventoryBulkOperationConfirmCreate,
    ) -> InventoryBulkOperation:
        _ = payload
        operation = self.inventory_repository.get_bulk_operation_by_id(
            tenant.tenant_id,
            operation_id,
            for_update=True,
        )
        if operation is None:
            raise AppError(404, "inventory_bulk_operation_not_found", "Bulk operation not found")
        if operation.status == "confirmed":
            raise AppError(409, "inventory_bulk_operation_already_confirmed", "Bulk operation already confirmed")
        if operation.status != "preview":
            raise AppError(409, "inventory_bulk_operation_not_confirmable", "Bulk operation cannot be confirmed")
        if self._is_expired(operation):
            operation.status = "expired"
            self.db.commit()
            raise AppError(409, "inventory_bulk_operation_expired", "Bulk operation preview expired")

        rows = self.inventory_repository.list_bulk_operation_change_items(
            tenant.tenant_id,
            operation.id,
            statuses={"pending"},
        )
        item_ids = sorted({row.inventory_item_id for row in rows})
        items = self.inventory_repository.list_items_by_ids_for_bulk(
            tenant.tenant_id,
            item_ids,
            for_update=True,
        )
        item_by_id = {item.id: item for item in items}

        try:
            for row in rows:
                item = item_by_id.get(row.inventory_item_id)
                if item is None:
                    raise AppError(404, "inventory_item_not_found", "Inventory item not found")
                if not self._same_snapshot(row.product_updated_at_snapshot, item.updated_at):
                    raise AppError(
                        409,
                        "inventory_bulk_operation_conflict",
                        "A product changed after preview. Generate a new preview.",
                    )
                self.inventory_repository.update_item(item, self._updates_from_row(row, use_old=False))
                row.status = "changed"
                self.db.add(row)

            operation.status = "confirmed"
            operation.confirmed_at = datetime.now(UTC)
            operation.affected_count = len(rows)
            operation.unchanged_count = self._count_operation_rows(operation, "unchanged")
            operation.invalid_count = self._count_operation_rows(operation, "invalid")
            self.db.add(operation)
            self.db.commit()
        except AppError:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            raise AppError(500, "inventory_bulk_operation_failed", "Bulk operation failed") from exc

        return self.get_operation(tenant.tenant_id, operation.id)

    def reverse_operation(
        self,
        tenant: TenantContext,
        operation_id: uuid.UUID,
        payload: InventoryBulkOperationReverseCreate,
    ) -> InventoryBulkOperation:
        operation = self.inventory_repository.get_bulk_operation_by_id(
            tenant.tenant_id,
            operation_id,
            for_update=True,
        )
        if operation is None:
            raise AppError(404, "inventory_bulk_operation_not_found", "Bulk operation not found")
        if operation.status not in {"confirmed", "partially_reversed"}:
            raise AppError(409, "inventory_bulk_operation_not_reversible", "Bulk operation cannot be reversed")

        rows = self.inventory_repository.list_bulk_operation_change_items(
            tenant.tenant_id,
            operation.id,
            statuses={"changed", "conflict"},
        )
        reversible_rows = [row for row in rows if row.status == "changed"]
        if not reversible_rows:
            raise AppError(409, "inventory_bulk_operation_already_reversed", "Bulk operation already reversed")
        item_ids = sorted({row.inventory_item_id for row in reversible_rows})
        items = self.inventory_repository.list_items_by_ids_for_bulk(
            tenant.tenant_id,
            item_ids,
            for_update=True,
        )
        item_by_id = {item.id: item for item in items}

        now = datetime.now(UTC)
        reversed_count = 0
        conflict_count = operation.conflict_count
        for row in reversible_rows:
            item = item_by_id.get(row.inventory_item_id)
            if item is None:
                row.status = "conflict"
                row.error_message = "inventory_item_not_found"
                conflict_count += 1
                self.db.add(row)
                continue
            current_value = self._current_value_for_row(item, row)
            expected_new = self._value_from_json(row.new_value_json)
            if not self._values_equal(current_value, expected_new):
                row.status = "conflict"
                row.error_message = "value_changed_after_bulk_operation"
                conflict_count += 1
                self.db.add(row)
                continue
            self.inventory_repository.update_item(item, self._updates_from_row(row, use_old=True))
            row.status = "reverted"
            row.reverted_at = now
            self.db.add(row)
            reversed_count += 1

        operation.reversed_count += reversed_count
        operation.conflict_count = conflict_count
        operation.reversed_at = now
        operation.reversed_by_user_id = tenant.user_id
        operation.reversal_reason = payload.reason
        operation.status = "partially_reversed" if conflict_count else "reversed"
        self.db.add(operation)
        self.db.commit()
        return self.get_operation(tenant.tenant_id, operation.id)

    def get_operation(
        self,
        tenant_id: uuid.UUID,
        operation_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = 100,
        status: str | None = None,
    ) -> InventoryBulkOperation:
        operation = self.inventory_repository.get_bulk_operation_by_id(tenant_id, operation_id)
        if operation is None:
            raise AppError(404, "inventory_bulk_operation_not_found", "Bulk operation not found")
        self._mark_expired_if_needed(operation)
        rows, meta = self._list_rows(tenant_id, operation.id, page=page, page_size=page_size, status=status)
        setattr(operation, "items", rows)
        setattr(operation, "items_meta", meta)
        setattr(operation, "summary", self._summary(operation))
        return operation

    def list_operations(
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
    ) -> tuple[list[InventoryBulkOperation], dict]:
        if page < 1 or page_size < 1 or page_size > 100:
            raise AppError(422, "invalid_pagination", "Invalid pagination parameters")
        operations, total = self.inventory_repository.list_bulk_operations(
            tenant_id,
            status=status,
            operation_type=operation_type,
            created_by_user_id=created_by_user_id,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
        return operations, {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size if total else 0,
        }

    def _resolve_selection(
        self,
        tenant_id: uuid.UUID,
        selection: InventoryBulkSelectionCreate,
    ) -> tuple[list[InventoryItem], int, dict | None]:
        excluded_ids = set(self._dedupe_ids(selection.excluded_ids))
        if len(excluded_ids) > MAX_BULK_EXCLUDED_IDS:
            raise AppError(422, "too_many_excluded_ids", "Too many excluded IDs")
        if selection.selection_mode == "selected":
            selected_ids = self._dedupe_ids(selection.selected_ids)
            if len(selected_ids) > MAX_BULK_SELECTED_IDS:
                raise AppError(422, "too_many_selected_ids", "Too many selected IDs")
            items_before_exclusion = self.inventory_repository.list_items_by_ids_for_bulk(
                tenant_id,
                selected_ids,
            )
            if len(items_before_exclusion) != len(selected_ids):
                raise AppError(404, "inventory_item_not_found", "One or more products were not found")
            items = [item for item in items_before_exclusion if item.id not in excluded_ids]
            if not items:
                raise AppError(422, "empty_selection", "Bulk operation selection is empty")
            return items, len(items_before_exclusion) - len(items), None

        filters = selection.filters
        filters_json = filters.model_dump(mode="json", exclude_none=True) if filters else {}
        items, total = self.inventory_repository.list_items_for_bulk_filter(
            tenant_id,
            search=filters.search if filters else None,
            category=filters.category if filters else None,
            brand=filters.brand if filters else None,
            supplier=filters.supplier if filters else None,
            stock_status=filters.stock_status if filters else None,
            is_active=filters.is_active if filters else None,
            excluded_ids=excluded_ids,
            limit=MAX_BULK_PRODUCTS + 1,
        )
        if total > MAX_BULK_PRODUCTS:
            raise AppError(
                413,
                "inventory_bulk_operation_too_large",
                "La operación supera 2.000 productos; aplica filtros más específicos.",
            )
        if not items:
            raise AppError(422, "empty_selection", "Bulk operation selection is empty")
        return items, len(excluded_ids), filters_json

    def _build_preview_row(
        self,
        tenant_id: uuid.UUID,
        item: InventoryItem,
        payload: InventoryBulkOperationPreviewCreate,
        *,
        rounding_increment: Decimal,
    ) -> dict:
        field_name, old_value, new_value, error = self._calculate_change(
            item,
            payload,
            rounding_increment=rounding_increment,
        )
        status = "invalid" if error else "unchanged" if self._values_equal(old_value, new_value) else "pending"
        return {
            "tenant_id": tenant_id,
            "inventory_item_id": item.id,
            "field_name": field_name,
            "old_value_json": self._json_box(old_value),
            "new_value_json": self._json_box(new_value),
            "product_updated_at_snapshot": item.updated_at,
            "status": status,
            "error_message": error,
        }

    def _calculate_change(
        self,
        item: InventoryItem,
        payload: InventoryBulkOperationPreviewCreate,
        *,
        rounding_increment: Decimal,
    ) -> tuple[str, Any, Any, str | None]:
        operation = payload.operation
        operation_type = operation.operation_type
        if operation_type in {"increase_sale_price_percentage", "decrease_sale_price_percentage"}:
            if item.sale_price_ars is None:
                return "sale_price_ars", None, None, "sale_price_missing"
            percentage = operation.percentage or ZERO
            factor = Decimal("1") + (percentage / HUNDRED)
            if operation_type == "decrease_sale_price_percentage":
                factor = Decimal("1") - (percentage / HUNDRED)
            if factor < ZERO:
                return "sale_price_ars", item.sale_price_ars, None, "sale_price_would_be_negative"
            return (
                "sale_price_ars",
                item.sale_price_ars,
                self.inventory_service._quantize_money(item.sale_price_ars * factor),
                None,
            )
        if operation_type == "set_profit_margin_percentage":
            margin = operation.profit_margin_percentage or ZERO
            if item.purchase_price_ars is None:
                return "profit_margin_percentage", item.profit_margin_percentage, margin, "purchase_price_missing"
            sale_price = self.inventory_service._resolve_sale_price(
                purchase_price_ars=item.purchase_price_ars,
                purchase_tax_rate_percentage=item.purchase_tax_rate_percentage,
                profit_margin_percentage=margin,
                round_sale_price=item.round_sale_price,
                manual_sale_price_ars=None,
                rounding_increment=rounding_increment,
            )
            return (
                "profit_margin_percentage",
                {
                    "profit_margin_percentage": item.profit_margin_percentage,
                    "sale_price_ars": item.sale_price_ars,
                },
                {
                    "profit_margin_percentage": margin,
                    "sale_price_ars": sale_price,
                },
                None,
            )
        if operation_type == "set_sale_price":
            return "sale_price_ars", item.sale_price_ars, operation.sale_price_ars, None
        if operation_type == "set_brand":
            new_value = operation.brand or None
            return "brand", item.brand, new_value, None
        if operation_type == "set_supplier":
            new_value = operation.supplier or None
            return "supplier", item.supplier, new_value, None
        if operation_type == "set_minimum_stock":
            return "minimum_stock", item.minimum_stock, operation.minimum_stock, None
        if operation_type == "activate":
            return "is_active", item.is_active, True, None
        if operation_type == "deactivate":
            return "is_active", item.is_active, False, None
        raise AppError(422, "invalid_bulk_operation", "Invalid bulk operation")

    def _updates_from_row(self, row: InventoryBulkOperationItem, *, use_old: bool) -> dict[str, Any]:
        value = self._value_from_json(row.old_value_json if use_old else row.new_value_json)
        if row.field_name == "profit_margin_percentage" and isinstance(value, dict):
            return {
                "profit_margin_percentage": self._json_inner_decimal(value.get("profit_margin_percentage")),
                "sale_price_ars": self._json_inner_decimal(value.get("sale_price_ars")),
            }
        return {row.field_name: value}

    def _current_value_for_row(self, item: InventoryItem, row: InventoryBulkOperationItem) -> Any:
        if row.field_name == "profit_margin_percentage":
            return {
                "profit_margin_percentage": item.profit_margin_percentage,
                "sale_price_ars": item.sale_price_ars,
            }
        return getattr(item, row.field_name)

    def _value_from_json(self, value_json: dict | None) -> Any:
        if value_json is None:
            return None
        value = value_json.get("value")
        value_type = value_json.get("type")
        if value_type == "decimal" and value is not None:
            return Decimal(str(value))
        if value_type == "object" and isinstance(value, dict):
            return value
        return value

    def _json_box(self, value: Any) -> dict:
        if isinstance(value, Decimal):
            return {"value": str(value), "type": "decimal"}
        if isinstance(value, uuid.UUID):
            return {"value": str(value), "type": "uuid"}
        if isinstance(value, dict):
            return {"value": self._json_ready(value), "type": "object"}
        return {"value": value, "type": type(value).__name__ if value is not None else "null"}

    def _json_ready(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, list):
            return [self._json_ready(item) for item in value]
        if isinstance(value, dict):
            return {key: self._json_ready(item) for key, item in value.items()}
        return value

    def _values_equal(self, left: Any, right: Any) -> bool:
        if isinstance(left, dict) and isinstance(right, dict):
            return self._json_ready(left) == self._json_ready(right)
        if isinstance(left, Decimal) or isinstance(right, Decimal):
            if left is None or right is None:
                return left is right
            return Decimal(str(left)) == Decimal(str(right))
        return left == right

    def _json_inner_decimal(self, value: Any) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value))

    def _same_snapshot(self, snapshot: datetime, current: datetime) -> bool:
        return self._normalize_datetime(snapshot).isoformat() == self._normalize_datetime(current).isoformat()

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _is_expired(self, operation: InventoryBulkOperation) -> bool:
        expires_at = operation.expires_at
        now = datetime.now(expires_at.tzinfo or UTC)
        if expires_at.tzinfo is None:
            now = now.replace(tzinfo=None)
        return expires_at <= now

    def _mark_expired_if_needed(self, operation: InventoryBulkOperation) -> None:
        if operation.status == "preview" and self._is_expired(operation):
            operation.status = "expired"
            self.db.add(operation)
            self.db.commit()

    def _count_rows(self, rows: list[dict], *, excluded_count: int) -> dict[str, int]:
        return {
            "selected_count": len(rows) + excluded_count,
            "affected_count": sum(1 for row in rows if row["status"] == "pending"),
            "unchanged_count": sum(1 for row in rows if row["status"] == "unchanged"),
            "invalid_count": sum(1 for row in rows if row["status"] == "invalid"),
            "excluded_count": excluded_count,
        }

    def _summary(self, operation: InventoryBulkOperation) -> dict:
        return {
            "selected_count": operation.selected_count,
            "affected_count": operation.affected_count,
            "unchanged_count": operation.unchanged_count,
            "invalid_count": operation.invalid_count,
            "excluded_count": operation.excluded_count,
            "reversed_count": operation.reversed_count,
            "conflict_count": operation.conflict_count,
        }

    def _count_operation_rows(self, operation: InventoryBulkOperation, status: str) -> int:
        _, total = self.inventory_repository.list_bulk_operation_items(
            operation.tenant_id,
            operation.id,
            page=1,
            page_size=1,
            status=status,
        )
        return total

    def _list_rows(
        self,
        tenant_id: uuid.UUID,
        operation_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
        status: str | None,
    ) -> tuple[list[InventoryBulkOperationItem], dict]:
        if page < 1 or page_size < 1 or page_size > 200:
            raise AppError(422, "invalid_pagination", "Invalid pagination parameters")
        rows, total = self.inventory_repository.list_bulk_operation_items(
            tenant_id,
            operation_id,
            page=page,
            page_size=page_size,
            status=status,
        )
        return rows, {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size if total else 0,
        }

    def _dedupe_ids(self, item_ids: list[uuid.UUID]) -> list[uuid.UUID]:
        unique_ids: list[uuid.UUID] = []
        seen: set[uuid.UUID] = set()
        for item_id in item_ids:
            if item_id in seen:
                continue
            seen.add(item_id)
            unique_ids.append(item_id)
        return unique_ids

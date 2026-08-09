from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal, ROUND_HALF_UP
from math import ceil

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.consultation import Consultation
from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.patient import Patient
from app.models.user import User
from app.repositories.inventory import InventoryRepository
from app.repositories.patient import PatientRepository
from app.repositories.user import UserRepository
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryMovementEntryCreate,
    InventoryMovementExitCreate,
    InventoryMovementReverseCreate,
)


ALLOWED_SORT_BY = {"name", "internal_code", "current_stock", "sale_price_ars", "updated_at"}
DEFAULT_SORT_BY = "created_at"
ALLOWED_SORT_ORDER = {"asc", "desc"}
INVENTORY_CATEGORY_PREFIXES = {
    "medication": "MED",
    "vaccine": "VAC",
    "supply": "INS",
    "food": "ALI",
    "accessory": "ACC",
    "other": "OTR",
}
ZERO = Decimal("0")
TEN = Decimal("10")
HUNDRED = Decimal("100")
MOVEMENT_INCREASE_TYPES = {
    "initial_stock",
    "manual_entry",
    "purchase",
    "customer_return",
    "adjustment_in",
    "transfer_in",
    "entry",
}
MOVEMENT_DECREASE_TYPES = {
    "manual_exit",
    "sale",
    "clinical_consumption",
    "supplier_return",
    "adjustment_out",
    "expiration",
    "loss",
    "breakage",
    "transfer_out",
    "exit",
}
MOVEMENT_HISTORICAL_UNKNOWN_DIRECTION_TYPES = {"adjustment"}
ALLOWED_MOVEMENT_TYPES = (
    MOVEMENT_INCREASE_TYPES
    | MOVEMENT_DECREASE_TYPES
    | MOVEMENT_HISTORICAL_UNKNOWN_DIRECTION_TYPES
    | {"reversal"}
)


class InventoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.inventory_repository = InventoryRepository(db)
        self.patient_repository = PatientRepository(db)
        self.user_repository = UserRepository(db)

    def create_item(
        self,
        tenant_id: uuid.UUID,
        payload: InventoryItemCreate,
        *,
        created_by_user_id: uuid.UUID | None = None,
    ) -> InventoryItem:
        self._validate_non_negative_prices(
            payload.purchase_price_ars,
            payload.profit_margin_percentage,
            payload.sale_price_ars,
        )
        self._validate_tax_rates(
            payload.purchase_tax_rate_percentage,
            payload.sale_tax_rate_percentage,
        )
        self._validate_optional_user(tenant_id, created_by_user_id)

        item_data = payload.model_dump()
        item_data["sale_price_ars"] = self._resolve_sale_price(
            purchase_price_ars=payload.purchase_price_ars,
            purchase_tax_rate_percentage=payload.purchase_tax_rate_percentage,
            profit_margin_percentage=payload.profit_margin_percentage,
            round_sale_price=payload.round_sale_price,
            manual_sale_price_ars=payload.sale_price_ars,
        )
        item_data["current_stock"] = ZERO
        item_data["internal_code"] = self.inventory_repository.get_next_internal_code(
            tenant_id,
            payload.category,
            INVENTORY_CATEGORY_PREFIXES[payload.category],
        )

        item = InventoryItem(
            tenant_id=tenant_id,
            created_by_user_id=created_by_user_id,
            **item_data,
        )
        self.inventory_repository.create_item(item)
        self.db.commit()
        return self.get_item(tenant_id, item.id)

    def list_items(
        self,
        tenant_id: uuid.UUID,
        *,
        search: str | None = None,
        category: str | None = None,
        brand: str | None = None,
        supplier: str | None = None,
        status: str | None = None,
        stock_status: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 10,
        sort_by: str | None = None,
        sort_direction: str | None = None,
    ) -> tuple[list[InventoryItem], dict]:
        self._validate_pagination(page, page_size)
        resolved_sort_by = sort_by or DEFAULT_SORT_BY
        resolved_sort_direction = sort_direction or "desc"
        if sort_by is not None and sort_by not in ALLOWED_SORT_BY:
            raise AppError(422, "validation_error", "Invalid sort_by value")
        if resolved_sort_direction not in ALLOWED_SORT_ORDER:
            raise AppError(422, "validation_error", "Invalid sort_direction value")

        items, total = self.inventory_repository.list_items(
            tenant_id,
            search=self._normalize_optional_string(search),
            category=category,
            brand=self._normalize_optional_string(brand),
            supplier=self._normalize_optional_string(supplier),
            status=status,
            stock_status=stock_status,
            is_active=is_active,
            page=page,
            page_size=page_size,
            sort_by=resolved_sort_by,
            sort_direction=resolved_sort_direction,
        )
        return items, {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": ceil(total / page_size) if total else 0,
        }

    def get_item(self, tenant_id: uuid.UUID, item_id: uuid.UUID) -> InventoryItem:
        item = self.inventory_repository.get_item_by_id(tenant_id, item_id)
        if item is None:
            raise AppError(404, "inventory_item_not_found", "Inventory item not found")
        return item

    def update_item(
        self,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: InventoryItemUpdate,
    ) -> InventoryItem:
        item = self.get_item(tenant_id, item_id)
        updates = payload.model_dump(exclude_unset=True)
        for field in (
            "purchase_tax_rate_percentage",
            "sale_tax_rate_percentage",
        ):
            if field in updates and updates[field] is None:
                updates[field] = ZERO
        self._validate_non_negative_prices(
            updates.get("purchase_price_ars", item.purchase_price_ars),
            updates.get("profit_margin_percentage", item.profit_margin_percentage),
            updates.get("sale_price_ars", item.sale_price_ars),
        )
        self._validate_tax_rates(
            updates.get(
                "purchase_tax_rate_percentage",
                item.purchase_tax_rate_percentage,
            ),
            updates.get("sale_tax_rate_percentage", item.sale_tax_rate_percentage),
        )

        if self._should_recalculate_sale_price(updates):
            updates["sale_price_ars"] = self._resolve_sale_price(
                purchase_price_ars=updates.get("purchase_price_ars", item.purchase_price_ars),
                purchase_tax_rate_percentage=updates.get(
                    "purchase_tax_rate_percentage",
                    item.purchase_tax_rate_percentage,
                ),
                profit_margin_percentage=updates.get(
                    "profit_margin_percentage",
                    item.profit_margin_percentage,
                ),
                round_sale_price=updates.get("round_sale_price", item.round_sale_price),
                manual_sale_price_ars=updates.get("sale_price_ars"),
            )

        self.inventory_repository.update_item(item, updates)
        self.db.commit()
        return self.get_item(tenant_id, item_id)

    def delete_item(self, tenant_id: uuid.UUID, item_id: uuid.UUID) -> None:
        item = self.get_item(tenant_id, item_id)
        self.inventory_repository.update_item(item, {"is_active": False})
        self.db.commit()

    def get_summary(self, tenant_id: uuid.UUID) -> dict[str, int]:
        return self.inventory_repository.summarize_items(tenant_id)

    def get_filter_options(self, tenant_id: uuid.UUID) -> dict[str, list[str]]:
        return self.inventory_repository.get_filter_options(tenant_id)

    def register_entry_movement(
        self,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: InventoryMovementEntryCreate,
        *,
        created_by_user_id: uuid.UUID | None = None,
    ) -> InventoryMovement:
        self._validate_optional_user(tenant_id, created_by_user_id)

        quantity = payload.quantity
        unit_cost = payload.unit_cost_ars
        total_cost = payload.total_cost_ars
        if total_cost is not None and unit_cost is None:
            unit_cost = self._quantize_money(total_cost / quantity)
        elif unit_cost is not None and total_cost is None:
            total_cost = self._quantize_money(unit_cost * quantity)

        return self._create_stock_movement(
            tenant_id,
            item_id,
            movement_type="manual_entry",
            quantity=quantity,
            reason="manual_entry",
            unit_cost_ars=unit_cost,
            total_cost_ars=total_cost,
            supplier=payload.supplier,
            notes=payload.notes,
            source_type="manual",
            created_by_user_id=created_by_user_id,
        )

    def register_exit_movement(
        self,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: InventoryMovementExitCreate,
        *,
        created_by_user_id: uuid.UUID | None = None,
    ) -> InventoryMovement:
        self._validate_optional_user(tenant_id, created_by_user_id)
        self._validate_optional_patient(tenant_id, payload.related_patient_id)
        self._validate_optional_consultation(tenant_id, payload.related_consultation_id)

        item = self.inventory_repository.get_item_by_id(tenant_id, item_id)
        if item is None:
            raise AppError(404, "inventory_item_not_found", "Inventory item not found")
        unit_sale_price = payload.unit_sale_price_ars or item.sale_price_ars
        total_sale_price = None
        if unit_sale_price is not None:
            total_sale_price = self._quantize_money(unit_sale_price * payload.quantity)

        return self._create_stock_movement(
            tenant_id,
            item_id,
            movement_type="manual_exit",
            reason=payload.reason,
            quantity=payload.quantity,
            unit_sale_price_ars=unit_sale_price,
            total_sale_price_ars=total_sale_price,
            notes=payload.notes,
            related_patient_id=payload.related_patient_id,
            related_consultation_id=payload.related_consultation_id,
            source_type="manual",
            created_by_user_id=created_by_user_id,
        )

    def reverse_movement(
        self,
        tenant_id: uuid.UUID,
        movement_id: uuid.UUID,
        payload: InventoryMovementReverseCreate,
        *,
        created_by_user_id: uuid.UUID | None = None,
    ) -> InventoryMovement:
        self._validate_optional_user(tenant_id, created_by_user_id)
        original = self.inventory_repository.get_movement_by_id(
            tenant_id,
            movement_id,
            for_update=True,
        )
        if original is None:
            raise AppError(404, "inventory_movement_not_found", "Inventory movement not found")
        if original.movement_type == "reversal":
            raise AppError(
                409,
                "reversal_not_allowed",
                "Reversal movements cannot be reversed",
            )
        if original.movement_type == "purchase" and original.source_type == "purchase":
            raise AppError(
                409,
                "purchase_movement_requires_purchase_reversal",
                "Purchase movements must be reversed from the purchase receipt",
            )
        if original.reversed_by_movement_id is not None:
            raise AppError(
                409,
                "movement_already_reversed",
                "Inventory movement has already been reversed",
            )
        if original.movement_type in MOVEMENT_HISTORICAL_UNKNOWN_DIRECTION_TYPES:
            raise AppError(
                409,
                "movement_type_not_reversible",
                "This historical movement type cannot be reversed safely",
            )

        return self._create_stock_movement(
            tenant_id,
            original.inventory_item_id,
            movement_type="reversal",
            quantity=original.quantity,
            reason=payload.reason,
            notes=payload.notes,
            source_type="reversal",
            source_id=str(original.id),
            reverses_movement_id=original.id,
            created_by_user_id=created_by_user_id,
            reverse_of=original,
            unit_override=original.unit,
        )

    def register_clinical_consumption_movement(
        self,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        quantity: Decimal,
        patient_id: uuid.UUID,
        consultation_id: uuid.UUID,
        consultation_reason: str,
        created_by_user_id: uuid.UUID | None = None,
        commit: bool = True,
    ) -> InventoryMovement:
        item = self.inventory_repository.get_item_by_id(tenant_id, item_id)
        if item is None:
            raise AppError(404, "inventory_item_not_found", "Inventory item not found")
        unit_sale_price = item.sale_price_ars
        total_sale_price = (
            self._quantize_money(unit_sale_price * quantity)
            if unit_sale_price is not None
            else None
        )

        return self._create_stock_movement(
            tenant_id,
            item_id,
            movement_type="clinical_consumption",
            reason="consultation_use",
            quantity=quantity,
            unit_sale_price_ars=unit_sale_price,
            total_sale_price_ars=total_sale_price,
            related_patient_id=patient_id,
            related_consultation_id=consultation_id,
            notes=f"Uso en consulta: {consultation_reason}",
            source_type="consultation",
            source_id=str(consultation_id),
            created_by_user_id=created_by_user_id,
            commit=commit,
        )

    def register_import_stock_movement(
        self,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        movement_type: str,
        quantity: Decimal,
        import_id: uuid.UUID,
        operation_id: uuid.UUID,
        created_by_user_id: uuid.UUID | None,
        reason: str,
        commit: bool = True,
    ) -> InventoryMovement:
        if movement_type not in {"initial_stock", "adjustment_in", "adjustment_out"}:
            raise AppError(422, "validation_error", "Invalid import movement type")
        return self._create_stock_movement(
            tenant_id,
            item_id,
            movement_type=movement_type,
            quantity=quantity,
            reason=reason,
            notes=f"Importación de inventario {import_id}",
            source_type="inventory_import",
            source_id=str(import_id),
            operation_id=operation_id,
            created_by_user_id=created_by_user_id,
            commit=commit,
        )

    def register_purchase_movement(
        self,
        tenant_id: uuid.UUID,
        *,
        item: InventoryItem,
        purchase_id: uuid.UUID,
        operation_id: uuid.UUID,
        quantity: Decimal,
        unit_cost_ars: Decimal,
        total_cost_ars: Decimal,
        supplier: str,
        created_by_user_id: uuid.UUID | None,
    ) -> InventoryMovement:
        return self._create_stock_movement(
            tenant_id,
            item.id,
            movement_type="purchase",
            quantity=quantity,
            reason="purchase_receipt",
            unit_cost_ars=unit_cost_ars,
            total_cost_ars=total_cost_ars,
            supplier=supplier,
            notes=f"Recepción de compra {purchase_id}",
            source_type="purchase",
            source_id=str(purchase_id),
            operation_id=operation_id,
            created_by_user_id=created_by_user_id,
            locked_item=item,
            commit=False,
        )

    def register_purchase_reversal_movement(
        self,
        tenant_id: uuid.UUID,
        *,
        item: InventoryItem,
        purchase_id: uuid.UUID,
        original: InventoryMovement,
        operation_id: uuid.UUID,
        reason: str,
        created_by_user_id: uuid.UUID | None,
    ) -> InventoryMovement:
        return self._create_stock_movement(
            tenant_id,
            item.id,
            movement_type="reversal",
            quantity=original.quantity,
            reason="purchase_receipt_reversal",
            notes=reason,
            source_type="purchase_reversal",
            source_id=str(purchase_id),
            operation_id=operation_id,
            reverses_movement_id=original.id,
            created_by_user_id=created_by_user_id,
            reverse_of=original,
            unit_override=original.unit,
            locked_item=item,
            commit=False,
        )

    def get_movement(self, tenant_id: uuid.UUID, movement_id: uuid.UUID) -> InventoryMovement:
        movement = self.inventory_repository.get_movement_by_id(tenant_id, movement_id)
        if movement is None:
            raise AppError(404, "inventory_movement_not_found", "Inventory movement not found")
        return movement

    def get_movement_reversal_status(self, movement: InventoryMovement) -> tuple[bool, str | None]:
        if movement.movement_type == "reversal":
            return False, "reversal_movements_cannot_be_reversed"
        if movement.movement_type == "purchase" and movement.source_type == "purchase":
            return False, "purchase_movement_requires_purchase_reversal"
        if movement.reversed_by_movement_id is not None:
            return False, "movement_already_reversed"
        if movement.movement_type in MOVEMENT_HISTORICAL_UNKNOWN_DIRECTION_TYPES:
            return False, "movement_type_not_reversible"

        direction = self._movement_direction(movement.movement_type)
        stock_after_reversal = movement.inventory_item.current_stock - (movement.quantity * direction)
        if stock_after_reversal < ZERO:
            return False, "insufficient_stock_for_reversal"
        return True, None

    def list_movements(
        self,
        tenant_id: uuid.UUID,
        *,
        item_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 10,
        movement_type: str | None = None,
        search: str | None = None,
        created_by_user_id: uuid.UUID | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        operation_id: uuid.UUID | None = None,
        reversal_status: str = "all",
        date_from: date | None = None,
        date_to: date | None = None,
        sort_direction: str = "desc",
    ) -> tuple[list[InventoryMovement], dict]:
        self._validate_pagination(page, page_size)
        if item_id is not None:
            self.get_item(tenant_id, item_id)
        if movement_type is not None and movement_type not in ALLOWED_MOVEMENT_TYPES:
            raise AppError(422, "validation_error", "Invalid movement_type value")
        if reversal_status not in {"all", "active", "reversed", "reversal"}:
            raise AppError(422, "validation_error", "Invalid reversal_status value")
        if sort_direction not in ALLOWED_SORT_ORDER:
            raise AppError(422, "validation_error", "Invalid sort_direction value")
        if date_from is not None and date_to is not None and date_from > date_to:
            raise AppError(422, "invalid_date_range", "date_from cannot be after date_to")

        date_from_dt = self._start_of_day(date_from)
        date_to_dt = self._end_of_day(date_to)
        movements, total = self.inventory_repository.list_movements(
            tenant_id,
            page=page,
            page_size=page_size,
            inventory_item_id=item_id,
            movement_type=movement_type,
            search=self._normalize_optional_string(search),
            created_by_user_id=created_by_user_id,
            source_type=self._normalize_optional_string(source_type),
            source_id=self._normalize_optional_string(source_id),
            operation_id=operation_id,
            reversal_status=reversal_status,
            date_from=date_from_dt,
            date_to=date_to_dt,
            sort_direction=sort_direction,
        )
        return movements, {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": ceil(total / page_size) if total else 0,
        }

    def _create_stock_movement(
        self,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        movement_type: str,
        quantity: Decimal,
        reason: str | None = None,
        unit_cost_ars: Decimal | None = None,
        total_cost_ars: Decimal | None = None,
        unit_sale_price_ars: Decimal | None = None,
        total_sale_price_ars: Decimal | None = None,
        supplier: str | None = None,
        notes: str | None = None,
        related_patient_id: uuid.UUID | None = None,
        related_consultation_id: uuid.UUID | None = None,
        created_by_user_id: uuid.UUID | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        operation_id: uuid.UUID | None = None,
        reverses_movement_id: uuid.UUID | None = None,
        reverse_of: InventoryMovement | None = None,
        unit_override: str | None = None,
        locked_item: InventoryItem | None = None,
        commit: bool = True,
    ) -> InventoryMovement:
        if movement_type not in ALLOWED_MOVEMENT_TYPES:
            raise AppError(422, "validation_error", "Invalid movement_type value")
        if quantity <= ZERO:
            raise AppError(422, "invalid_quantity", "Movement quantity must be greater than zero")

        item = locked_item or self.inventory_repository.get_item_by_id_for_update(
            tenant_id, item_id
        )
        if item is not None and (item.id != item_id or item.tenant_id != tenant_id):
            item = None
        if item is None:
            raise AppError(404, "inventory_item_not_found", "Inventory item not found")

        direction = (
            -self._movement_direction(reverse_of.movement_type)
            if movement_type == "reversal" and reverse_of is not None
            else self._movement_direction(movement_type)
        )
        stock_before = item.current_stock
        stock_after = stock_before + (quantity * Decimal(direction))
        if stock_after < ZERO:
            error_code = (
                "insufficient_stock_for_reversal"
                if movement_type == "reversal"
                else "insufficient_stock"
            )
            raise AppError(409, error_code, "Insufficient stock for this movement")

        movement = InventoryMovement(
            tenant_id=tenant_id,
            inventory_item_id=item.id,
            movement_type=movement_type,
            reason=reason,
            quantity=quantity,
            stock_before=stock_before,
            stock_after=stock_after,
            unit=unit_override or item.unit,
            unit_cost_ars=unit_cost_ars,
            total_cost_ars=total_cost_ars,
            unit_sale_price_ars=unit_sale_price_ars,
            total_sale_price_ars=total_sale_price_ars,
            supplier=supplier,
            notes=notes,
            related_patient_id=related_patient_id,
            related_consultation_id=related_consultation_id,
            created_by_user_id=created_by_user_id,
            source_type=source_type,
            source_id=source_id,
            operation_id=operation_id or uuid.uuid4(),
            reverses_movement_id=reverses_movement_id,
        )
        self.inventory_repository.create_movement(movement)

        updates = {"current_stock": stock_after}
        if movement_type == "manual_entry" and supplier:
            updates["supplier"] = supplier
        self.inventory_repository.update_item(item, updates)
        if not commit:
            return movement

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(
                409,
                "movement_already_reversed",
                "Inventory movement has already been reversed",
            ) from exc
        return self.get_movement(tenant_id, movement.id)

    def _movement_direction(self, movement_type: str) -> int:
        if movement_type in MOVEMENT_INCREASE_TYPES:
            return 1
        if movement_type in MOVEMENT_DECREASE_TYPES:
            return -1
        raise AppError(
            409,
            "movement_type_not_reversible",
            "This movement type does not have a stock direction",
        )

    def _resolve_sale_price(
        self,
        *,
        purchase_price_ars: Decimal | None,
        purchase_tax_rate_percentage: Decimal | None,
        profit_margin_percentage: Decimal | None,
        round_sale_price: bool,
        manual_sale_price_ars: Decimal | None,
    ) -> Decimal | None:
        if manual_sale_price_ars is not None:
            return self._quantize_money(manual_sale_price_ars)
        if purchase_price_ars is None or profit_margin_percentage is None:
            return None
        purchase_price_with_tax = self._price_with_tax(
            purchase_price_ars,
            purchase_tax_rate_percentage,
        )
        sale_price = purchase_price_with_tax * (
            Decimal("1") + (profit_margin_percentage / HUNDRED)
        )
        sale_price = self._quantize_money(sale_price)
        if round_sale_price:
            sale_price = self._round_to_nearest_ten(sale_price)
        return sale_price

    def _should_recalculate_sale_price(self, updates: dict) -> bool:
        if "sale_price_ars" in updates:
            return True
        return bool(
            {
                "purchase_price_ars",
                "purchase_tax_rate_percentage",
                "profit_margin_percentage",
                "round_sale_price",
            }
            & set(updates)
        )

    def _price_with_tax(
        self,
        price: Decimal,
        tax_rate_percentage: Decimal | None,
    ) -> Decimal:
        tax_rate = tax_rate_percentage if tax_rate_percentage is not None else ZERO
        tax_amount = self._quantize_money(price * tax_rate / HUNDRED)
        return self._quantize_money(price + tax_amount)

    def _round_to_nearest_ten(self, value: Decimal) -> Decimal:
        return (value / TEN).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * TEN

    def _quantize_money(self, value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _validate_non_negative_prices(
        self,
        purchase_price_ars: Decimal | None,
        profit_margin_percentage: Decimal | None,
        sale_price_ars: Decimal | None,
    ) -> None:
        for value in (purchase_price_ars, profit_margin_percentage, sale_price_ars):
            if value is not None and value < ZERO:
                raise AppError(422, "invalid_price", "Price values cannot be negative")

    def _validate_tax_rates(
        self,
        purchase_tax_rate_percentage: Decimal | None,
        sale_tax_rate_percentage: Decimal | None,
    ) -> None:
        for value in (
            purchase_tax_rate_percentage,
            sale_tax_rate_percentage,
        ):
            if value is not None and (value < ZERO or value > HUNDRED):
                raise AppError(
                    422,
                    "invalid_tax_rate",
                    "Tax rates must be between 0 and 100",
                )

    def _validate_pagination(self, page: int, page_size: int) -> None:
        if page < 1 or page_size < 1 or page_size > 100:
            raise AppError(422, "invalid_pagination", "Invalid pagination parameters")

    def _normalize_optional_string(self, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    def _start_of_day(self, value: date | None) -> datetime | None:
        if value is None:
            return None
        return datetime.combine(value, time.min, tzinfo=UTC)

    def _end_of_day(self, value: date | None) -> datetime | None:
        if value is None:
            return None
        return datetime.combine(value, time.max, tzinfo=UTC)

    def _validate_optional_user(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> None:
        if user_id is None:
            return
        user = self.user_repository.get_by_id(tenant_id, user_id)
        if user is not None:
            return
        user_any_tenant = self.db.get(User, user_id)
        if user_any_tenant is not None:
            raise AppError(
                409,
                "invalid_cross_tenant_access",
                "User does not belong to the provided tenant",
            )
        raise AppError(404, "user_not_found", "User not found")

    def _validate_optional_patient(
        self,
        tenant_id: uuid.UUID,
        patient_id: uuid.UUID | None,
    ) -> None:
        if patient_id is None:
            return
        patient = self.patient_repository.get_by_id(tenant_id, patient_id)
        if patient is not None:
            return
        patient_any_tenant = self.db.get(Patient, patient_id)
        if patient_any_tenant is not None:
            raise AppError(
                409,
                "invalid_cross_tenant_access",
                "Patient does not belong to the provided tenant",
            )
        raise AppError(404, "patient_not_found", "Patient not found")

    def _validate_optional_consultation(
        self,
        tenant_id: uuid.UUID,
        consultation_id: uuid.UUID | None,
    ) -> None:
        if consultation_id is None:
            return
        consultation = self.db.scalar(
            select(Consultation).where(
                Consultation.id == consultation_id,
                Consultation.tenant_id == tenant_id,
            )
        )
        if consultation is not None:
            return
        consultation_any_tenant = self.db.get(Consultation, consultation_id)
        if consultation_any_tenant is not None:
            raise AppError(
                409,
                "invalid_cross_tenant_access",
                "Consultation does not belong to the provided tenant",
            )
        raise AppError(404, "consultation_not_found", "Consultation not found")

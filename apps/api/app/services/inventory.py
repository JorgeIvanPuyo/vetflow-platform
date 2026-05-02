from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP
from math import ceil

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
)


ALLOWED_SORT_BY = {"name", "current_stock", "expiration_date", "created_at", "updated_at"}
ALLOWED_SORT_ORDER = {"asc", "desc"}
ZERO = Decimal("0")
TEN = Decimal("10")


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
        self._validate_optional_user(tenant_id, created_by_user_id)

        item_data = payload.model_dump()
        item_data["sale_price_ars"] = self._resolve_sale_price(
            purchase_price_ars=payload.purchase_price_ars,
            profit_margin_percentage=payload.profit_margin_percentage,
            round_sale_price=payload.round_sale_price,
            manual_sale_price_ars=payload.sale_price_ars,
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
        q: str | None = None,
        category: str | None = None,
        supplier: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 10,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> tuple[list[InventoryItem], dict]:
        self._validate_pagination(page, page_size)
        resolved_sort_by = sort_by or "created_at"
        resolved_sort_order = sort_order or "desc"
        if resolved_sort_by not in ALLOWED_SORT_BY:
            raise AppError(422, "validation_error", "Invalid sort_by value")
        if resolved_sort_order not in ALLOWED_SORT_ORDER:
            raise AppError(422, "validation_error", "Invalid sort_order value")

        items, total = self.inventory_repository.list_items(
            tenant_id,
            q=q,
            category=category,
            supplier=supplier,
            status=status,
            page=page,
            page_size=page_size,
            sort_by=resolved_sort_by,
            sort_order=resolved_sort_order,
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
        self._validate_non_negative_prices(
            updates.get("purchase_price_ars", item.purchase_price_ars),
            updates.get("profit_margin_percentage", item.profit_margin_percentage),
            updates.get("sale_price_ars", item.sale_price_ars),
        )

        if self._should_recalculate_sale_price(updates):
            updates["sale_price_ars"] = self._resolve_sale_price(
                purchase_price_ars=updates.get("purchase_price_ars", item.purchase_price_ars),
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

    def register_entry_movement(
        self,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: InventoryMovementEntryCreate,
        *,
        created_by_user_id: uuid.UUID | None = None,
    ) -> InventoryMovement:
        item = self.get_item(tenant_id, item_id)
        self._validate_optional_user(tenant_id, created_by_user_id)

        quantity = payload.quantity
        unit_cost = payload.unit_cost_ars
        total_cost = payload.total_cost_ars
        if total_cost is not None and unit_cost is None:
            unit_cost = self._quantize_money(total_cost / quantity)
        elif unit_cost is not None and total_cost is None:
            total_cost = self._quantize_money(unit_cost * quantity)

        movement = InventoryMovement(
            tenant_id=tenant_id,
            inventory_item_id=item.id,
            movement_type="entry",
            quantity=quantity,
            unit_cost_ars=unit_cost,
            total_cost_ars=total_cost,
            supplier=payload.supplier,
            notes=payload.notes,
            created_by_user_id=created_by_user_id,
        )
        self.inventory_repository.create_movement(movement)

        updates = {"current_stock": item.current_stock + quantity}
        if payload.supplier:
            updates["supplier"] = payload.supplier
        self.inventory_repository.update_item(item, updates)
        self.db.commit()
        return movement

    def register_exit_movement(
        self,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: InventoryMovementExitCreate,
        *,
        created_by_user_id: uuid.UUID | None = None,
    ) -> InventoryMovement:
        item = self.get_item(tenant_id, item_id)
        self._validate_optional_user(tenant_id, created_by_user_id)
        self._validate_optional_patient(tenant_id, payload.related_patient_id)
        self._validate_optional_consultation(tenant_id, payload.related_consultation_id)

        if item.current_stock - payload.quantity < ZERO:
            raise AppError(409, "insufficient_stock", "Insufficient stock for this movement")

        unit_sale_price = payload.unit_sale_price_ars or item.sale_price_ars
        total_sale_price = None
        if unit_sale_price is not None:
            total_sale_price = self._quantize_money(unit_sale_price * payload.quantity)

        movement = InventoryMovement(
            tenant_id=tenant_id,
            inventory_item_id=item.id,
            movement_type="exit",
            reason=payload.reason,
            quantity=payload.quantity,
            unit_sale_price_ars=unit_sale_price,
            total_sale_price_ars=total_sale_price,
            notes=payload.notes,
            related_patient_id=payload.related_patient_id,
            related_consultation_id=payload.related_consultation_id,
            created_by_user_id=created_by_user_id,
        )
        self.inventory_repository.create_movement(movement)
        self.inventory_repository.update_item(
            item,
            {"current_stock": item.current_stock - payload.quantity},
        )
        self.db.commit()
        return movement

    def list_movements(
        self,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = 10,
        movement_type: str | None = None,
    ) -> tuple[list[InventoryMovement], dict]:
        self.get_item(tenant_id, item_id)
        self._validate_pagination(page, page_size)
        movements, total = self.inventory_repository.list_movements(
            tenant_id,
            item_id,
            page=page,
            page_size=page_size,
            movement_type=movement_type,
        )
        return movements, {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": ceil(total / page_size) if total else 0,
        }

    def _resolve_sale_price(
        self,
        *,
        purchase_price_ars: Decimal | None,
        profit_margin_percentage: Decimal | None,
        round_sale_price: bool,
        manual_sale_price_ars: Decimal | None,
    ) -> Decimal | None:
        if manual_sale_price_ars is not None:
            return self._quantize_money(manual_sale_price_ars)
        if purchase_price_ars is None or profit_margin_percentage is None:
            return None
        sale_price = purchase_price_ars * (Decimal("1") + (profit_margin_percentage / Decimal("100")))
        sale_price = self._quantize_money(sale_price)
        if round_sale_price:
            sale_price = self._round_to_nearest_ten(sale_price)
        return sale_price

    def _should_recalculate_sale_price(self, updates: dict) -> bool:
        if "sale_price_ars" in updates:
            return True
        return bool(
            {"purchase_price_ars", "profit_margin_percentage", "round_sale_price"} & set(updates)
        )

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

    def _validate_pagination(self, page: int, page_size: int) -> None:
        if page < 1 or page_size < 1 or page_size > 50:
            raise AppError(422, "invalid_pagination", "Invalid pagination parameters")

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
        consultation = self.db.get(Consultation, consultation_id)
        if consultation is None:
            raise AppError(404, "consultation_not_found", "Consultation not found")
        if consultation.tenant_id != tenant_id:
            raise AppError(
                409,
                "invalid_cross_tenant_access",
                "Consultation does not belong to the provided tenant",
            )

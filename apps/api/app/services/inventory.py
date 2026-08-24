from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP
from math import ceil

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.catalog_item import CatalogItem
from app.models.consultation import Consultation
from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.patient import Patient
from app.models.supplier import Supplier
from app.models.user import User
from app.repositories.clinic import ClinicRepository
from app.repositories.inventory import InventoryRepository
from app.repositories.patient import PatientRepository
from app.repositories.supplier import SupplierRepository
from app.repositories.user import UserRepository
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryMovementEntryCreate,
    InventoryMovementExitCreate,
)


CATEGORY_CATALOG_TYPE = "inventory_category"


ALLOWED_SORT_BY = {"name", "current_stock", "expiration_date", "created_at", "updated_at"}
ALLOWED_SORT_ORDER = {"asc", "desc"}
ZERO = Decimal("0")
HUNDRED = Decimal("100")
FALLBACK_PURCHASE_TAX_RATE = Decimal("0")
FALLBACK_SALE_TAX_RATE = Decimal("0")
FALLBACK_PROFIT_MARGIN = Decimal("35")
FALLBACK_ROUNDING_INCREMENT = Decimal("10")


class InventoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.inventory_repository = InventoryRepository(db)
        self.patient_repository = PatientRepository(db)
        self.user_repository = UserRepository(db)
        self.clinic_repository = ClinicRepository(db)
        self.supplier_repository = SupplierRepository(db)

    def create_item(
        self,
        tenant_id: uuid.UUID,
        payload: InventoryItemCreate,
        *,
        created_by_user_id: uuid.UUID | None = None,
    ) -> InventoryItem:
        defaults = self._resolve_pricing_defaults(tenant_id)
        purchase_tax_rate = (
            payload.purchase_tax_rate_percentage
            if payload.purchase_tax_rate_percentage is not None
            else defaults["purchase_tax_rate"]
        )
        profit_margin = (
            payload.profit_margin_percentage
            if payload.profit_margin_percentage is not None
            else defaults["profit_margin"]
        )
        sale_tax_rate = (
            payload.sale_tax_rate_percentage
            if payload.sale_tax_rate_percentage is not None
            else defaults["sale_tax_rate"]
        )

        self._validate_non_negative_prices(
            payload.purchase_price_ars,
            profit_margin,
            payload.sale_price_ars,
        )
        self._validate_tax_rates(purchase_tax_rate, sale_tax_rate)
        self._validate_optional_user(tenant_id, created_by_user_id)
        self._validate_optional_supplier(tenant_id, payload.supplier_id)
        self._validate_optional_category_catalog_item(
            tenant_id,
            payload.category_catalog_item_id,
        )

        item_data = payload.model_dump()
        item_data["purchase_tax_rate_percentage"] = purchase_tax_rate
        item_data["profit_margin_percentage"] = profit_margin
        item_data["sale_tax_rate_percentage"] = sale_tax_rate
        item_data["sale_price_ars"] = self._resolve_sale_price(
            purchase_price_ars=payload.purchase_price_ars,
            purchase_tax_rate_percentage=purchase_tax_rate,
            profit_margin_percentage=profit_margin,
            round_sale_price=payload.round_sale_price,
            manual_sale_price_ars=payload.sale_price_ars,
            rounding_increment=defaults["rounding_increment"],
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
        defaults = self._resolve_pricing_defaults(tenant_id)
        for field, default_value in (
            ("purchase_tax_rate_percentage", defaults["purchase_tax_rate"]),
            ("sale_tax_rate_percentage", defaults["sale_tax_rate"]),
            ("profit_margin_percentage", defaults["profit_margin"]),
        ):
            if field in updates and updates[field] is None:
                updates[field] = default_value
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
        if "supplier_id" in updates:
            self._validate_optional_supplier(tenant_id, updates["supplier_id"])
        if "category_catalog_item_id" in updates:
            self._validate_optional_category_catalog_item(
                tenant_id,
                updates["category_catalog_item_id"],
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
                rounding_increment=defaults["rounding_increment"],
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

    def _resolve_pricing_defaults(self, tenant_id: uuid.UUID) -> dict[str, Decimal]:
        preferences = self.clinic_repository.get_preferences(tenant_id)
        if preferences is None:
            return {
                "purchase_tax_rate": FALLBACK_PURCHASE_TAX_RATE,
                "sale_tax_rate": FALLBACK_SALE_TAX_RATE,
                "profit_margin": FALLBACK_PROFIT_MARGIN,
                "rounding_increment": FALLBACK_ROUNDING_INCREMENT,
            }
        return {
            "purchase_tax_rate": preferences.default_purchase_tax_rate,
            "sale_tax_rate": preferences.default_sale_tax_rate,
            "profit_margin": preferences.default_profit_margin,
            "rounding_increment": preferences.money_rounding_increment,
        }

    def _resolve_sale_price(
        self,
        *,
        purchase_price_ars: Decimal | None,
        purchase_tax_rate_percentage: Decimal | None,
        profit_margin_percentage: Decimal | None,
        round_sale_price: bool,
        manual_sale_price_ars: Decimal | None,
        rounding_increment: Decimal,
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
            sale_price = self._round_to_increment(sale_price, rounding_increment)
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

    def _round_to_increment(self, value: Decimal, increment: Decimal) -> Decimal:
        return (value / increment).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * increment

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

    def _validate_optional_supplier(
        self,
        tenant_id: uuid.UUID,
        supplier_id: uuid.UUID | None,
    ) -> None:
        if supplier_id is None:
            return
        supplier = self.supplier_repository.get_by_id(tenant_id, supplier_id)
        if supplier is not None:
            if not supplier.is_active:
                raise AppError(409, "inactive_supplier", "Supplier is inactive")
            return
        supplier_any_tenant = self.db.get(Supplier, supplier_id)
        if supplier_any_tenant is not None:
            raise AppError(
                409,
                "invalid_cross_tenant_access",
                "Supplier does not belong to the provided tenant",
            )
        raise AppError(404, "supplier_not_found", "Supplier not found")

    def _validate_optional_category_catalog_item(
        self,
        tenant_id: uuid.UUID,
        catalog_item_id: uuid.UUID | None,
    ) -> None:
        if catalog_item_id is None:
            return
        catalog_item = self.db.get(CatalogItem, catalog_item_id)
        if catalog_item is None:
            raise AppError(404, "catalog_item_not_found", "Catalog item not found")
        if catalog_item.tenant_id != tenant_id:
            raise AppError(
                409,
                "invalid_cross_tenant_access",
                "Catalog item does not belong to the provided tenant",
            )
        if catalog_item.catalog_type != CATEGORY_CATALOG_TYPE:
            raise AppError(
                422,
                "invalid_catalog_item_type",
                f"Catalog item must be of type {CATEGORY_CATALOG_TYPE}",
            )
        if not catalog_item.is_active:
            raise AppError(409, "inactive_catalog_item", "Catalog item is inactive")

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

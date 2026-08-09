from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from math import ceil

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.purchase import Purchase, PurchaseItem
from app.repositories.purchase import PurchaseRepository
from app.repositories.supplier import SupplierRepository
from app.repositories.user import UserRepository
from app.schemas.purchase import PurchaseCancel, PurchaseCreate, PurchaseUpdate


MONEY_QUANTUM = Decimal("0.01")
QUANTITY_QUANTUM = Decimal("0.01")
HUNDRED = Decimal("100")
ZERO = Decimal("0.00")
ALLOWED_SORT_BY = {"purchase_date", "created_at", "total_ars", "supplier_name"}
ALLOWED_SORT_DIRECTIONS = {"asc", "desc"}


class PurchaseService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = PurchaseRepository(db)
        self.supplier_repository = SupplierRepository(db)
        self.user_repository = UserRepository(db)

    def create(
        self,
        tenant_id: uuid.UUID,
        payload: PurchaseCreate,
        *,
        created_by_user_id: uuid.UUID | None,
    ) -> Purchase:
        self._validate_optional_user(tenant_id, created_by_user_id)
        supplier = self._get_active_supplier(tenant_id, payload.supplier_id)
        items, totals = self._build_items(tenant_id, payload.items)
        purchase = Purchase(
            tenant_id=tenant_id,
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            supplier_tax_id=supplier.tax_id,
            purchase_date=payload.purchase_date,
            document_type=payload.document_type,
            document_number=payload.document_number,
            currency="ARS",
            notes=payload.notes,
            status="draft",
            created_by_user_id=created_by_user_id,
            **totals,
        )
        for item in items:
            purchase.items.append(item)
        try:
            self.repository.create(purchase)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, purchase.id)

    def get(self, tenant_id: uuid.UUID, purchase_id: uuid.UUID) -> Purchase:
        purchase = self.repository.get_by_id(tenant_id, purchase_id)
        if purchase is None:
            raise AppError(404, "purchase_not_found", "Compra no encontrada")
        return purchase

    def list(
        self,
        tenant_id: uuid.UUID,
        *,
        search: str | None,
        supplier: str | None,
        supplier_id: uuid.UUID | None,
        status: str | None,
        document_type: str | None,
        date_from,
        date_to,
        created_by_user_id: uuid.UUID | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_direction: str,
    ) -> tuple[list[dict], dict]:
        if sort_by not in ALLOWED_SORT_BY:
            raise AppError(422, "validation_error", "Invalid sort_by value")
        if sort_direction not in ALLOWED_SORT_DIRECTIONS:
            raise AppError(422, "validation_error", "Invalid sort_direction value")
        if date_from and date_to and date_from > date_to:
            raise AppError(422, "validation_error", "date_from must be before date_to")
        rows, total = self.repository.list(
            tenant_id,
            search=self._normalize_filter(search),
            supplier=self._normalize_filter(supplier),
            supplier_id=supplier_id,
            status=status,
            document_type=document_type,
            date_from=date_from,
            date_to=date_to,
            created_by_user_id=created_by_user_id,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_direction=sort_direction,
        )
        data = [
            {
                "id": purchase.id,
                "supplier_id": purchase.supplier_id,
                "supplier_name": purchase.supplier_name,
                "supplier_tax_id": purchase.supplier_tax_id,
                "purchase_date": purchase.purchase_date,
                "document_type": purchase.document_type,
                "document_number": purchase.document_number,
                "currency": purchase.currency,
                "subtotal_ars": purchase.subtotal_ars,
                "tax_total_ars": purchase.tax_total_ars,
                "total_ars": purchase.total_ars,
                "status": purchase.status,
                "item_count": item_count,
                "created_by_user_id": purchase.created_by_user_id,
                "created_by_user_name": purchase.created_by_user_name,
                "created_by_user_email": purchase.created_by_user_email,
                "created_at": purchase.created_at,
                "updated_at": purchase.updated_at,
            }
            for purchase, item_count in rows
        ]
        return data, {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": ceil(total / page_size) if total else 0,
        }

    def update(
        self,
        tenant_id: uuid.UUID,
        purchase_id: uuid.UUID,
        payload: PurchaseUpdate,
    ) -> Purchase:
        purchase = self.repository.get_by_id(tenant_id, purchase_id, for_update=True)
        if purchase is None:
            raise AppError(404, "purchase_not_found", "Compra no encontrada")
        self._require_draft(purchase, "editar")

        updates = payload.model_dump(exclude_unset=True, exclude={"items", "supplier_id"})
        if "supplier_id" in payload.model_fields_set and payload.supplier_id != purchase.supplier_id:
            supplier = self._get_active_supplier(tenant_id, payload.supplier_id)
            purchase.supplier_id = supplier.id
            purchase.supplier_name = supplier.name
            purchase.supplier_tax_id = supplier.tax_id
        for field_name, value in updates.items():
            setattr(purchase, field_name, value)
        if "items" in payload.model_fields_set:
            items, totals = self._build_items(tenant_id, payload.items or [])
            self.repository.replace_items(purchase, items)
            for field_name, value in totals.items():
                setattr(purchase, field_name, value)
        purchase.updated_at = datetime.now(UTC)
        try:
            self.db.add(purchase)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, purchase_id)

    def cancel(
        self,
        tenant_id: uuid.UUID,
        purchase_id: uuid.UUID,
        payload: PurchaseCancel,
        *,
        cancelled_by_user_id: uuid.UUID | None,
    ) -> Purchase:
        self._validate_optional_user(tenant_id, cancelled_by_user_id)
        purchase = self.repository.get_by_id(tenant_id, purchase_id, for_update=True)
        if purchase is None:
            raise AppError(404, "purchase_not_found", "Compra no encontrada")
        self._require_draft(purchase, "cancelar")
        now = datetime.now(UTC)
        purchase.status = "cancelled"
        purchase.cancelled_at = now
        purchase.cancelled_by_user_id = cancelled_by_user_id
        purchase.cancellation_reason = payload.reason
        purchase.updated_at = now
        try:
            self.db.add(purchase)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, purchase_id)

    def _build_items(self, tenant_id: uuid.UUID, payload_items) -> tuple[list[PurchaseItem], dict]:
        if not payload_items:
            raise AppError(422, "purchase_items_required", "La compra requiere al menos una línea")
        item_ids = [item.inventory_item_id for item in payload_items]
        if len(set(item_ids)) != len(item_ids):
            raise AppError(422, "duplicate_purchase_item", "No se puede repetir un producto")
        inventory_items = self.repository.list_inventory_items_by_ids(tenant_id, item_ids)
        by_id = {item.id: item for item in inventory_items}
        if len(by_id) != len(item_ids):
            raise AppError(404, "inventory_item_not_found", "Producto no encontrado")

        items: list[PurchaseItem] = []
        subtotal = ZERO
        tax_total = ZERO
        total = ZERO
        for index, payload_item in enumerate(payload_items, start=1):
            inventory_item = by_id[payload_item.inventory_item_id]
            quantity = payload_item.quantity.quantize(QUANTITY_QUANTUM, rounding=ROUND_HALF_UP)
            if quantity <= 0:
                raise AppError(422, "invalid_purchase_quantity", "La cantidad debe ser mayor que cero")
            unit_price = self._money(payload_item.unit_price_without_tax_ars)
            tax_rate = payload_item.tax_rate_percentage.quantize(
                MONEY_QUANTUM, rounding=ROUND_HALF_UP
            )
            line_subtotal = self._money(quantity * unit_price)
            line_tax = self._money(line_subtotal * tax_rate / HUNDRED)
            line_total = self._money(line_subtotal + line_tax)
            unit_tax = self._money(unit_price * tax_rate / HUNDRED)
            items.append(
                PurchaseItem(
                    tenant_id=tenant_id,
                    inventory_item_id=inventory_item.id,
                    line_number=index,
                    description_snapshot=inventory_item.name,
                    internal_code_snapshot=inventory_item.internal_code,
                    unit=inventory_item.unit,
                    quantity=quantity,
                    unit_price_without_tax_ars=unit_price,
                    tax_rate_percentage=tax_rate,
                    unit_price_with_tax_ars=self._money(unit_price + unit_tax),
                    line_subtotal_ars=line_subtotal,
                    line_tax_ars=line_tax,
                    line_total_ars=line_total,
                )
            )
            subtotal += line_subtotal
            tax_total += line_tax
            total += line_total
        return items, {
            "subtotal_ars": self._money(subtotal),
            "tax_total_ars": self._money(tax_total),
            "total_ars": self._money(total),
        }

    def _validate_optional_user(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID | None
    ) -> None:
        if user_id is not None and self.user_repository.get_by_id(tenant_id, user_id) is None:
            raise AppError(404, "user_not_found", "Usuario no encontrado")

    def _get_active_supplier(
        self, tenant_id: uuid.UUID, supplier_id: uuid.UUID | None
    ):
        if supplier_id is None:
            raise AppError(422, "supplier_required", "La compra requiere un proveedor")
        supplier = self.supplier_repository.get_by_id(tenant_id, supplier_id)
        if supplier is None:
            raise AppError(404, "supplier_not_found", "Proveedor no encontrado")
        if not supplier.is_active:
            raise AppError(
                409,
                "supplier_inactive",
                "El proveedor seleccionado está inactivo",
            )
        return supplier

    def _require_draft(self, purchase: Purchase, action: str) -> None:
        if purchase.status != "draft":
            raise AppError(
                409,
                "purchase_not_editable",
                f"Sólo se puede {action} una compra en borrador",
            )

    def _money(self, value: Decimal) -> Decimal:
        return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)

    def _normalize_filter(self, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

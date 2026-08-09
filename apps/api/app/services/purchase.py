from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from math import ceil

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.purchase import Purchase, PurchaseItem
from app.repositories.inventory import InventoryRepository
from app.repositories.purchase import PurchaseRepository
from app.repositories.supplier import SupplierRepository
from app.repositories.user import UserRepository
from app.schemas.purchase import (
    PurchaseCancel,
    PurchaseCreate,
    PurchaseListSummaryRead,
    PurchaseUpdate,
)
from app.services.inventory import InventoryService


MONEY_QUANTUM = Decimal("0.01")
QUANTITY_QUANTUM = Decimal("0.01")
HUNDRED = Decimal("100")
ZERO = Decimal("0.00")
ALLOWED_SORT_BY = {
    "purchase_date",
    "created_at",
    "total_ars",
    "supplier_name",
    "status",
}
ALLOWED_SORT_DIRECTIONS = {"asc", "desc"}


class PurchaseService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = PurchaseRepository(db)
        self.inventory_repository = InventoryRepository(db)
        self.inventory_service = InventoryService(db)
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
        attachment_status: str | None,
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
        rows, summary = self.repository.list(
            tenant_id,
            search=self._normalize_filter(search),
            supplier=self._normalize_filter(supplier),
            supplier_id=supplier_id,
            status=status,
            document_type=document_type,
            date_from=date_from,
            date_to=date_to,
            created_by_user_id=created_by_user_id,
            attachment_status=attachment_status,
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
                "attachment_status": "attached" if has_attachment else "pending",
                "created_by_user_id": purchase.created_by_user_id,
                "created_by_user_name": purchase.created_by_user_name,
                "created_by_user_email": purchase.created_by_user_email,
                "created_at": purchase.created_at,
                "updated_at": purchase.updated_at,
                "return_status": return_status,
            }
            for purchase, item_count, has_attachment, return_status in rows
        ]
        total = int(summary["purchase_count"] or 0)
        list_summary = PurchaseListSummaryRead(
            purchase_count=total,
            subtotal_ars=self._money(Decimal(summary["subtotal_ars"] or 0)),
            tax_total_ars=self._money(Decimal(summary["tax_total_ars"] or 0)),
            total_ars=self._money(Decimal(summary["total_ars"] or 0)),
        ).model_dump(mode="json")
        return data, {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": ceil(total / page_size) if total else 0,
            "summary": list_summary,
        }

    def list_creator_options(self, tenant_id: uuid.UUID) -> list[dict]:
        return self.repository.list_creator_options(tenant_id)

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

    def receive(
        self,
        tenant_id: uuid.UUID,
        purchase_id: uuid.UUID,
        *,
        received_by_user_id: uuid.UUID | None,
    ) -> Purchase:
        self._validate_optional_user(tenant_id, received_by_user_id)
        try:
            purchase = self.repository.get_by_id(tenant_id, purchase_id, for_update=True)
            if purchase is None:
                raise AppError(404, "purchase_not_found", "Compra no encontrada")
            if purchase.status != "draft":
                raise AppError(
                    409,
                    "purchase_not_receivable",
                    "Sólo se puede recibir una compra en borrador",
                )
            if not purchase.items:
                raise AppError(
                    409,
                    "purchase_items_required",
                    "La compra requiere al menos una línea",
                )
            if any(
                line.quantity != line.quantity.to_integral_value()
                for line in purchase.items
            ):
                raise AppError(
                    409,
                    "purchase_quantity_must_be_integer",
                    "Todas las cantidades de la compra deben ser números enteros mayores que cero",
                )

            lines_by_item_id = {line.inventory_item_id: line for line in purchase.items}
            item_ids = sorted(lines_by_item_id)
            locked_items = self.inventory_repository.list_items_by_ids_for_update(
                tenant_id, item_ids
            )
            if len(locked_items) != len(item_ids):
                raise AppError(404, "inventory_item_not_found", "Producto no encontrado")

            operation_id = uuid.uuid4()
            for item in locked_items:
                line = lines_by_item_id[item.id]
                line.previous_purchase_price_ars = item.purchase_price_ars
                line.previous_purchase_tax_rate_percentage = (
                    item.purchase_tax_rate_percentage
                )
                self.inventory_service.register_purchase_movement(
                    tenant_id,
                    item=item,
                    purchase_id=purchase.id,
                    operation_id=operation_id,
                    quantity=line.quantity,
                    unit_cost_ars=line.unit_price_without_tax_ars,
                    total_cost_ars=line.line_subtotal_ars,
                    supplier=purchase.supplier_name,
                    created_by_user_id=received_by_user_id,
                )
                self.inventory_repository.update_item(
                    item,
                    {
                        "purchase_price_ars": line.unit_price_without_tax_ars,
                        "purchase_tax_rate_percentage": line.tax_rate_percentage,
                    },
                )

            now = datetime.now(UTC)
            purchase.status = "received"
            purchase.received_at = now
            purchase.received_by_user_id = received_by_user_id
            purchase.inventory_operation_id = operation_id
            purchase.updated_at = now
            self.repository.save(purchase)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, purchase_id)

    def reverse_receipt(
        self,
        tenant_id: uuid.UUID,
        purchase_id: uuid.UUID,
        *,
        reason: str,
        reversed_by_user_id: uuid.UUID | None,
    ) -> Purchase:
        self._validate_optional_user(tenant_id, reversed_by_user_id)
        try:
            purchase = self.repository.get_by_id(tenant_id, purchase_id, for_update=True)
            if purchase is None:
                raise AppError(404, "purchase_not_found", "Compra no encontrada")
            if purchase.status != "received":
                raise AppError(
                    409,
                    "purchase_receipt_not_reversible",
                    "Sólo se puede revertir una compra recibida",
                )
            if purchase.confirmed_return_count > 0:
                raise AppError(
                    409,
                    "purchase_receipt_has_confirmed_returns",
                    "No se puede revertir una recepción con devoluciones confirmadas",
                )
            if purchase.inventory_operation_id is None:
                raise AppError(
                    409,
                    "purchase_receipt_movements_inconsistent",
                    "La recepción no tiene una operación de inventario válida",
                )

            originals = self.inventory_repository.list_purchase_movements_for_update(
                tenant_id,
                purchase_id=purchase.id,
                operation_id=purchase.inventory_operation_id,
            )
            lines_by_item_id = {line.inventory_item_id: line for line in purchase.items}
            originals_by_item_id = {
                movement.inventory_item_id: movement for movement in originals
            }
            if (
                len(originals) != len(purchase.items)
                or len(originals_by_item_id) != len(lines_by_item_id)
                or set(originals_by_item_id) != set(lines_by_item_id)
                or any(
                    originals_by_item_id[item_id].quantity != line.quantity
                    for item_id, line in lines_by_item_id.items()
                )
            ):
                raise AppError(
                    409,
                    "purchase_receipt_movements_inconsistent",
                    "Los movimientos de la recepción están incompletos o son inconsistentes",
                )
            if self.inventory_repository.list_reversals_for_movements(
                tenant_id, [movement.id for movement in originals]
            ):
                raise AppError(
                    409,
                    "purchase_receipt_already_reversed",
                    "La recepción ya contiene movimientos revertidos",
                )

            locked_items = self.inventory_repository.list_items_by_ids_for_update(
                tenant_id, sorted(lines_by_item_id)
            )
            if len(locked_items) != len(lines_by_item_id):
                raise AppError(404, "inventory_item_not_found", "Producto no encontrado")
            for item in locked_items:
                if item.current_stock < originals_by_item_id[item.id].quantity:
                    raise AppError(
                        409,
                        "insufficient_stock_for_reversal",
                        "El stock actual no permite revertir la recepción completa",
                    )

            reversal_operation_id = uuid.uuid4()
            cost_warning = False
            for item in locked_items:
                line = lines_by_item_id[item.id]
                original = originals_by_item_id[item.id]
                self.inventory_service.register_purchase_reversal_movement(
                    tenant_id,
                    item=item,
                    purchase_id=purchase.id,
                    original=original,
                    operation_id=reversal_operation_id,
                    reason=reason,
                    created_by_user_id=reversed_by_user_id,
                )
                if (
                    item.purchase_price_ars == line.unit_price_without_tax_ars
                    and item.purchase_tax_rate_percentage == line.tax_rate_percentage
                ):
                    self.inventory_repository.update_item(
                        item,
                        {
                            "purchase_price_ars": line.previous_purchase_price_ars,
                            "purchase_tax_rate_percentage": (
                                line.previous_purchase_tax_rate_percentage
                            ),
                        },
                    )
                else:
                    cost_warning = True

            now = datetime.now(UTC)
            purchase.status = "reversed"
            purchase.reversed_at = now
            purchase.reversed_by_user_id = reversed_by_user_id
            purchase.reversal_reason = reason
            purchase.reversal_operation_id = reversal_operation_id
            purchase.reversal_cost_warning = cost_warning
            purchase.updated_at = now
            self.repository.save(purchase)
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

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from math import ceil

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.purchase import Purchase, PurchaseItem
from app.models.purchase_return import PurchaseReturn, PurchaseReturnItem
from app.repositories.inventory import InventoryRepository
from app.repositories.purchase import PurchaseRepository
from app.repositories.purchase_return import PurchaseReturnRepository
from app.repositories.user import UserRepository
from app.schemas.purchase_return import PurchaseReturnCreate, PurchaseReturnUpdate
from app.services.inventory import InventoryService


MONEY_QUANTUM = Decimal("0.01")
QUANTITY_QUANTUM = Decimal("0.01")
HUNDRED = Decimal("100")
ZERO = Decimal("0")
ALLOWED_SORT_BY = {
    "return_date",
    "created_at",
    "total_ars",
    "supplier_name",
    "status",
}
ALLOWED_SORT_DIRECTIONS = {"asc", "desc"}


class PurchaseReturnService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = PurchaseReturnRepository(db)
        self.purchase_repository = PurchaseRepository(db)
        self.inventory_repository = InventoryRepository(db)
        self.inventory_service = InventoryService(db)
        self.user_repository = UserRepository(db)

    def create(
        self,
        tenant_id: uuid.UUID,
        purchase_id: uuid.UUID,
        payload: PurchaseReturnCreate,
        *,
        created_by_user_id: uuid.UUID | None,
    ) -> PurchaseReturn:
        self._validate_optional_user(tenant_id, created_by_user_id)
        try:
            purchase = self._get_received_purchase(
                tenant_id, purchase_id, for_update=True
            )
            confirmed = self.repository.confirmed_quantities_by_purchase_item(
                tenant_id, purchase.id
            )
            items, totals = self._build_items(
                tenant_id, purchase, payload.items, confirmed
            )
            purchase_return = PurchaseReturn(
                tenant_id=tenant_id,
                purchase_id=purchase.id,
                supplier_id=purchase.supplier_id,
                supplier_name=purchase.supplier_name,
                supplier_tax_id=purchase.supplier_tax_id,
                return_date=payload.return_date,
                status="draft",
                reason=payload.reason,
                document_type=payload.document_type,
                document_number=payload.document_number,
                currency="ARS",
                created_by_user_id=created_by_user_id,
                **totals,
            )
            purchase_return.items.extend(items)
            self.repository.create(purchase_return)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, purchase_return.id)

    def get(self, tenant_id: uuid.UUID, return_id: uuid.UUID) -> PurchaseReturn:
        purchase_return = self.repository.get_by_id(tenant_id, return_id)
        if purchase_return is None:
            raise AppError(
                404, "purchase_return_not_found", "Devolución no encontrada"
            )
        return purchase_return

    def list(
        self,
        tenant_id: uuid.UUID,
        *,
        search: str | None,
        supplier_id: uuid.UUID | None,
        purchase_id: uuid.UUID | None,
        status: str | None,
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
            raise AppError(
                422, "validation_error", "date_from must be before date_to"
            )
        rows, total = self.repository.list(
            tenant_id,
            search=self._normalize_filter(search),
            supplier_id=supplier_id,
            purchase_id=purchase_id,
            status=status,
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
                "id": item.id,
                "purchase_id": item.purchase_id,
                "supplier_id": item.supplier_id,
                "supplier_name": item.supplier_name,
                "return_date": item.return_date,
                "status": item.status,
                "reason": item.reason,
                "document_type": item.document_type,
                "document_number": item.document_number,
                "subtotal_ars": item.subtotal_ars,
                "tax_total_ars": item.tax_total_ars,
                "total_ars": item.total_ars,
                "item_count": item_count,
                "attachment_status": "attached" if has_attachment else "pending",
                "created_by_user_id": item.created_by_user_id,
                "created_by_user_name": item.created_by_user_name,
                "created_by_user_email": item.created_by_user_email,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
            for item, item_count, has_attachment in rows
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
        return_id: uuid.UUID,
        payload: PurchaseReturnUpdate,
    ) -> PurchaseReturn:
        try:
            purchase_return = self._get_for_update(tenant_id, return_id)
            self._require_draft(purchase_return, "editar")
            purchase = self._get_received_purchase(
                tenant_id, purchase_return.purchase_id, for_update=True
            )
            updates = payload.model_dump(exclude_unset=True, exclude={"items"})
            for field_name, value in updates.items():
                setattr(purchase_return, field_name, value)
            if "items" in payload.model_fields_set:
                confirmed = self.repository.confirmed_quantities_by_purchase_item(
                    tenant_id, purchase.id
                )
                items, totals = self._build_items(
                    tenant_id, purchase, payload.items or [], confirmed
                )
                self.repository.replace_items(purchase_return, items)
                for field_name, value in totals.items():
                    setattr(purchase_return, field_name, value)
            purchase_return.updated_at = datetime.now(UTC)
            self.repository.save(purchase_return)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, return_id)

    def cancel(
        self,
        tenant_id: uuid.UUID,
        return_id: uuid.UUID,
        *,
        reason: str,
        cancelled_by_user_id: uuid.UUID | None,
    ) -> PurchaseReturn:
        self._validate_optional_user(tenant_id, cancelled_by_user_id)
        try:
            purchase_return = self._get_for_update(tenant_id, return_id)
            self._require_draft(purchase_return, "cancelar")
            now = datetime.now(UTC)
            purchase_return.status = "cancelled"
            purchase_return.cancelled_at = now
            purchase_return.cancelled_by_user_id = cancelled_by_user_id
            purchase_return.cancellation_reason = reason
            purchase_return.updated_at = now
            self.repository.save(purchase_return)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, return_id)

    def confirm(
        self,
        tenant_id: uuid.UUID,
        return_id: uuid.UUID,
        *,
        confirmed_by_user_id: uuid.UUID | None,
    ) -> PurchaseReturn:
        self._validate_optional_user(tenant_id, confirmed_by_user_id)
        try:
            purchase_return = self._get_for_update(tenant_id, return_id)
            self._require_draft(purchase_return, "confirmar")
            purchase = self._get_received_purchase(
                tenant_id, purchase_return.purchase_id, for_update=True
            )
            confirmed = self.repository.confirmed_quantities_by_purchase_item(
                tenant_id, purchase.id
            )
            purchase_items_by_id = {item.id: item for item in purchase.items}
            self._validate_persisted_items(
                tenant_id,
                purchase_return,
                purchase_items_by_id,
                confirmed,
            )

            return_lines_by_inventory_id = {
                item.inventory_item_id: item for item in purchase_return.items
            }
            locked_inventory_items = (
                self.inventory_repository.list_items_by_ids_for_update(
                    tenant_id, sorted(return_lines_by_inventory_id)
                )
            )
            if len(locked_inventory_items) != len(return_lines_by_inventory_id):
                raise AppError(
                    404, "inventory_item_not_found", "Producto no encontrado"
                )
            for inventory_item in locked_inventory_items:
                line = return_lines_by_inventory_id[inventory_item.id]
                if inventory_item.current_stock < line.quantity:
                    raise AppError(
                        409,
                        "purchase_return_insufficient_stock",
                        "No hay stock suficiente para devolver la cantidad "
                        f"seleccionada de {line.description_snapshot}.",
                    )

            operation_id = uuid.uuid4()
            for inventory_item in locked_inventory_items:
                line = return_lines_by_inventory_id[inventory_item.id]
                self.inventory_service.register_purchase_return_movement(
                    tenant_id,
                    item=inventory_item,
                    purchase_return_id=purchase_return.id,
                    quantity=line.quantity,
                    unit_cost_ars=line.unit_price_without_tax_ars,
                    total_cost_ars=line.line_subtotal_ars,
                    supplier=purchase_return.supplier_name,
                    operation_id=operation_id,
                    created_by_user_id=confirmed_by_user_id,
                )

            now = datetime.now(UTC)
            purchase_return.status = "confirmed"
            purchase_return.inventory_operation_id = operation_id
            purchase_return.confirmed_at = now
            purchase_return.confirmed_by_user_id = confirmed_by_user_id
            purchase_return.updated_at = now
            self.repository.save(purchase_return)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, return_id)

    def _build_items(
        self,
        tenant_id: uuid.UUID,
        purchase: Purchase,
        payload_items,
        confirmed_quantities: dict[uuid.UUID, Decimal],
    ) -> tuple[list[PurchaseReturnItem], dict]:
        if not payload_items:
            raise AppError(
                422,
                "purchase_return_items_required",
                "La devolución requiere al menos una línea",
            )
        purchase_item_ids = [item.purchase_item_id for item in payload_items]
        if len(set(purchase_item_ids)) != len(purchase_item_ids):
            raise AppError(
                422,
                "duplicate_purchase_return_item",
                "No se puede repetir una línea de compra",
            )
        purchase_items_by_id = {item.id: item for item in purchase.items}
        if any(item_id not in purchase_items_by_id for item_id in purchase_item_ids):
            raise AppError(
                404,
                "purchase_item_not_found",
                "La línea de compra no pertenece a la compra indicada",
            )

        items: list[PurchaseReturnItem] = []
        subtotal = ZERO
        tax_total = ZERO
        total = ZERO
        for index, payload_item in enumerate(payload_items, start=1):
            source = purchase_items_by_id[payload_item.purchase_item_id]
            if source.tenant_id != tenant_id or source.purchase_id != purchase.id:
                raise AppError(
                    404,
                    "purchase_item_not_found",
                    "La línea de compra no pertenece a la compra indicada",
                )
            quantity = payload_item.quantity.quantize(
                QUANTITY_QUANTUM, rounding=ROUND_HALF_UP
            )
            returnable = source.quantity - confirmed_quantities.get(source.id, ZERO)
            if quantity > returnable:
                raise AppError(
                    409,
                    "purchase_return_quantity_exceeded",
                    f"La cantidad disponible para devolver de "
                    f"{source.description_snapshot} es {returnable}.",
                )
            line_subtotal = self._money(
                quantity * source.unit_price_without_tax_ars
            )
            line_tax = self._money(
                line_subtotal * source.tax_rate_percentage / HUNDRED
            )
            line_total = self._money(line_subtotal + line_tax)
            items.append(
                PurchaseReturnItem(
                    tenant_id=tenant_id,
                    purchase_item_id=source.id,
                    inventory_item_id=source.inventory_item_id,
                    line_number=index,
                    description_snapshot=source.description_snapshot,
                    internal_code_snapshot=source.internal_code_snapshot,
                    unit=source.unit,
                    quantity=quantity,
                    unit_price_without_tax_ars=source.unit_price_without_tax_ars,
                    tax_rate_percentage=source.tax_rate_percentage,
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

    def _validate_persisted_items(
        self,
        tenant_id: uuid.UUID,
        purchase_return: PurchaseReturn,
        purchase_items_by_id: dict[uuid.UUID, PurchaseItem],
        confirmed_quantities: dict[uuid.UUID, Decimal],
    ) -> None:
        if not purchase_return.items:
            raise AppError(
                409,
                "purchase_return_items_required",
                "La devolución requiere al menos una línea",
            )
        seen_inventory_items: set[uuid.UUID] = set()
        for line in purchase_return.items:
            source = purchase_items_by_id.get(line.purchase_item_id)
            if (
                line.tenant_id != tenant_id
                or source is None
                or source.tenant_id != tenant_id
                or source.purchase_id != purchase_return.purchase_id
                or source.inventory_item_id != line.inventory_item_id
            ):
                raise AppError(
                    409,
                    "purchase_return_items_inconsistent",
                    "Las líneas de la devolución son inconsistentes",
                )
            if line.inventory_item_id in seen_inventory_items:
                raise AppError(
                    409,
                    "purchase_return_items_inconsistent",
                    "Las líneas de la devolución repiten un producto",
                )
            seen_inventory_items.add(line.inventory_item_id)
            returnable = source.quantity - confirmed_quantities.get(source.id, ZERO)
            if line.quantity > returnable:
                raise AppError(
                    409,
                    "purchase_return_quantity_exceeded",
                    f"La cantidad disponible para devolver de "
                    f"{source.description_snapshot} es {returnable}.",
                )

    def _get_for_update(
        self, tenant_id: uuid.UUID, return_id: uuid.UUID
    ) -> PurchaseReturn:
        purchase_return = self.repository.get_by_id(
            tenant_id, return_id, for_update=True
        )
        if purchase_return is None:
            raise AppError(
                404, "purchase_return_not_found", "Devolución no encontrada"
            )
        return purchase_return

    def _get_received_purchase(
        self,
        tenant_id: uuid.UUID,
        purchase_id: uuid.UUID,
        *,
        for_update: bool,
    ) -> Purchase:
        purchase = self.purchase_repository.get_by_id(
            tenant_id, purchase_id, for_update=for_update
        )
        if purchase is None:
            raise AppError(404, "purchase_not_found", "Compra no encontrada")
        if purchase.status != "received":
            raise AppError(
                409,
                "purchase_not_returnable",
                "Sólo una compra recibida puede registrar devoluciones",
            )
        return purchase

    def _require_draft(self, purchase_return: PurchaseReturn, action: str) -> None:
        if purchase_return.status != "draft":
            raise AppError(
                409,
                "purchase_return_not_editable",
                f"Sólo se puede {action} una devolución en borrador",
            )

    def _validate_optional_user(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID | None
    ) -> None:
        if (
            user_id is not None
            and self.user_repository.get_by_id(tenant_id, user_id) is None
        ):
            raise AppError(404, "user_not_found", "Usuario no encontrado")

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)

    @staticmethod
    def _normalize_filter(value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

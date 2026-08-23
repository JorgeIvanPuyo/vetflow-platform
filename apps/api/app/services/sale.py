from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from math import ceil

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.owner import Owner
from app.models.patient import Patient
from app.models.sale import Sale, SaleItem
from app.repositories.inventory import InventoryRepository
from app.repositories.owner import OwnerRepository
from app.repositories.patient import PatientRepository
from app.repositories.sale import SaleRepository
from app.repositories.user import UserRepository
from app.schemas.sale import SaleCreate, SaleProductItemInput, SaleUpdate
from app.services.inventory import InventoryService


MONEY_QUANTUM = Decimal("0.01")
HUNDRED = Decimal("100")


class SaleService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = SaleRepository(db)
        self.owner_repository = OwnerRepository(db)
        self.patient_repository = PatientRepository(db)
        self.user_repository = UserRepository(db)
        self.inventory_repository = InventoryRepository(db)
        self.inventory_service = InventoryService(db)

    def create(self, tenant_id: uuid.UUID, payload: SaleCreate, *, created_by_user_id: uuid.UUID | None) -> Sale:
        self._validate_user(tenant_id, created_by_user_id)
        try:
            owner, patient = self._resolve_parties(tenant_id, payload.owner_id, payload.patient_id)
            items, totals = self._build_items(tenant_id, payload.items)
            sale = Sale(
                tenant_id=tenant_id,
                owner_id=owner.id if owner else None,
                patient_id=patient.id if patient else None,
                owner_name_snapshot=owner.full_name if owner else None,
                owner_document_snapshot=owner.document_id if owner else None,
                owner_email_snapshot=owner.email if owner else None,
                patient_name_snapshot=patient.name if patient else None,
                patient_species_snapshot=patient.species if patient else None,
                sale_date=payload.sale_date,
                currency="ARS",
                notes=payload.notes,
                status="draft",
                created_by_user_id=created_by_user_id,
                **totals,
            )
            sale.items.extend(items)
            self.repository.create(sale)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, sale.id)

    def get(self, tenant_id: uuid.UUID, sale_id: uuid.UUID) -> Sale:
        sale = self.repository.get_by_id(tenant_id, sale_id)
        if sale is None:
            raise AppError(404, "sale_not_found", "Venta no encontrada")
        return sale

    def update(self, tenant_id: uuid.UUID, sale_id: uuid.UUID, payload: SaleUpdate) -> Sale:
        try:
            sale = self.repository.get_by_id(tenant_id, sale_id, for_update=True)
            if sale is None:
                raise AppError(404, "sale_not_found", "Venta no encontrada")
            self._require_draft(sale, "editar")
            fields = payload.model_fields_set
            if "owner_id" in fields or "patient_id" in fields:
                owner_id = payload.owner_id if "owner_id" in fields else sale.owner_id
                patient_id = payload.patient_id if "patient_id" in fields else (None if "owner_id" in fields else sale.patient_id)
                owner, patient = self._resolve_parties(tenant_id, owner_id, patient_id)
                sale.owner_id = owner.id if owner else None
                sale.patient_id = patient.id if patient else None
                sale.owner_name_snapshot = owner.full_name if owner else None
                sale.owner_document_snapshot = owner.document_id if owner else None
                sale.owner_email_snapshot = owner.email if owner else None
                sale.patient_name_snapshot = patient.name if patient else None
                sale.patient_species_snapshot = patient.species if patient else None
            if "sale_date" in fields:
                sale.sale_date = payload.sale_date
            if "notes" in fields:
                sale.notes = payload.notes
            if "items" in fields:
                items, totals = self._build_items(tenant_id, payload.items or [])
                self.repository.replace_items(sale, items)
                for name, value in totals.items():
                    setattr(sale, name, value)
            sale.updated_at = datetime.now(UTC)
            self.repository.save(sale)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, sale_id)

    def cancel(self, tenant_id: uuid.UUID, sale_id: uuid.UUID, *, reason: str, cancelled_by_user_id: uuid.UUID | None) -> Sale:
        self._validate_user(tenant_id, cancelled_by_user_id)
        try:
            sale = self.repository.get_by_id(tenant_id, sale_id, for_update=True)
            if sale is None:
                raise AppError(404, "sale_not_found", "Venta no encontrada")
            self._require_draft(sale, "cancelar")
            now = datetime.now(UTC)
            sale.status = "cancelled"
            sale.cancelled_at = now
            sale.cancelled_by_user_id = cancelled_by_user_id
            sale.cancellation_reason = reason
            sale.updated_at = now
            self.repository.save(sale)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, sale_id)

    def confirm(
        self,
        tenant_id: uuid.UUID,
        sale_id: uuid.UUID,
        *,
        confirmed_by_user_id: uuid.UUID | None,
    ) -> Sale:
        self._validate_user(tenant_id, confirmed_by_user_id)
        try:
            sale = self.repository.get_by_id(tenant_id, sale_id, for_update=True)
            if sale is None:
                raise AppError(404, "sale_not_found", "Venta no encontrada")
            self._require_draft(sale, "confirmar")

            product_lines = self._validated_product_lines(tenant_id, sale)
            lines_by_item_id = {
                line.inventory_item_id: line for line in product_lines
            }
            locked_items = self.inventory_repository.list_items_by_ids_for_update(
                tenant_id, sorted(lines_by_item_id)
            )
            if len(locked_items) != len(lines_by_item_id):
                raise AppError(404, "inventory_item_not_found", "Producto no encontrado")

            for item in locked_items:
                line = lines_by_item_id[item.id]
                if item.current_stock < line.quantity:
                    raise AppError(
                        409,
                        "sale_insufficient_stock",
                        f"Stock insuficiente para {line.description_snapshot}. "
                        f"Disponible: {item.current_stock}. Solicitado: {line.quantity}.",
                    )

            operation_id = uuid.uuid4() if product_lines else None
            for item in locked_items:
                line = lines_by_item_id[item.id]
                self.inventory_service.register_sale_movement(
                    tenant_id,
                    item=item,
                    sale_id=sale.id,
                    operation_id=operation_id,
                    quantity=line.quantity,
                    unit_sale_price_ars=line.unit_price_ars,
                    total_sale_price_ars=line.line_total_ars,
                    created_by_user_id=confirmed_by_user_id,
                )

            now = datetime.now(UTC)
            sale.status = "confirmed"
            sale.confirmed_at = now
            sale.confirmed_by_user_id = confirmed_by_user_id
            sale.inventory_operation_id = operation_id
            sale.updated_at = now
            self.repository.save(sale)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, sale_id)

    def reverse(
        self,
        tenant_id: uuid.UUID,
        sale_id: uuid.UUID,
        *,
        reason: str,
        reversed_by_user_id: uuid.UUID | None,
    ) -> Sale:
        self._validate_user(tenant_id, reversed_by_user_id)
        try:
            sale = self.repository.get_by_id(tenant_id, sale_id, for_update=True)
            if sale is None:
                raise AppError(404, "sale_not_found", "Venta no encontrada")
            if sale.status != "confirmed":
                raise AppError(
                    409,
                    "sale_not_reversible",
                    "Sólo se puede revertir una venta confirmada",
                )

            product_lines = self._validated_product_lines(tenant_id, sale)
            lines_by_item_id = {
                line.inventory_item_id: line for line in product_lines
            }
            originals = []
            if product_lines:
                if sale.inventory_operation_id is None:
                    raise AppError(
                        409,
                        "sale_movements_inconsistent",
                        "La venta no tiene una operación de inventario válida",
                    )
                originals = self.inventory_repository.list_sale_movements_for_update(
                    tenant_id,
                    sale_id=sale.id,
                    operation_id=sale.inventory_operation_id,
                )

            originals_by_item_id = {
                movement.inventory_item_id: movement for movement in originals
            }
            if (
                len(originals) != len(product_lines)
                or set(originals_by_item_id) != set(lines_by_item_id)
                or any(
                    originals_by_item_id[item_id].quantity != line.quantity
                    for item_id, line in lines_by_item_id.items()
                )
            ):
                raise AppError(
                    409,
                    "sale_movements_inconsistent",
                    "Los movimientos de la venta están incompletos o son inconsistentes",
                )
            if self.inventory_repository.list_reversals_for_movements(
                tenant_id, [movement.id for movement in originals]
            ):
                raise AppError(
                    409,
                    "sale_already_reversed",
                    "La venta ya contiene movimientos revertidos",
                )

            locked_items = self.inventory_repository.list_items_by_ids_for_update(
                tenant_id, sorted(lines_by_item_id)
            )
            if len(locked_items) != len(lines_by_item_id):
                raise AppError(404, "inventory_item_not_found", "Producto no encontrado")

            reversal_operation_id = uuid.uuid4() if originals else None
            for item in locked_items:
                self.inventory_service.register_sale_reversal_movement(
                    tenant_id,
                    item=item,
                    sale_id=sale.id,
                    original=originals_by_item_id[item.id],
                    operation_id=reversal_operation_id,
                    reason=reason,
                    created_by_user_id=reversed_by_user_id,
                )

            now = datetime.now(UTC)
            sale.status = "reversed"
            sale.reversed_at = now
            sale.reversed_by_user_id = reversed_by_user_id
            sale.reversal_reason = reason
            sale.reversal_operation_id = reversal_operation_id
            sale.updated_at = now
            self.repository.save(sale)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, sale_id)

    def list(self, tenant_id: uuid.UUID, **filters) -> tuple[list[dict], dict]:
        if filters["date_from"] and filters["date_to"] and filters["date_from"] > filters["date_to"]:
            raise AppError(422, "validation_error", "date_from must be before date_to")
        rows, total = self.repository.list(tenant_id, **filters)
        data = [
            {
                "id": sale.id, "owner_id": sale.owner_id, "patient_id": sale.patient_id,
                "owner_name_snapshot": sale.owner_name_snapshot, "patient_name_snapshot": sale.patient_name_snapshot,
                "sale_date": sale.sale_date, "currency": sale.currency, "subtotal_ars": sale.subtotal_ars,
                "discount_total_ars": sale.discount_total_ars, "total_ars": sale.total_ars,
                "status": sale.status, "fiscal_status": sale.fiscal_status,
                "item_count": item_count,
                "created_by_user_id": sale.created_by_user_id, "created_by_user_name": sale.created_by_user_name,
                "created_by_user_email": sale.created_by_user_email, "created_at": sale.created_at, "updated_at": sale.updated_at,
                "paid_total_ars": paid_total,
                "balance_due_ars": sale.total_ars - paid_total,
                "payment_status": (
                    "requires_attention" if sale.status == "reversed" and paid_total > 0
                    else "unpaid" if sale.status == "confirmed" and paid_total == 0
                    else "paid" if sale.status == "confirmed" and paid_total == sale.total_ars
                    else "partial" if sale.status == "confirmed" else None
                ),
                "payment_requires_attention": sale.status == "reversed" and paid_total > 0,
            }
            for sale, item_count, paid_total in rows
        ]
        page, page_size = filters["page"], filters["page_size"]
        return data, {"page": page, "page_size": page_size, "total": total, "total_pages": ceil(total / page_size) if total else 0}

    def list_creators(self, tenant_id: uuid.UUID):
        return self.user_repository.list_active_by_tenant(tenant_id)

    def _resolve_parties(self, tenant_id: uuid.UUID, owner_id: uuid.UUID | None, patient_id: uuid.UUID | None) -> tuple[Owner | None, Patient | None]:
        if patient_id is not None and owner_id is None:
            raise AppError(422, "sale_patient_requires_owner", "Selecciona el propietario antes del paciente")
        owner = self.owner_repository.get_by_id(tenant_id, owner_id) if owner_id else None
        if owner_id and owner is None:
            raise AppError(404, "owner_not_found", "Propietario no encontrado")
        patient = self.patient_repository.get_by_id(tenant_id, patient_id) if patient_id else None
        if patient_id and patient is None:
            raise AppError(404, "patient_not_found", "Paciente no encontrado")
        if patient is not None and patient.owner_id != owner.id:
            raise AppError(422, "sale_patient_owner_mismatch", "El paciente no pertenece al propietario seleccionado")
        return owner, patient

    def _build_items(self, tenant_id: uuid.UUID, inputs) -> tuple[list[SaleItem], dict]:
        product_ids = [item.inventory_item_id for item in inputs if isinstance(item, SaleProductItemInput)]
        if len(product_ids) != len(set(product_ids)):
            raise AppError(422, "duplicate_sale_product", "Un producto no puede repetirse en la venta")
        products = {item.id: item for item in self.repository.list_inventory_items(tenant_id, product_ids)}
        if len(products) != len(product_ids):
            raise AppError(404, "inventory_item_not_found", "Producto no encontrado")
        items: list[SaleItem] = []
        subtotal = discount_total = total = Decimal("0")
        for order, item_input in enumerate(inputs, start=1):
            if isinstance(item_input, SaleProductItemInput):
                product = products[item_input.inventory_item_id]
                if not product.is_active:
                    raise AppError(409, "inventory_item_inactive", f"{product.name} no está activo para venta")
                price = item_input.unit_price_ars if item_input.unit_price_ars is not None else product.sale_price_ars
                if price is None:
                    raise AppError(409, "sale_price_missing", f"{product.name} no tiene precio de venta")
                description, code, unit, inventory_id = product.name, product.internal_code, product.unit, product.id
            else:
                price = item_input.unit_price_ars
                description, code, unit, inventory_id = item_input.description, None, "service", None
            line_subtotal = (item_input.quantity * price).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
            line_discount = (line_subtotal * item_input.discount_percentage / HUNDRED).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
            line_total = (line_subtotal - line_discount).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
            items.append(SaleItem(
                tenant_id=tenant_id, line_type=item_input.line_type, inventory_item_id=inventory_id, service_id=None,
                description_snapshot=description, internal_code_snapshot=code, unit_snapshot=unit,
                quantity=item_input.quantity, unit_price_ars=price, discount_percentage=item_input.discount_percentage,
                line_subtotal_ars=line_subtotal, line_discount_ars=line_discount, line_total_ars=line_total, line_order=order,
            ))
            subtotal += line_subtotal
            discount_total += line_discount
            total += line_total
        return items, {
            "subtotal_ars": subtotal.quantize(MONEY_QUANTUM),
            "discount_total_ars": discount_total.quantize(MONEY_QUANTUM),
            "total_ars": total.quantize(MONEY_QUANTUM),
        }

    def _validate_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID | None) -> None:
        if user_id is not None and self.user_repository.get_by_id(tenant_id, user_id) is None:
            raise AppError(404, "user_not_found", "Usuario no encontrado")

    @staticmethod
    def _validated_product_lines(
        tenant_id: uuid.UUID, sale: Sale
    ) -> list[SaleItem]:
        if not sale.items:
            raise AppError(
                409,
                "sale_items_required",
                "La venta requiere al menos una línea",
            )
        product_lines: list[SaleItem] = []
        seen_item_ids: set[uuid.UUID] = set()
        for line in sale.items:
            if line.tenant_id != tenant_id or line.sale_id != sale.id:
                raise AppError(
                    409,
                    "sale_items_inconsistent",
                    "Las líneas de la venta son inconsistentes",
                )
            if line.quantity <= 0 or line.quantity != line.quantity.to_integral_value():
                raise AppError(
                    409,
                    "sale_quantity_must_be_integer",
                    "Todas las cantidades deben ser números enteros mayores que cero",
                )
            if line.line_type == "service":
                if line.inventory_item_id is not None:
                    raise AppError(
                        409,
                        "sale_items_inconsistent",
                        "Las líneas de la venta son inconsistentes",
                    )
                continue
            if line.line_type != "product" or line.inventory_item_id is None:
                raise AppError(
                    409,
                    "sale_items_inconsistent",
                    "Las líneas de la venta son inconsistentes",
                )
            if line.inventory_item_id in seen_item_ids:
                raise AppError(
                    409,
                    "sale_items_inconsistent",
                    "Las líneas de la venta repiten un producto",
                )
            seen_item_ids.add(line.inventory_item_id)
            product_lines.append(line)
        return product_lines

    @staticmethod
    def _require_draft(sale: Sale, action: str) -> None:
        if sale.status != "draft":
            raise AppError(409, "sale_not_editable", f"Sólo se puede {action} una venta en borrador")

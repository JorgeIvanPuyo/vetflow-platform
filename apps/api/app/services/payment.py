from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from math import ceil

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.payment import PaymentMethod, SalePayment
from app.repositories.payment import PaymentMethodRepository, SalePaymentRepository
from app.repositories.sale import SaleRepository
from app.repositories.user import UserRepository
from app.schemas.payment import PaymentMethodCreate, PaymentMethodUpdate, SalePaymentCreate


def normalized_label(value: str) -> str:
    return " ".join(value.split()).casefold()


class PaymentMethodService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = PaymentMethodRepository(db)
        self.user_repository = UserRepository(db)

    def create(self, tenant_id: uuid.UUID, payload: PaymentMethodCreate, *, user_id: uuid.UUID | None) -> PaymentMethod:
        self._validate_user(tenant_id, user_id)
        normalized = normalized_label(payload.label)
        if payload.is_active and self.repository.find_active_label(tenant_id, normalized):
            raise AppError(409, "payment_method_label_duplicate", "Ya existe una forma de pago activa con ese nombre")
        method = PaymentMethod(tenant_id=tenant_id, normalized_label=normalized, created_by_user_id=user_id, updated_by_user_id=user_id, **payload.model_dump())
        try:
            self.repository.create(method)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(409, "payment_method_label_duplicate", "Ya existe una forma de pago activa con ese nombre") from exc
        return self.get(tenant_id, method.id)

    def get(self, tenant_id: uuid.UUID, method_id: uuid.UUID) -> PaymentMethod:
        method = self.repository.get_by_id(tenant_id, method_id)
        if method is None:
            raise AppError(404, "payment_method_not_found", "Forma de pago no encontrada")
        method.has_payments = self.repository.has_payments(tenant_id, method.id)
        return method

    def list(self, tenant_id: uuid.UUID, **filters):
        rows, total = self.repository.list(tenant_id, **filters)
        data = []
        for method, has_payments in rows:
            method.has_payments = has_payments
            data.append(method)
        return data, {"page": filters["page"], "page_size": filters["page_size"], "total": total, "total_pages": ceil(total / filters["page_size"]) if total else 0}

    def update(self, tenant_id: uuid.UUID, method_id: uuid.UUID, payload: PaymentMethodUpdate, *, user_id: uuid.UUID | None) -> PaymentMethod:
        self._validate_user(tenant_id, user_id)
        try:
            method = self.repository.get_by_id(tenant_id, method_id, for_update=True)
            if method is None:
                raise AppError(404, "payment_method_not_found", "Forma de pago no encontrada")
            changes = payload.model_dump(exclude_unset=True)
            if any(value is None for value in changes.values()):
                raise AppError(422, "validation_error", "Los campos enviados no pueden ser null")
            if "type" in changes and changes["type"] != method.type and self.repository.has_payments(tenant_id, method.id):
                raise AppError(409, "payment_method_type_locked", "El tipo no puede cambiar porque la forma de pago ya tiene cobros históricos")
            candidate_label = changes.get("label", method.label)
            candidate_active = changes.get("is_active", method.is_active)
            normalized = normalized_label(candidate_label)
            if candidate_active and self.repository.find_active_label(tenant_id, normalized, exclude_id=method.id):
                raise AppError(409, "payment_method_label_duplicate", "Ya existe una forma de pago activa con ese nombre")
            for field, value in changes.items():
                setattr(method, field, value)
            method.normalized_label = normalized
            method.updated_by_user_id = user_id
            method.updated_at = datetime.now(UTC)
            self.repository.save(method)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(409, "payment_method_label_duplicate", "Ya existe una forma de pago activa con ese nombre") from exc
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, method_id)

    def _validate_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID | None) -> None:
        if user_id is not None and self.user_repository.get_by_id(tenant_id, user_id) is None:
            raise AppError(404, "user_not_found", "Usuario no encontrado")


class SalePaymentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = SalePaymentRepository(db)
        self.method_repository = PaymentMethodRepository(db)
        self.sale_repository = SaleRepository(db)
        self.user_repository = UserRepository(db)

    def create(self, tenant_id: uuid.UUID, sale_id: uuid.UUID, payload: SalePaymentCreate, *, user_id: uuid.UUID | None) -> SalePayment:
        self._validate_user(tenant_id, user_id)
        try:
            sale = self.sale_repository.get_by_id(tenant_id, sale_id, for_update=True)
            if sale is None:
                raise AppError(404, "sale_not_found", "Venta no encontrada")
            if sale.status != "confirmed":
                raise AppError(409, "sale_payment_not_allowed", "Sólo se pueden registrar cobros en ventas confirmadas")
            method = self.method_repository.get_by_id(tenant_id, payload.payment_method_id)
            if method is None:
                raise AppError(404, "payment_method_not_found", "Forma de pago no encontrada")
            if not method.is_active:
                raise AppError(409, "payment_method_inactive", "La forma de pago está inactiva")
            paid_total = self.repository.active_total(tenant_id, sale.id)
            balance = sale.total_ars - paid_total
            if payload.amount_ars > balance:
                raise AppError(409, "sale_payment_exceeds_balance", f"El cobro supera el saldo pendiente de ARS {balance:.2f}")
            payment = SalePayment(
                tenant_id=tenant_id, sale_id=sale.id, payment_method_id=method.id,
                payment_method_label_snapshot=method.label, payment_method_type_snapshot=method.type,
                amount_ars=payload.amount_ars, received_at=payload.received_at,
                reference=payload.reference, notes=payload.notes, created_by_user_id=user_id, is_active=True,
            )
            self.repository.create(payment)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, payment.id)

    def get(self, tenant_id: uuid.UUID, payment_id: uuid.UUID) -> SalePayment:
        payment = self.repository.get_by_id(tenant_id, payment_id)
        if payment is None:
            raise AppError(404, "sale_payment_not_found", "Cobro no encontrado")
        return payment

    def list(self, tenant_id: uuid.UUID, sale_id: uuid.UUID) -> tuple[list[SalePayment], dict]:
        sale = self.sale_repository.get_by_id(tenant_id, sale_id)
        if sale is None:
            raise AppError(404, "sale_not_found", "Venta no encontrada")
        payments = self.repository.list_for_sale(tenant_id, sale_id)
        paid = sum((payment.amount_ars for payment in payments if payment.is_active), Decimal("0.00")).quantize(Decimal("0.01"))
        return payments, self._summary(sale.status, sale.total_ars, paid)

    def void(self, tenant_id: uuid.UUID, payment_id: uuid.UUID, *, reason: str, user_id: uuid.UUID | None) -> SalePayment:
        self._validate_user(tenant_id, user_id)
        try:
            candidate = self.repository.get_by_id(tenant_id, payment_id)
            if candidate is None:
                raise AppError(404, "sale_payment_not_found", "Cobro no encontrado")
            sale = self.sale_repository.get_by_id(tenant_id, candidate.sale_id, for_update=True)
            if sale is None:
                raise AppError(404, "sale_not_found", "Venta no encontrada")
            payment = self.repository.get_by_id(tenant_id, payment_id, for_update=True)
            if payment is None or payment.sale_id != sale.id:
                raise AppError(404, "sale_payment_not_found", "Cobro no encontrado")
            if not payment.is_active:
                raise AppError(409, "sale_payment_already_voided", "El cobro ya está anulado")
            now = datetime.now(UTC)
            payment.is_active = False
            payment.voided_at = now
            payment.voided_by_user_id = user_id
            payment.void_reason = reason
            payment.updated_at = now
            self.repository.save(payment)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, payment_id)

    @staticmethod
    def _summary(status: str, total: Decimal, paid: Decimal) -> dict:
        attention = status == "reversed" and paid > 0
        payment_status = "requires_attention" if attention else ("unpaid" if paid == 0 else "paid" if paid == total else "partial") if status == "confirmed" else None
        return {"paid_total_ars": paid, "balance_due_ars": total - paid, "payment_status": payment_status, "payment_requires_attention": attention}

    def _validate_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID | None) -> None:
        if user_id is not None and self.user_repository.get_by_id(tenant_id, user_id) is None:
            raise AppError(404, "user_not_found", "Usuario no encontrado")

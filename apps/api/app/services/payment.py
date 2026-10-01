from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from math import ceil

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.payment import PaymentMethod, SalePayment
from app.models.sale import calculate_payment_status
from app.repositories.payment import PaymentMethodRepository, SalePaymentRepository
from app.repositories.sale import SaleRepository
from app.repositories.user import UserRepository
from app.schemas.payment import IdempotencyKey, PaymentMethodCreate, PaymentMethodUpdate, SalePaymentCreate


def normalized_label(value: str) -> str:
    return " ".join(value.split()).casefold()


def payment_request_hash(sale_id: uuid.UUID, payload: SalePaymentCreate) -> str:
    received_at = payload.received_at
    if received_at.tzinfo is not None:
        received_at = received_at.astimezone(UTC)
    # received_at is required, so no server-generated default enters this hash.
    # Optional omitted/null text has the same meaning after schema normalization.
    canonical = {
        "version": 1,
        "sale_id": str(sale_id),
        "payment_method_id": str(payload.payment_method_id),
        "amount_ars": format(payload.amount_ars, ".2f"),
        "received_at": received_at.isoformat(timespec="microseconds"),
        "reference": payload.reference,
        "notes": payload.notes,
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
        self.idempotency_replayed = False

    def create(self, tenant_id: uuid.UUID, sale_id: uuid.UUID, payload: SalePaymentCreate, *, user_id: uuid.UUID | None, idempotency_key: str | None = None) -> SalePayment:
        self.idempotency_replayed = False
        self._validate_user(tenant_id, user_id)
        if idempotency_key is not None:
            try:
                idempotency_key = TypeAdapter(IdempotencyKey).validate_python(idempotency_key)
            except ValidationError as exc:
                raise AppError(422, "validation_error", "Clave de idempotencia inválida") from exc
        request_hash = payment_request_hash(sale_id, payload) if idempotency_key is not None else None
        try:
            if idempotency_key is not None:
                existing = self.repository.get_by_idempotency_key(tenant_id, idempotency_key)
                if existing is not None:
                    return self._replay(existing, request_hash)
            sale = self.sale_repository.get_by_id(tenant_id, sale_id, for_update=True)
            if sale is None:
                raise AppError(404, "sale_not_found", "Venta no encontrada")
            # A request for this sale may have committed while we waited for its lock.
            if idempotency_key is not None:
                existing = self.repository.get_by_idempotency_key(tenant_id, idempotency_key)
                if existing is not None:
                    return self._replay(existing, request_hash)
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
                raise AppError(409, "sale_payment_exceeds_balance", f"El cobro supera el saldo pendiente de {sale.currency} {balance:.2f}")
            payment = SalePayment(
                tenant_id=tenant_id, sale_id=sale.id, payment_method_id=method.id,
                payment_method_label_snapshot=method.label, payment_method_type_snapshot=method.type,
                amount_ars=payload.amount_ars, received_at=payload.received_at,
                reference=payload.reference, notes=payload.notes, created_by_user_id=user_id, is_active=True,
                idempotency_key=idempotency_key, idempotency_request_hash=request_hash,
            )
            self.repository.create(payment)
            self.db.commit()
        except IntegrityError:
            # The same tenant/key can race on different sale locks. The unique
            # index chooses the winner; release our lock before looking it up.
            self.db.rollback()
            if idempotency_key is not None:
                existing = self.repository.get_by_idempotency_key(tenant_id, idempotency_key)
                if existing is not None:
                    return self._replay(existing, request_hash)
            raise
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, payment.id)

    def _replay(self, payment: SalePayment, request_hash: str) -> SalePayment:
        if payment.idempotency_request_hash != request_hash:
            raise AppError(409, "sale_payment_idempotency_conflict", "La solicitud de cobro ya se utilizó con datos diferentes")
        self.idempotency_replayed = True
        return payment

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
        payment_status = calculate_payment_status(status, total, paid)
        return {"paid_total_ars": paid, "balance_due_ars": total - paid, "payment_status": payment_status, "payment_requires_attention": attention}

    def _validate_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID | None) -> None:
        if user_id is not None and self.user_repository.get_by_id(tenant_id, user_id) is None:
            raise AppError(404, "user_not_found", "Usuario no encontrado")

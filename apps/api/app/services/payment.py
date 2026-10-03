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
from app.models.payment import PaymentMethod, SalePayment, SalePaymentBatch
from app.models.sale import Sale, calculate_balance_due, calculate_payment_status
from app.repositories.payment import PaymentMethodRepository, SalePaymentRepository
from app.repositories.sale import SaleRepository
from app.repositories.user import UserRepository
from app.schemas.payment import IdempotencyKey, PaymentMethodCreate, PaymentMethodUpdate, SalePaymentCreate


def normalized_label(value: str) -> str:
    return " ".join(value.split()).casefold()


def payment_request_hash(sale_id: uuid.UUID, payload: SalePaymentCreate) -> str:
    received_at = payload.received_at
    if received_at is not None and received_at.tzinfo is not None:
        received_at = received_at.astimezone(UTC)
    # Checkout's omitted date is a stable intent; the generated effective date
    # must never enter the hash. Individual payments still require received_at.
    # Optional omitted/null text has the same meaning after schema normalization.
    canonical = {
        "version": 1,
        "sale_id": str(sale_id),
        "payment_method_id": str(payload.payment_method_id),
        "amount_ars": format(payload.amount_ars, ".2f"),
        "received_at": received_at.isoformat(timespec="microseconds") if received_at is not None else None,
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
        """Standalone operation: commit success (including replay), roll back errors."""
        try:
            payment = self.create_in_transaction(
                tenant_id, sale_id, payload, user_id=user_id, idempotency_key=idempotency_key,
            )
            payment_id = payment.id
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, payment_id)

    def create_in_transaction(self, tenant_id: uuid.UUID, sale_id: uuid.UUID, payload: SalePaymentCreate, *, user_id: uuid.UUID | None, idempotency_key: str | None = None) -> SalePayment:
        """Flush a payment without completing the caller's transaction.

        Lock order is unchanged: Sale only; PaymentMethod is a scoped read.
        The caller owns commit/rollback and must roll back on unexpected errors.
        Only the idempotent insert is recoverable through a local savepoint.
        """
        self.idempotency_replayed = False
        self._validate_user(tenant_id, user_id)
        idempotency_key = self._normalize_idempotency_key(idempotency_key)
        request_hash = payment_request_hash(sale_id, payload) if idempotency_key is not None else None
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
        payment = self._build_payment(tenant_id, sale, payload, user_id=user_id)
        payment.idempotency_key = idempotency_key
        payment.idempotency_request_hash = request_hash
        if idempotency_key is None:
            self.repository.create(payment)
        else:
            # sqlite3 legacy mode does not BEGIN for SELECT/SAVEPOINT. Ensure
            # RELEASE cannot commit the payment independently of the caller.
            connection = self.db.connection()
            if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
                connection.exec_driver_sql("BEGIN")
            # begin_nested flushes ALL pending outer changes unconditionally.
            # Keep that flush outside the insert recovery handler: a failure
            # there belongs to the outer transaction and must propagate.
            savepoint = self.db.begin_nested()
            try:
                with savepoint:
                    self.repository.create(payment)
            except IntegrityError as exc:
                if not self._is_idempotency_collision(exc):
                    raise
                # PostgreSQL READ COMMITTED can now see the winning insert.
                # Sale/inventory locks acquired before the savepoint stay held.
                existing = self.repository.get_by_idempotency_key(tenant_id, idempotency_key)
                if existing is None:
                    raise
                return self._replay(existing, request_hash)
        # A composing caller may already hold this Sale with payments loaded.
        self.db.expire(sale, ["payments"])
        return self.get(tenant_id, payment.id)

    def create_for_locked_sale_in_transaction(
        self, tenant_id: uuid.UUID, sale: Sale, payload: SalePaymentCreate,
        *, user_id: uuid.UUID | None, batch: SalePaymentBatch,
    ) -> SalePayment:
        """Flush a batch member under the coordinator's existing Sale lock.

        The caller must reserve the batch and hold Sale FOR UPDATE in this
        Session, and owns the only commit/rollback. Individual idempotency is
        intentionally unused: the batch's persisted identity covers all rows.
        """
        if sale.tenant_id != tenant_id or batch.tenant_id != tenant_id or batch.sale_id != sale.id:
            raise AppError(404, "sale_not_found", "Venta no encontrada")
        self._validate_user(tenant_id, user_id)
        payment = self._build_payment(tenant_id, sale, payload, user_id=user_id)
        payment.batch_id = batch.id
        self.repository.create(payment)
        self.db.expire(sale, ["payments"])
        return self.get(tenant_id, payment.id)

    def _build_payment(
        self, tenant_id: uuid.UUID, sale: Sale, payload: SalePaymentCreate,
        *, user_id: uuid.UUID | None,
    ) -> SalePayment:
        """Shared state, method, balance, timestamp and snapshot rules."""
        if sale.status != "confirmed":
            raise AppError(409, "sale_payment_not_allowed", "Sólo se pueden registrar cobros en ventas confirmadas")
        method = self.method_repository.get_by_id(tenant_id, payload.payment_method_id)
        if method is None:
            raise AppError(404, "payment_method_not_found", "Forma de pago no encontrada")
        if not method.is_active:
            raise AppError(409, "payment_method_inactive", "La forma de pago está inactiva")
        paid_total = self.repository.active_total(tenant_id, sale.id)
        balance = calculate_balance_due(sale.total_ars, paid_total)
        if payload.amount_ars > balance:
            raise AppError(409, "sale_payment_exceeds_balance", f"El cobro supera el saldo pendiente de {sale.currency} {balance:.2f}")
        payment = SalePayment(
            tenant_id=tenant_id, sale_id=sale.id, payment_method_id=method.id,
            payment_method_label_snapshot=method.label, payment_method_type_snapshot=method.type,
            amount_ars=payload.amount_ars, received_at=payload.received_at if payload.received_at is not None else datetime.now(UTC),
            reference=payload.reference, notes=payload.notes, created_by_user_id=user_id, is_active=True,
        )
        return payment

    def find_replay_in_transaction(self, tenant_id: uuid.UUID, sale_id: uuid.UUID, payload: SalePaymentCreate, *, user_id: uuid.UUID | None, idempotency_key: str) -> SalePayment | None:
        """Check persisted intent before a coordinator requires a draft sale.

        No commit/rollback or payment/business mutation. A coordinator must
        check again after acquiring the Sale lock to handle concurrent retries.
        """
        self.idempotency_replayed = False
        self._validate_user(tenant_id, user_id)
        key = self._normalize_idempotency_key(idempotency_key)
        existing = self.repository.get_by_idempotency_key(tenant_id, key)
        if existing is None:
            return None
        return self._replay(existing, payment_request_hash(sale_id, payload))

    @staticmethod
    def _normalize_idempotency_key(key: str | None) -> str | None:
        if key is None:
            return None
        try:
            return TypeAdapter(IdempotencyKey).validate_python(key)
        except ValidationError as exc:
            raise AppError(422, "validation_error", "Clave de idempotencia inválida") from exc

    @staticmethod
    def _is_idempotency_collision(exc: IntegrityError) -> bool:
        original = exc.orig
        diagnostic = getattr(original, "diag", None)
        if getattr(original, "pgcode", None) == "23505":
            return getattr(diagnostic, "constraint_name", None) == "uq_sale_payments_tenant_idempotency_key"
        return (
            getattr(original, "sqlite_errorname", None) == "SQLITE_CONSTRAINT_UNIQUE"
            and str(original) == "UNIQUE constraint failed: sale_payments.tenant_id, sale_payments.idempotency_key"
        )

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
        return {"paid_total_ars": paid, "balance_due_ars": calculate_balance_due(total, paid), "payment_status": payment_status, "payment_requires_attention": attention}

    def _validate_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID | None) -> None:
        if user_id is not None and self.user_repository.get_by_id(tenant_id, user_id) is None:
            raise AppError(404, "user_not_found", "Usuario no encontrado")

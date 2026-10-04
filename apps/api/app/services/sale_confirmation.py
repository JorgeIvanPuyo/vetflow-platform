from __future__ import annotations

import hashlib
import json
import uuid
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.payment import SalePaymentBatch
from app.models.sale import Sale
from app.repositories.payment import SalePaymentBatchRepository
from app.schemas.payment import SaleInitialPaymentCreate
from app.schemas.sale import SaleConfirm
from app.services.payment import SalePaymentService, payment_request_hash
from app.services.sale import SaleService


def batch_request_hash(sale_id: uuid.UUID, payments: list[SaleInitialPaymentCreate]) -> str:
    """Hash the ordered normalized intents, including stable omitted dates."""
    canonical = {"version": 1, "sale_id": str(sale_id), "payments": [
        payment_request_hash(sale_id, payment) for payment in payments
    ]}
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class SaleConfirmationService:
    """Own one outer transaction for confirmation and initial payments."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.sales = SaleService(db)
        self.payments = SalePaymentService(db)
        self.batches = SalePaymentBatchRepository(db)
        self.idempotency_replayed = False

    def confirm(
        self,
        tenant_id: uuid.UUID,
        sale_id: uuid.UUID,
        payload: SaleConfirm,
        *,
        user_id: uuid.UUID | None,
        idempotency_key: str | None = None,
    ) -> Sale:
        self.idempotency_replayed = False
        try:
            initial_payment = payload.initial_payment
            if payload.initial_payments is not None:
                self._confirm_batch(tenant_id, sale_id, payload.initial_payments, user_id=user_id, idempotency_key=idempotency_key)
            elif initial_payment is not None:
                if idempotency_key is None:
                    raise AppError(422, "validation_error", "Idempotency-Key es obligatorio para el cobro inicial")
                replay = self.payments.find_replay_in_transaction(
                    tenant_id, sale_id, initial_payment,
                    user_id=user_id, idempotency_key=idempotency_key,
                )
                if replay is None:
                    # Lock Sale before inventory. Recheck intent after waiting:
                    # the winner may now have confirmed and charged this sale.
                    sale = self.sales.repository.get_by_id(tenant_id, sale_id, for_update=True)
                    if sale is None:
                        raise AppError(404, "sale_not_found", "Venta no encontrada")
                    replay = self.payments.find_replay_in_transaction(
                        tenant_id, sale_id, initial_payment,
                        user_id=user_id, idempotency_key=idempotency_key,
                    )
                self.idempotency_replayed = replay is not None

            if payload.initial_payments is None and not self.idempotency_replayed:
                self.sales.confirm_in_transaction(
                    tenant_id, sale_id, confirmed_by_user_id=user_id,
                )
                if initial_payment is not None:
                    self.payments.create_in_transaction(
                        tenant_id, sale_id, initial_payment,
                        user_id=user_id, idempotency_key=idempotency_key,
                    )
            if not self.idempotency_replayed:
                self.sales.validate_confirmation_balance_in_transaction(tenant_id, sale_id)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        # Reload the current detail, including payments and their summary, even
        # if the caller configured expire_on_commit=False.
        self.db.expire_all()
        return self.sales.get(tenant_id, sale_id)

    def _confirm_batch(
        self, tenant_id: uuid.UUID, sale_id: uuid.UUID, payments: list[SaleInitialPaymentCreate],
        *, user_id: uuid.UUID | None, idempotency_key: str | None,
    ) -> None:
        self.payments._validate_user(tenant_id, user_id)
        key = self.payments._normalize_idempotency_key(idempotency_key)
        if key is None:
            raise AppError(422, "validation_error", "Idempotency-Key es obligatorio para los cobros iniciales")
        request_hash = batch_request_hash(sale_id, payments)
        if self._batch_replay(tenant_id, key, request_hash):
            return
        sale = self.sales.repository.get_by_id(tenant_id, sale_id, for_update=True)
        if sale is None:
            raise AppError(404, "sale_not_found", "Venta no encontrada")
        if self._batch_replay(tenant_id, key, request_hash):
            return
        total = sum((payment.amount_ars for payment in payments), Decimal("0.00"))
        if total > sale.total_ars:
            raise AppError(409, "sale_payment_batch_exceeds_total", "La suma de los cobros supera el total de la venta")
        # Reserve the tenant-wide key BEFORE inventory locks. A competing sale
        # can then wait for this identity without holding shared inventory.
        batch = SalePaymentBatch(tenant_id=tenant_id, sale_id=sale_id, idempotency_key=key, request_hash=request_hash)
        try:
            self.batches.create(batch)
        except IntegrityError as exc:
            original = exc.orig
            is_collision = (
                getattr(original, "pgcode", None) == "23505"
                and getattr(getattr(original, "diag", None), "constraint_name", None) == "uq_sale_payment_batches_tenant_key"
            ) or (
                getattr(original, "sqlite_errorname", None) == "SQLITE_CONSTRAINT_UNIQUE"
                and str(original) == "UNIQUE constraint failed: sale_payment_batches.tenant_id, sale_payment_batches.idempotency_key"
            )
            if not is_collision:
                raise
            # Same-sale retries are serialized by Sale and rechecked above.
            # A collision here is another sale using this key: roll back the
            # entire outer transaction, rather than recover a partial batch.
            raise self._batch_conflict() from exc
        sale = self.sales.confirm_in_transaction(tenant_id, sale_id, confirmed_by_user_id=user_id)
        for payment in payments:
            self.payments.create_for_locked_sale_in_transaction(
                tenant_id, sale, payment, user_id=user_id, batch=batch,
            )

    def _batch_replay(self, tenant_id: uuid.UUID, key: str, request_hash: str) -> bool:
        existing = self.batches.get_by_idempotency_key(tenant_id, key)
        if existing is None:
            return False
        if existing.request_hash != request_hash:
            raise self._batch_conflict()
        self.idempotency_replayed = True
        return True

    @staticmethod
    def _batch_conflict() -> AppError:
        return AppError(409, "sale_payment_batch_idempotency_conflict", "La solicitud de cobros ya se utilizó con datos diferentes")

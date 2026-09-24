from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.payment import PaymentMethod, SalePayment
from app.models.user import User


class PaymentMethodRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, method: PaymentMethod) -> PaymentMethod:
        self.db.add(method)
        self.db.flush()
        return method

    save = create

    def get_by_id(self, tenant_id: uuid.UUID, method_id: uuid.UUID, *, for_update: bool = False) -> PaymentMethod | None:
        statement = select(PaymentMethod).where(PaymentMethod.tenant_id == tenant_id, PaymentMethod.id == method_id)
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def find_active_label(self, tenant_id: uuid.UUID, normalized_label: str, *, exclude_id: uuid.UUID | None = None) -> PaymentMethod | None:
        filters = [PaymentMethod.tenant_id == tenant_id, PaymentMethod.normalized_label == normalized_label, PaymentMethod.is_active.is_(True)]
        if exclude_id:
            filters.append(PaymentMethod.id != exclude_id)
        return self.db.scalar(select(PaymentMethod).where(*filters))

    def has_payments(self, tenant_id: uuid.UUID, method_id: uuid.UUID) -> bool:
        return bool(self.db.scalar(select(func.count(SalePayment.id)).where(SalePayment.tenant_id == tenant_id, SalePayment.payment_method_id == method_id)))

    def list(self, tenant_id: uuid.UUID, *, active: bool | None, method_type: str | None, search: str | None, page: int, page_size: int) -> tuple[list[tuple[PaymentMethod, bool]], int]:
        filters = [PaymentMethod.tenant_id == tenant_id]
        if active is not None:
            filters.append(PaymentMethod.is_active.is_(active))
        if method_type:
            filters.append(PaymentMethod.type == method_type)
        if search:
            filters.append(PaymentMethod.label.ilike(f"%{search}%"))
        used = select(func.count(SalePayment.id) > 0).where(SalePayment.tenant_id == tenant_id, SalePayment.payment_method_id == PaymentMethod.id).correlate(PaymentMethod).scalar_subquery()
        rows = self.db.execute(
            select(PaymentMethod, used.label("has_payments")).where(*filters)
            .order_by(PaymentMethod.sort_order, func.lower(PaymentMethod.label), PaymentMethod.id)
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        total = int(self.db.scalar(select(func.count(PaymentMethod.id)).where(*filters)) or 0)
        return [(row[0], bool(row[1])) for row in rows], total


class SalePaymentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payment: SalePayment) -> SalePayment:
        self.db.add(payment)
        self.db.flush()
        return payment

    save = create

    def get_by_id(self, tenant_id: uuid.UUID, payment_id: uuid.UUID, *, for_update: bool = False) -> SalePayment | None:
        statement = (
            select(SalePayment)
            .where(SalePayment.tenant_id == tenant_id, SalePayment.id == payment_id)
            .options(
                selectinload(SalePayment.created_by_user.and_(User.tenant_id == tenant_id)),
                selectinload(SalePayment.voided_by_user.and_(User.tenant_id == tenant_id)),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list_for_sale(self, tenant_id: uuid.UUID, sale_id: uuid.UUID) -> list[SalePayment]:
        return list(self.db.scalars(
            select(SalePayment)
            .where(SalePayment.tenant_id == tenant_id, SalePayment.sale_id == sale_id)
            .options(
                selectinload(SalePayment.created_by_user.and_(User.tenant_id == tenant_id)),
                selectinload(SalePayment.voided_by_user.and_(User.tenant_id == tenant_id)),
            )
            .order_by(SalePayment.received_at.desc(), SalePayment.created_at.desc(), SalePayment.id.desc())
        ).all())

    def active_total(self, tenant_id: uuid.UUID, sale_id: uuid.UUID) -> Decimal:
        return self.db.scalar(select(func.coalesce(func.sum(SalePayment.amount_ars), 0)).where(SalePayment.tenant_id == tenant_id, SalePayment.sale_id == sale_id, SalePayment.is_active.is_(True))) or Decimal("0")

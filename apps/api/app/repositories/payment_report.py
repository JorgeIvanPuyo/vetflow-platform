import uuid
from datetime import datetime

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.models.owner import Owner
from app.models.patient import Patient
from app.models.payment import PaymentMethod, SalePayment
from app.models.sale import Sale
from app.models.user import User
from app.repositories.payment import active_payment_criteria


class PaymentReportRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def methods(self, tenant_id: uuid.UUID):
        # Complete selector, including inactive methods; no 100-row truncation.
        return self.db.execute(select(
            PaymentMethod.id.label("payment_method_id"), PaymentMethod.label, PaymentMethod.is_active,
        ).where(PaymentMethod.tenant_id == tenant_id).order_by(
            PaymentMethod.sort_order, func.lower(PaymentMethod.label), PaymentMethod.id,
        )).mappings().all()

    def read(self, tenant_id: uuid.UUID, *, start: datetime, end: datetime,
             method_id: uuid.UUID | None, page: int, page_size: int):
        criteria = [*active_payment_criteria(tenant_id), SalePayment.received_at >= start, SalePayment.received_at < end]
        if method_id is not None:
            criteria.append(SalePayment.payment_method_id == method_id)
        # Validate sale and method membership in both the aggregate and detail.
        base = select(
            SalePayment.id.label("payment_id"), SalePayment.received_at,
            SalePayment.payment_method_id, SalePayment.payment_method_label_snapshot.label("payment_method_label"),
            SalePayment.amount_ars, SalePayment.sale_id, SalePayment.reference,
            SalePayment.created_by_user_id,
            Sale.owner_id, Sale.owner_name_snapshot, Sale.patient_id, Sale.patient_name_snapshot,
        ).join(Sale, and_(Sale.id == SalePayment.sale_id, Sale.tenant_id == tenant_id)).join(
            PaymentMethod, and_(PaymentMethod.id == SalePayment.payment_method_id, PaymentMethod.tenant_id == tenant_id),
        ).where(*criteria).cte("filtered_payments")
        ranked = select(base.c.payment_method_id, base.c.payment_method_label, base.c.amount_ars,
            func.row_number().over(partition_by=base.c.payment_method_id,
                order_by=(base.c.received_at.desc(), base.c.payment_id.desc())).label("position"),
        ).cte("ranked_payments")
        # One identity per method. Latest snapshot within this filter is the group label.
        groups = self.db.execute(select(
            ranked.c.payment_method_id,
            func.max(case((ranked.c.position == 1, ranked.c.payment_method_label))).label("label"),
            func.sum(ranked.c.amount_ars).label("amount_ars"),
            func.count().label("payment_count"),
        ).group_by(ranked.c.payment_method_id).order_by(ranked.c.payment_method_id)).mappings().all()
        rows = self.db.execute(select(
            base.c.payment_id, base.c.received_at, base.c.payment_method_id, base.c.payment_method_label,
            base.c.amount_ars, base.c.sale_id, base.c.reference,
            Owner.id.label("owner_id"),
            case((or_(base.c.owner_id.is_(None), Owner.id.is_not(None)), base.c.owner_name_snapshot)).label("owner_name"),
            Patient.id.label("patient_id"),
            case((or_(base.c.patient_id.is_(None), Patient.id.is_not(None)), base.c.patient_name_snapshot)).label("patient_name"),
            User.id.label("created_by_user_id"), User.full_name.label("created_by_user_name"),
        ).outerjoin(Owner, and_(Owner.id == base.c.owner_id, Owner.tenant_id == tenant_id)).outerjoin(
            Patient, and_(Patient.id == base.c.patient_id, Patient.tenant_id == tenant_id),
        ).outerjoin(User, and_(User.id == base.c.created_by_user_id, User.tenant_id == tenant_id)).order_by(
            base.c.received_at.desc(), base.c.payment_id.desc(),
        ).offset((page - 1) * page_size).limit(page_size)).mappings().all()
        return groups, rows

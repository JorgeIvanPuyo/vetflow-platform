"""Derived receivables with explicit tenant cutoffs and active payments."""

import uuid
from decimal import Decimal

from sqlalchemy import and_, case, func, or_, select, true
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models.owner import Owner
from app.models.patient import Patient
from app.models.payment import SalePayment
from app.models.sale import Sale, calculate_balance_due
from app.models.tenant_preference import TenantPreference
from app.repositories.payment import active_payment_total_statement


def receivable_sale_criteria(tenant_id: uuid.UUID) -> ColumnElement[bool]:
    """Reusable WHERE criterion with the tenant's explicitly configured cutoff.

    A missing preference or NULL cutoff selects nothing. Fully paid sales and
    archived owners remain eligible; future balances must subtract active payments.
    """
    cutoff = select(TenantPreference.receivables_tracking_started_at).where(
        TenantPreference.tenant_id == tenant_id,
    ).scalar_subquery()
    identified_owner = select(Owner.id).where(
        Owner.tenant_id == tenant_id, Owner.id == Sale.owner_id,
    ).exists()
    return and_(
        Sale.tenant_id == tenant_id,
        Sale.status == "confirmed",
        Sale.owner_id.is_not(None),
        identified_owner,
        Sale.confirmed_at >= cutoff,
    )


class ReceivablesRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def statement(tenant_id: uuid.UUID, owner_id: uuid.UUID, *, page: int, page_size: int):
        eligible = select(
            Sale.id.label("sale_id"), Sale.sale_date, Sale.confirmed_at,
            Patient.id.label("patient_id"),
            case((or_(Sale.patient_id.is_(None), Patient.id.is_not(None)), Sale.patient_name_snapshot), else_=None).label("patient_name_snapshot"),
            Sale.currency, Sale.total_ars,
        ).outerjoin(Patient, and_(Patient.tenant_id == tenant_id, Patient.id == Sale.patient_id)).where(
            receivable_sale_criteria(tenant_id), Sale.owner_id == owner_id,
        ).cte("eligible_receivable_sales")
        # Restrict payment aggregation to this owner's eligible sales, without
        # loading ORM relationships or making per-sale requests.
        paid = active_payment_total_statement(tenant_id).add_columns(SalePayment.sale_id).where(
            SalePayment.sale_id.in_(select(eligible.c.sale_id)),
        ).group_by(SalePayment.sale_id).subquery("active_sale_totals")
        paid_total = func.coalesce(paid.c.paid_total_ars, Decimal("0.00"))
        balance = calculate_balance_due(eligible.c.total_ars, paid_total)
        outstanding = select(
            eligible, paid_total.label("paid_total_ars"), balance.label("balance_due_ars"),
        ).outerjoin(paid, paid.c.sale_id == eligible.c.sale_id).where(
            balance > 0,
        ).cte("open_receivable_sales")
        summary = select(
            func.coalesce(func.sum(outstanding.c.balance_due_ars), Decimal("0.00")).label("total_outstanding_ars"),
            func.count(outstanding.c.sale_id).label("open_sales_count"),
        ).subquery("receivables_summary")
        sales_page = select(outstanding).order_by(
            outstanding.c.confirmed_at.desc(), outstanding.c.sale_id.desc(),
        ).offset((page - 1) * page_size).limit(page_size).subquery("sales_page")
        # One SQL snapshot gives the global summary even on an empty/beyond-last
        # page, and keeps it consistent with the rows during concurrent payments.
        return select(summary, sales_page).select_from(
            summary.outerjoin(sales_page, true()),
        ).order_by(sales_page.c.confirmed_at.desc(), sales_page.c.sale_id.desc())

    def get(self, tenant_id: uuid.UUID, owner_id: uuid.UUID, *, page: int, page_size: int) -> tuple[Decimal, int, list[dict]]:
        rows = self.db.execute(self.statement(tenant_id, owner_id, page=page, page_size=page_size)).mappings().all()
        total = rows[0]["total_outstanding_ars"]
        count = rows[0]["open_sales_count"]
        sales = [
            {key: value for key, value in row.items() if key not in {"total_outstanding_ars", "open_sales_count"}}
            for row in rows if row["sale_id"] is not None
        ]
        return total, count, sales

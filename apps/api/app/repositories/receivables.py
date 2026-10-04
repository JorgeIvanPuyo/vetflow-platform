"""Derived receivables with explicit tenant cutoffs and active payments."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, case, func, literal, or_, select, true, union_all
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models.owner import Owner
from app.models.patient import Patient
from app.models.payment import PaymentMethod, SalePayment
from app.models.sale import Sale, calculate_balance_due
from app.models.tenant_preference import TenantPreference
from app.repositories.payment import active_payment_total_statement


def receivable_sale_criteria(tenant_id: uuid.UUID, *, include_history: bool = False) -> ColumnElement[bool]:
    """Reusable WHERE criterion with the tenant's explicitly configured cutoff.

    A missing preference or NULL cutoff selects nothing. Fully paid sales and
    archived owners remain eligible; balances subtract active payments. History
    also includes formerly confirmed reversed sales; cancelled drafts never enter.
    """
    cutoff = select(TenantPreference.receivables_tracking_started_at).where(
        TenantPreference.tenant_id == tenant_id,
    ).scalar_subquery()
    identified_owner = select(Owner.id).where(
        Owner.tenant_id == tenant_id, Owner.id == Sale.owner_id,
    ).exists()
    return and_(
        Sale.tenant_id == tenant_id,
        Sale.status.in_(("confirmed", "reversed")) if include_history else Sale.status == "confirmed",
        Sale.owner_id.is_not(None),
        identified_owner,
        Sale.confirmed_at >= cutoff,
    )


class ReceivablesRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def owner_signals_statement(tenant_id: uuid.UUID, owner_ids: set[uuid.UUID]):
        """One bounded lookup for owner names and the positive P.11 balance signal.

        P.11 sums only positive sale balances, so existence of an open eligible
        sale is equivalent to total_outstanding_ars > 0. No balance is persisted.
        """
        eligible = select(Sale.id.label("sale_id"), Sale.owner_id, Sale.total_ars).where(
            receivable_sale_criteria(tenant_id), Sale.owner_id.in_(owner_ids),
        ).cte("signal_sales")
        paid = active_payment_total_statement(tenant_id).add_columns(SalePayment.sale_id).where(
            SalePayment.sale_id.in_(select(eligible.c.sale_id)),
        ).group_by(SalePayment.sale_id).subquery("signal_payments")
        open_owners = select(eligible.c.owner_id).outerjoin(
            paid, paid.c.sale_id == eligible.c.sale_id,
        ).where(
            calculate_balance_due(eligible.c.total_ars, func.coalesce(paid.c.paid_total_ars, Decimal("0.00"))) > 0,
        ).distinct().subquery("owners_with_receivables")
        return select(
            Owner.id, Owner.full_name,
            open_owners.c.owner_id.is_not(None).label("has_active_receivable"),
        ).outerjoin(open_owners, open_owners.c.owner_id == Owner.id).where(
            Owner.tenant_id == tenant_id, Owner.id.in_(owner_ids),
        )

    def owner_signals(self, tenant_id: uuid.UUID, owner_ids: set[uuid.UUID]) -> dict:
        if not owner_ids:
            return {}
        rows = self.db.execute(self.owner_signals_statement(tenant_id, owner_ids)).mappings().all()
        return {row["id"]: row for row in rows}

    @staticmethod
    def eligible_statement(tenant_id: uuid.UUID, owner_id: uuid.UUID, *, include_history: bool = False):
        return select(
            Sale.id.label("sale_id"), Sale.sale_date, Sale.confirmed_at,
            Patient.id.label("patient_id"),
            case((or_(Sale.patient_id.is_(None), Patient.id.is_not(None)), Sale.patient_name_snapshot), else_=None).label("patient_name_snapshot"),
            Sale.currency, Sale.total_ars,
            Sale.status, Sale.reversed_at, Sale.reversal_reason,
        ).outerjoin(Patient, and_(Patient.tenant_id == tenant_id, Patient.id == Sale.patient_id)).where(
            receivable_sale_criteria(tenant_id, include_history=include_history), Sale.owner_id == owner_id,
        )

    @staticmethod
    def statement(tenant_id: uuid.UUID, owner_id: uuid.UUID, *, page: int, page_size: int,
                  date_from: date | None = None, date_to: date | None = None, patient_id: uuid.UUID | None = None):
        eligible = ReceivablesRepository.eligible_statement(tenant_id, owner_id).cte("eligible_receivable_sales")
        # Restrict payment aggregation to this owner's eligible sales, without
        # loading ORM relationships or making per-sale requests.
        paid = active_payment_total_statement(tenant_id).add_columns(SalePayment.sale_id).where(
            SalePayment.sale_id.in_(select(eligible.c.sale_id)),
        ).group_by(SalePayment.sale_id).subquery("active_sale_totals")
        paid_total = func.coalesce(paid.c.paid_total_ars, Decimal("0.00"))
        balance = calculate_balance_due(eligible.c.total_ars, paid_total)
        outstanding = select(
            *(eligible.c[name] for name in ("sale_id", "sale_date", "confirmed_at", "patient_id", "patient_name_snapshot", "currency", "total_ars")),
            paid_total.label("paid_total_ars"), balance.label("balance_due_ars"),
        ).outerjoin(paid, paid.c.sale_id == eligible.c.sale_id).where(
            balance > 0,
        ).cte("open_receivable_sales")
        filters = []
        if date_from is not None:
            filters.append(outstanding.c.sale_date >= date_from)
        if date_to is not None:
            filters.append(outstanding.c.sale_date <= date_to)
        if patient_id is not None:
            filters.append(outstanding.c.patient_id == patient_id)
        filtered = select(outstanding).where(*filters).cte("filtered_receivable_sales")
        summary = select(
            func.coalesce(func.sum(outstanding.c.balance_due_ars), Decimal("0.00")).label("total_outstanding_ars"),
            func.count(outstanding.c.sale_id).label("open_sales_count"),
            select(func.count()).select_from(filtered).scalar_subquery().label("filtered_sales_count"),
        ).subquery("receivables_summary")
        sales_page = select(filtered).order_by(
            filtered.c.confirmed_at.desc(), filtered.c.sale_id.desc(),
        ).offset((page - 1) * page_size).limit(page_size).subquery("sales_page")
        # One SQL snapshot gives the global summary even on an empty/beyond-last
        # page, and keeps it consistent with the rows during concurrent payments.
        return select(summary, sales_page).select_from(
            summary.outerjoin(sales_page, true()),
        ).order_by(sales_page.c.confirmed_at.desc(), sales_page.c.sale_id.desc())

    def get(self, tenant_id: uuid.UUID, owner_id: uuid.UUID, *, page: int, page_size: int, **filters) -> tuple[Decimal, int, list[dict], int]:
        rows = self.db.execute(self.statement(tenant_id, owner_id, page=page, page_size=page_size, **filters)).mappings().all()
        total = rows[0]["total_outstanding_ars"]
        count = rows[0]["open_sales_count"]
        sales = [
            {key: value for key, value in row.items() if key not in {"total_outstanding_ars", "open_sales_count", "filtered_sales_count"}}
            for row in rows if row["sale_id"] is not None
        ]
        return total, count, sales, rows[0]["filtered_sales_count"]

    @staticmethod
    def activity_statement(tenant_id: uuid.UUID, owner_id: uuid.UUID, *, page: int, page_size: int):
        sales = ReceivablesRepository.eligible_statement(tenant_id, owner_id, include_history=True).cte("account_sales")
        # Typed NULLs let PostgreSQL reconcile all UNION branches (including UUID
        # and NUMERIC) without converting monetary values to float/text.
        no_payment = literal(None, type_=SalePayment.id.type)
        no_text = literal(None, type_=SalePayment.notes.type)
        no_amount = literal(None, type_=Sale.total_ars.type)
        no_active = literal(None, type_=SalePayment.is_active.type)
        common = [sales.c.sale_id, sales.c.sale_date, sales.c.patient_id, sales.c.patient_name_snapshot, sales.c.currency]

        def sale_event(kind, occurred_at, amount, reason):
            return select(literal(kind).label("type"), sales.c.sale_id.label("source_id"), occurred_at.label("occurred_at"),
                *common, no_payment.label("payment_id"), amount.label("amount_ars"),
                no_text.label("payment_method_label"), no_text.label("reference"), no_text.label("notes"),
                reason.label("reason"), no_active.label("payment_is_active")).select_from(sales)

        def payment_event(kind, occurred_at, reason):
            return select(
                literal(kind).label("type"), SalePayment.id.label("source_id"), occurred_at.label("occurred_at"),
                *common, SalePayment.id.label("payment_id"), SalePayment.amount_ars,
                case((PaymentMethod.id.is_not(None), SalePayment.payment_method_label_snapshot), else_=None).label("payment_method_label"),
                SalePayment.reference, SalePayment.notes, reason.label("reason"), SalePayment.is_active.label("payment_is_active"),
            ).select_from(sales).join(SalePayment, and_(SalePayment.tenant_id == tenant_id, SalePayment.sale_id == sales.c.sale_id)).outerjoin(
                PaymentMethod, and_(PaymentMethod.tenant_id == tenant_id, PaymentMethod.id == SalePayment.payment_method_id),
            )
        recorded = payment_event("payment_recorded", SalePayment.received_at, no_text)
        voided = payment_event("payment_cancelled", SalePayment.voided_at, SalePayment.void_reason).where(
            SalePayment.is_active.is_(False), SalePayment.voided_at.is_not(None),
        )
        reversed_sale = sale_event("sale_reversed", sales.c.reversed_at, no_amount, sales.c.reversal_reason).where(
            sales.c.status == "reversed", sales.c.reversed_at.is_not(None),
        )
        events = union_all(sale_event("sale_confirmed", sales.c.confirmed_at, sales.c.total_ars, no_text), recorded, voided, reversed_sale).cte("account_activity")
        summary = select(func.count().label("total")).select_from(events).subquery("activity_count")
        event_page = select(events).order_by(events.c.occurred_at.desc(), events.c.source_id.desc(), events.c.type.desc()).offset(
            (page - 1) * page_size,
        ).limit(page_size).subquery("activity_page")
        return select(summary, event_page).select_from(summary.outerjoin(event_page, true())).order_by(
            event_page.c.occurred_at.desc(), event_page.c.source_id.desc(), event_page.c.type.desc(),
        )

    def activity(self, tenant_id: uuid.UUID, owner_id: uuid.UUID, *, page: int, page_size: int) -> tuple[list[dict], int]:
        rows = self.db.execute(self.activity_statement(tenant_id, owner_id, page=page, page_size=page_size)).mappings().all()
        return [{key: value for key, value in row.items() if key != "total"} for row in rows if row["source_id"] is not None], rows[0]["total"]

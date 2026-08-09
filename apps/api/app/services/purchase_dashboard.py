from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.repositories.purchase_dashboard import PurchaseDashboardRepository
from app.schemas.purchase_dashboard import (
    PurchaseDashboardAttentionRead,
    PurchaseDashboardRead,
    PurchaseDashboardRecentPurchaseRead,
    PurchaseDashboardTopSupplierRead,
)


MONEY_QUANTUM = Decimal("0.01")
ATTENTION_LIMIT = 15
TOP_SUPPLIER_LIMIT = 5
RECENT_PURCHASE_LIMIT = 8
OLD_DRAFT_DAYS = 7


class PurchaseDashboardService:
    def __init__(self, db: Session) -> None:
        self.repository = PurchaseDashboardRepository(db)

    def get_dashboard(
        self,
        tenant_id: uuid.UUID,
        *,
        date_from: date | None,
        date_to: date | None,
        supplier_id: uuid.UUID | None,
        created_by_user_id: uuid.UUID | None,
        document_type: str | None,
    ) -> PurchaseDashboardRead:
        start_date, end_date = self._resolve_period(date_from, date_to)
        repository_filters = {
            "date_from": start_date,
            "date_to": end_date,
            "supplier_id": supplier_id,
            "created_by_user_id": created_by_user_id,
            "document_type": document_type,
        }
        summary = self.repository.get_summary(tenant_id, **repository_filters)
        attention_rows = self.repository.list_attention(
            tenant_id,
            **repository_filters,
            old_draft_cutoff=date.today() - timedelta(days=OLD_DRAFT_DAYS),
            limit=ATTENTION_LIMIT,
        )
        supplier_rows = self.repository.list_top_suppliers(
            tenant_id,
            **repository_filters,
            limit=TOP_SUPPLIER_LIMIT,
        )
        recent_rows = self.repository.list_recent_purchases(
            tenant_id,
            **repository_filters,
            limit=RECENT_PURCHASE_LIMIT,
        )

        return PurchaseDashboardRead(
            generated_at=datetime.now(UTC),
            period={"date_from": start_date, "date_to": end_date},
            filters={
                "supplier_id": supplier_id,
                "created_by_user_id": created_by_user_id,
                "document_type": document_type,
            },
            summary={
                "registered_total_ars": self._money(
                    summary["registered_total_ars"]
                ),
                "received_total_ars": self._money(summary["received_total_ars"]),
                "registered_tax_total_ars": self._money(
                    summary["registered_tax_total_ars"]
                ),
                "received_tax_total_ars": self._money(
                    summary["received_tax_total_ars"]
                ),
                "purchase_count": int(summary["purchase_count"] or 0),
                "draft_count": int(summary["draft_count"] or 0),
                "received_count": int(summary["received_count"] or 0),
                "reversed_count": int(summary["reversed_count"] or 0),
                "cancelled_count": int(summary["cancelled_count"] or 0),
                "attachment_pending_count": int(
                    summary["attachment_pending_count"] or 0
                ),
                "attachment_attached_count": int(
                    summary["attachment_attached_count"] or 0
                ),
            },
            attention=[self._attention_row(row) for row in attention_rows],
            top_suppliers=[
                PurchaseDashboardTopSupplierRead(
                    supplier_id=row["supplier_id"],
                    supplier_name=row["supplier_name"],
                    purchase_count=int(row["purchase_count"] or 0),
                    registered_total_ars=self._money(row["registered_total_ars"]),
                    received_total_ars=self._money(row["received_total_ars"]),
                )
                for row in supplier_rows
            ],
            recent_purchases=[
                PurchaseDashboardRecentPurchaseRead(
                    id=row["id"],
                    purchase_date=row["purchase_date"],
                    supplier_name=row["supplier_name"],
                    document_type=row["document_type"],
                    document_number=row["document_number"],
                    total_ars=self._money(row["total_ars"]),
                    status=row["status"],
                    attachment_status=(
                        "attached" if row["has_attachment"] else "pending"
                    ),
                    created_by_user_id=(
                        row["created_by_user_id"]
                        if row["created_by_user_name"]
                        or row["created_by_user_email"]
                        else None
                    ),
                    created_by_user_name=row["created_by_user_name"],
                    created_by_user_email=row["created_by_user_email"],
                    created_at=row["created_at"],
                )
                for row in recent_rows
            ],
        )

    @staticmethod
    def _resolve_period(
        date_from: date | None, date_to: date | None
    ) -> tuple[date, date]:
        today = date.today()
        if date_from is None and date_to is None:
            start_date = today.replace(day=1)
            end_date = today.replace(day=monthrange(today.year, today.month)[1])
        elif date_from is None:
            assert date_to is not None
            start_date = date_to.replace(day=1)
            end_date = date_to
        elif date_to is None:
            start_date = date_from
            end_date = date_from.replace(
                day=monthrange(date_from.year, date_from.month)[1]
            )
        else:
            start_date = date_from
            end_date = date_to
        if start_date > end_date:
            raise AppError(
                422,
                "validation_error",
                "date_from must be before or equal to date_to",
            )
        return start_date, end_date

    @classmethod
    def _attention_row(cls, row: dict) -> PurchaseDashboardAttentionRead:
        alerts = []
        if row["old_draft"]:
            alerts.append("old_draft")
        if row["attachment_pending"]:
            alerts.append("attachment_pending")
        if row["document_number_missing"]:
            alerts.append("document_number_missing")
        if row["reversed_receipt"]:
            alerts.append("reversed_receipt")
        priority_order = int(row["priority_order"])
        priority = "high" if priority_order <= 2 else "medium"
        if row["reversed_receipt"] and len(alerts) == 1:
            priority = "info"
        return PurchaseDashboardAttentionRead(
            id=row["id"],
            purchase_date=row["purchase_date"],
            supplier_name=row["supplier_name"],
            document_number=row["document_number"],
            total_ars=cls._money(row["total_ars"]),
            status=row["status"],
            attachment_status=("attached" if row["has_attachment"] else "pending"),
            alerts=alerts,
            priority=priority,
        )

    @staticmethod
    def _money(value) -> Decimal:
        return Decimal(value or 0).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)

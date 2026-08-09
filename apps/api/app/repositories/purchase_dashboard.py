from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import and_, case, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models.purchase import Purchase
from app.models.user import User
from app.repositories.purchase import (
    active_purchase_attachment_exists,
    build_purchase_filters,
)


REGISTERED_STATUSES = ("draft", "received")


class PurchaseDashboardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_summary(
        self,
        tenant_id: uuid.UUID,
        *,
        date_from: date,
        date_to: date,
        supplier_id: uuid.UUID | None,
        created_by_user_id: uuid.UUID | None,
        document_type: str | None,
    ) -> dict:
        filters = self._dashboard_filters(
            tenant_id,
            date_from=date_from,
            date_to=date_to,
            supplier_id=supplier_id,
            created_by_user_id=created_by_user_id,
            document_type=document_type,
        )
        has_attachment = active_purchase_attachment_exists(tenant_id)
        non_cancelled = Purchase.status != "cancelled"
        statement = select(
            func.coalesce(
                func.sum(Purchase.total_ars).filter(
                    Purchase.status.in_(REGISTERED_STATUSES)
                ),
                0,
            ).label("registered_total_ars"),
            func.coalesce(
                func.sum(Purchase.total_ars).filter(Purchase.status == "received"),
                0,
            ).label("received_total_ars"),
            func.coalesce(
                func.sum(Purchase.tax_total_ars).filter(
                    Purchase.status.in_(REGISTERED_STATUSES)
                ),
                0,
            ).label("registered_tax_total_ars"),
            func.coalesce(
                func.sum(Purchase.tax_total_ars).filter(
                    Purchase.status == "received"
                ),
                0,
            ).label("received_tax_total_ars"),
            func.count(Purchase.id).label("purchase_count"),
            func.count(Purchase.id)
            .filter(Purchase.status == "draft")
            .label("draft_count"),
            func.count(Purchase.id)
            .filter(Purchase.status == "received")
            .label("received_count"),
            func.count(Purchase.id)
            .filter(Purchase.status == "reversed")
            .label("reversed_count"),
            func.count(Purchase.id)
            .filter(Purchase.status == "cancelled")
            .label("cancelled_count"),
            func.count(Purchase.id)
            .filter(non_cancelled, ~has_attachment)
            .label("attachment_pending_count"),
            func.count(Purchase.id)
            .filter(non_cancelled, has_attachment)
            .label("attachment_attached_count"),
        ).where(*filters)
        return dict(self.db.execute(statement).mappings().one())

    def list_attention(
        self,
        tenant_id: uuid.UUID,
        *,
        date_from: date,
        date_to: date,
        supplier_id: uuid.UUID | None,
        created_by_user_id: uuid.UUID | None,
        document_type: str | None,
        old_draft_cutoff: date,
        limit: int,
    ) -> list[dict]:
        filters = self._dashboard_filters(
            tenant_id,
            date_from=date_from,
            date_to=date_to,
            supplier_id=supplier_id,
            created_by_user_id=created_by_user_id,
            document_type=document_type,
        )
        has_attachment = active_purchase_attachment_exists(tenant_id)
        old_draft = and_(
            Purchase.status == "draft", Purchase.purchase_date < old_draft_cutoff
        )
        attachment_pending = and_(
            Purchase.status.in_(("draft", "received")), ~has_attachment
        )
        reversed_receipt = Purchase.status == "reversed"
        document_number_missing = and_(
            Purchase.status == "received",
            or_(
                Purchase.document_number.is_(None),
                func.trim(Purchase.document_number) == "",
            ),
        )
        priority = case(
            (and_(Purchase.status == "received", ~has_attachment), 0),
            (old_draft, 1),
            (document_number_missing, 2),
            (attachment_pending, 3),
            (reversed_receipt, 4),
            else_=5,
        )
        statement = (
            select(
                Purchase.id,
                Purchase.purchase_date,
                Purchase.supplier_name,
                Purchase.document_number,
                Purchase.total_ars,
                Purchase.status,
                has_attachment.label("has_attachment"),
                old_draft.label("old_draft"),
                attachment_pending.label("attachment_pending"),
                reversed_receipt.label("reversed_receipt"),
                document_number_missing.label("document_number_missing"),
                priority.label("priority_order"),
            )
            .where(
                *filters,
                or_(
                    old_draft,
                    attachment_pending,
                    reversed_receipt,
                    document_number_missing,
                ),
            )
            .order_by(
                priority.asc(),
                Purchase.purchase_date.asc(),
                Purchase.created_at.desc(),
                Purchase.id.desc(),
            )
            .limit(limit)
        )
        return [dict(row) for row in self.db.execute(statement).mappings().all()]

    def list_top_suppliers(
        self,
        tenant_id: uuid.UUID,
        *,
        date_from: date,
        date_to: date,
        supplier_id: uuid.UUID | None,
        created_by_user_id: uuid.UUID | None,
        document_type: str | None,
        limit: int,
    ) -> list[dict]:
        filters = self._dashboard_filters(
            tenant_id,
            date_from=date_from,
            date_to=date_to,
            supplier_id=supplier_id,
            created_by_user_id=created_by_user_id,
            document_type=document_type,
        )
        registered_total = func.coalesce(
            func.sum(Purchase.total_ars).filter(
                Purchase.status.in_(REGISTERED_STATUSES)
            ),
            0,
        )
        received_total = func.coalesce(
            func.sum(Purchase.total_ars).filter(Purchase.status == "received"),
            0,
        )
        statement = (
            select(
                Purchase.supplier_id,
                Purchase.supplier_name,
                func.count(Purchase.id).label("purchase_count"),
                registered_total.label("registered_total_ars"),
                received_total.label("received_total_ars"),
            )
            .where(*filters)
            .group_by(Purchase.supplier_id, Purchase.supplier_name)
            .order_by(
                desc(received_total),
                desc(registered_total),
                func.count(Purchase.id).desc(),
                func.lower(Purchase.supplier_name).asc(),
                Purchase.supplier_id.asc(),
            )
            .limit(limit)
        )
        return [dict(row) for row in self.db.execute(statement).mappings().all()]

    def list_recent_purchases(
        self,
        tenant_id: uuid.UUID,
        *,
        date_from: date,
        date_to: date,
        supplier_id: uuid.UUID | None,
        created_by_user_id: uuid.UUID | None,
        document_type: str | None,
        limit: int,
    ) -> list[dict]:
        filters = self._dashboard_filters(
            tenant_id,
            date_from=date_from,
            date_to=date_to,
            supplier_id=supplier_id,
            created_by_user_id=created_by_user_id,
            document_type=document_type,
        )
        has_attachment = active_purchase_attachment_exists(tenant_id)
        statement = (
            select(
                Purchase.id,
                Purchase.purchase_date,
                Purchase.supplier_name,
                Purchase.document_type,
                Purchase.document_number,
                Purchase.total_ars,
                Purchase.status,
                has_attachment.label("has_attachment"),
                Purchase.created_by_user_id,
                User.full_name.label("created_by_user_name"),
                User.email.label("created_by_user_email"),
                Purchase.created_at,
            )
            .outerjoin(
                User,
                (User.id == Purchase.created_by_user_id)
                & (User.tenant_id == tenant_id),
            )
            .where(*filters)
            .order_by(Purchase.created_at.desc(), Purchase.id.desc())
            .limit(limit)
        )
        return [dict(row) for row in self.db.execute(statement).mappings().all()]

    @staticmethod
    def _dashboard_filters(
        tenant_id: uuid.UUID,
        *,
        date_from: date,
        date_to: date,
        supplier_id: uuid.UUID | None,
        created_by_user_id: uuid.UUID | None,
        document_type: str | None,
    ) -> list:
        return build_purchase_filters(
            tenant_id,
            supplier_id=supplier_id,
            created_by_user_id=created_by_user_id,
            document_type=document_type,
            date_from=date_from,
            date_to=date_to,
        )

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import asc, desc, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.purchase import Purchase, PurchaseItem
from app.models.purchase_return import (
    PurchaseReturn,
    PurchaseReturnAttachment,
    PurchaseReturnItem,
)
from app.models.user import User


def active_purchase_return_attachment_exists(tenant_id: uuid.UUID):
    return exists(
        select(PurchaseReturnAttachment.id).where(
            PurchaseReturnAttachment.tenant_id == tenant_id,
            PurchaseReturnAttachment.purchase_return_id == PurchaseReturn.id,
            PurchaseReturnAttachment.is_active.is_(True),
        )
    )


class PurchaseReturnRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, purchase_return: PurchaseReturn) -> PurchaseReturn:
        self.db.add(purchase_return)
        self.db.flush()
        return purchase_return

    def save(self, purchase_return: PurchaseReturn) -> PurchaseReturn:
        self.db.add(purchase_return)
        self.db.flush()
        return purchase_return

    def replace_items(
        self, purchase_return: PurchaseReturn, items: list[PurchaseReturnItem]
    ) -> None:
        purchase_return.items.clear()
        self.db.flush()
        purchase_return.items.extend(items)
        self.db.add(purchase_return)
        self.db.flush()

    def get_by_id(
        self,
        tenant_id: uuid.UUID,
        return_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> PurchaseReturn | None:
        statement = (
            select(PurchaseReturn)
            .where(
                PurchaseReturn.tenant_id == tenant_id,
                PurchaseReturn.id == return_id,
            )
            .options(
                selectinload(
                    PurchaseReturn.items.and_(
                        PurchaseReturnItem.tenant_id == tenant_id
                    )
                ).selectinload(
                    PurchaseReturnItem.purchase_item.and_(
                        PurchaseItem.tenant_id == tenant_id
                    )
                ),
                selectinload(
                    PurchaseReturn.purchase.and_(Purchase.tenant_id == tenant_id)
                ),
                selectinload(
                    PurchaseReturn.created_by_user.and_(User.tenant_id == tenant_id)
                ),
                selectinload(
                    PurchaseReturn.confirmed_by_user.and_(User.tenant_id == tenant_id)
                ),
                selectinload(
                    PurchaseReturn.cancelled_by_user.and_(User.tenant_id == tenant_id)
                ),
                selectinload(
                    PurchaseReturn.attachments.and_(
                        PurchaseReturnAttachment.tenant_id == tenant_id
                    )
                ).selectinload(
                    PurchaseReturnAttachment.uploaded_by_user.and_(
                        User.tenant_id == tenant_id
                    )
                ),
                selectinload(
                    PurchaseReturn.attachments.and_(
                        PurchaseReturnAttachment.tenant_id == tenant_id
                    )
                ).selectinload(
                    PurchaseReturnAttachment.replaced_by_user.and_(
                        User.tenant_id == tenant_id
                    )
                ),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list(
        self,
        tenant_id: uuid.UUID,
        *,
        search: str | None,
        supplier_id: uuid.UUID | None,
        purchase_id: uuid.UUID | None,
        status: str | None,
        date_from: date | None,
        date_to: date | None,
        created_by_user_id: uuid.UUID | None,
        attachment_status: str | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_direction: str,
    ) -> tuple[list[tuple[PurchaseReturn, int, bool]], int]:
        filters = [PurchaseReturn.tenant_id == tenant_id]
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    PurchaseReturn.supplier_name.ilike(pattern),
                    PurchaseReturn.document_number.ilike(pattern),
                    PurchaseReturn.reason.ilike(pattern),
                )
            )
        if supplier_id:
            filters.append(PurchaseReturn.supplier_id == supplier_id)
        if purchase_id:
            filters.append(PurchaseReturn.purchase_id == purchase_id)
        if status:
            filters.append(PurchaseReturn.status == status)
        if date_from:
            filters.append(PurchaseReturn.return_date >= date_from)
        if date_to:
            filters.append(PurchaseReturn.return_date <= date_to)
        if created_by_user_id:
            filters.append(PurchaseReturn.created_by_user_id == created_by_user_id)
        has_attachment = active_purchase_return_attachment_exists(tenant_id)
        if attachment_status == "attached":
            filters.append(has_attachment)
        elif attachment_status == "pending":
            filters.append(~has_attachment)

        item_count = (
            select(func.count(PurchaseReturnItem.id))
            .where(
                PurchaseReturnItem.tenant_id == tenant_id,
                PurchaseReturnItem.purchase_return_id == PurchaseReturn.id,
            )
            .correlate(PurchaseReturn)
            .scalar_subquery()
        )
        sort_columns = {
            "return_date": PurchaseReturn.return_date,
            "created_at": PurchaseReturn.created_at,
            "total_ars": PurchaseReturn.total_ars,
            "supplier_name": func.lower(PurchaseReturn.supplier_name),
            "status": PurchaseReturn.status,
        }
        order = asc if sort_direction == "asc" else desc
        statement = (
            select(
                PurchaseReturn,
                item_count.label("item_count"),
                has_attachment.label("has_attachment"),
            )
            .where(*filters)
            .options(
                selectinload(
                    PurchaseReturn.created_by_user.and_(User.tenant_id == tenant_id)
                )
            )
            .order_by(order(sort_columns[sort_by]), order(PurchaseReturn.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        count_statement = (
            select(func.count(PurchaseReturn.id)).where(*filters)
        )
        rows = self.db.execute(statement).all()
        return [
            (row[0], int(row[1] or 0), bool(row[2])) for row in rows
        ], int(self.db.scalar(count_statement) or 0)

    def confirmed_quantities_by_purchase_item(
        self,
        tenant_id: uuid.UUID,
        purchase_id: uuid.UUID,
    ) -> dict[uuid.UUID, Decimal]:
        statement = (
            select(
                PurchaseReturnItem.purchase_item_id,
                func.coalesce(func.sum(PurchaseReturnItem.quantity), 0),
            )
            .join(
                PurchaseReturn,
                (PurchaseReturn.id == PurchaseReturnItem.purchase_return_id)
                & (PurchaseReturn.tenant_id == tenant_id),
            )
            .where(
                PurchaseReturnItem.tenant_id == tenant_id,
                PurchaseReturn.purchase_id == purchase_id,
                PurchaseReturn.status == "confirmed",
            )
            .group_by(PurchaseReturnItem.purchase_item_id)
        )
        return {
            purchase_item_id: Decimal(quantity)
            for purchase_item_id, quantity in self.db.execute(statement).all()
        }


class PurchaseReturnAttachmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active(
        self,
        tenant_id: uuid.UUID,
        return_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> PurchaseReturnAttachment | None:
        statement = (
            select(PurchaseReturnAttachment)
            .where(
                PurchaseReturnAttachment.tenant_id == tenant_id,
                PurchaseReturnAttachment.purchase_return_id == return_id,
                PurchaseReturnAttachment.is_active.is_(True),
            )
            .options(
                selectinload(
                    PurchaseReturnAttachment.uploaded_by_user.and_(
                        User.tenant_id == tenant_id
                    )
                ),
                selectinload(
                    PurchaseReturnAttachment.replaced_by_user.and_(
                        User.tenant_id == tenant_id
                    )
                ),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def create(
        self, attachment: PurchaseReturnAttachment
    ) -> PurchaseReturnAttachment:
        self.db.add(attachment)
        self.db.flush()
        return attachment

    def save(
        self, attachment: PurchaseReturnAttachment
    ) -> PurchaseReturnAttachment:
        self.db.add(attachment)
        self.db.flush()
        return attachment

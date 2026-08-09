from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import asc, case, desc, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.inventory_item import InventoryItem
from app.models.purchase import Purchase, PurchaseItem
from app.models.purchase_attachment import PurchaseAttachment
from app.models.purchase_return import (
    PurchaseReturn,
    PurchaseReturnAttachment,
    PurchaseReturnItem,
)
from app.models.supplier import Supplier
from app.models.user import User


def active_purchase_attachment_exists(tenant_id: uuid.UUID):
    return exists(
        select(PurchaseAttachment.id).where(
            PurchaseAttachment.tenant_id == tenant_id,
            PurchaseAttachment.purchase_id == Purchase.id,
            PurchaseAttachment.is_active.is_(True),
        )
    )


def build_purchase_filters(
    tenant_id: uuid.UUID,
    *,
    search: str | None = None,
    supplier: str | None = None,
    supplier_id: uuid.UUID | None = None,
    status: str | None = None,
    document_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    created_by_user_id: uuid.UUID | None = None,
    attachment_status: str | None = None,
) -> list:
    filters = [Purchase.tenant_id == tenant_id]
    if search:
        pattern = f"%{search}%"
        filters.append(
            or_(
                Purchase.supplier_name.ilike(pattern),
                Purchase.document_number.ilike(pattern),
            )
        )
    if supplier:
        filters.append(func.lower(Purchase.supplier_name) == supplier.lower())
    if supplier_id:
        filters.append(Purchase.supplier_id == supplier_id)
    if status:
        filters.append(Purchase.status == status)
    if document_type:
        filters.append(Purchase.document_type == document_type)
    if date_from:
        filters.append(Purchase.purchase_date >= date_from)
    if date_to:
        filters.append(Purchase.purchase_date <= date_to)
    if created_by_user_id:
        filters.append(Purchase.created_by_user_id == created_by_user_id)
    has_attachment = active_purchase_attachment_exists(tenant_id)
    if attachment_status == "attached":
        filters.append(has_attachment)
    elif attachment_status == "pending":
        filters.append(~has_attachment)
    return filters


class PurchaseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_inventory_items_by_ids(
        self, tenant_id: uuid.UUID, inventory_item_ids: list[uuid.UUID]
    ) -> list[InventoryItem]:
        if not inventory_item_ids:
            return []
        statement = select(InventoryItem).where(
            InventoryItem.tenant_id == tenant_id,
            InventoryItem.id.in_(inventory_item_ids),
        )
        return list(self.db.scalars(statement).all())

    def create(self, purchase: Purchase) -> Purchase:
        self.db.add(purchase)
        self.db.flush()
        return purchase

    def get_by_id(
        self,
        tenant_id: uuid.UUID,
        purchase_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> Purchase | None:
        statement = (
            select(Purchase)
            .where(Purchase.id == purchase_id, Purchase.tenant_id == tenant_id)
            .options(
                selectinload(
                    Purchase.items.and_(PurchaseItem.tenant_id == tenant_id)
                ),
                selectinload(
                    Purchase.created_by_user.and_(User.tenant_id == tenant_id)
                ),
                selectinload(
                    Purchase.cancelled_by_user.and_(User.tenant_id == tenant_id)
                ),
                selectinload(
                    Purchase.received_by_user.and_(User.tenant_id == tenant_id)
                ),
                selectinload(
                    Purchase.reversed_by_user.and_(User.tenant_id == tenant_id)
                ),
                selectinload(Purchase.supplier.and_(Supplier.tenant_id == tenant_id)),
                selectinload(
                    Purchase.attachments.and_(PurchaseAttachment.tenant_id == tenant_id)
                ).selectinload(
                    PurchaseAttachment.uploaded_by_user.and_(User.tenant_id == tenant_id)
                ),
                selectinload(
                    Purchase.attachments.and_(PurchaseAttachment.tenant_id == tenant_id)
                ).selectinload(
                    PurchaseAttachment.replaced_by_user.and_(User.tenant_id == tenant_id)
                ),
                selectinload(
                    Purchase.returns.and_(PurchaseReturn.tenant_id == tenant_id)
                ).selectinload(
                    PurchaseReturn.items.and_(PurchaseReturnItem.tenant_id == tenant_id)
                ),
                selectinload(
                    Purchase.returns.and_(PurchaseReturn.tenant_id == tenant_id)
                ).selectinload(
                    PurchaseReturn.created_by_user.and_(User.tenant_id == tenant_id)
                ),
                selectinload(
                    Purchase.returns.and_(PurchaseReturn.tenant_id == tenant_id)
                ).selectinload(
                    PurchaseReturn.attachments.and_(
                        PurchaseReturnAttachment.tenant_id == tenant_id
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
        supplier: str | None,
        supplier_id: uuid.UUID | None,
        status: str | None,
        document_type: str | None,
        date_from: date | None,
        date_to: date | None,
        created_by_user_id: uuid.UUID | None,
        attachment_status: str | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_direction: str,
    ) -> tuple[list[tuple[Purchase, int, bool, str]], dict]:
        item_count = (
            select(func.count(PurchaseItem.id))
            .where(
                PurchaseItem.purchase_id == Purchase.id,
                PurchaseItem.tenant_id == tenant_id,
            )
            .correlate(Purchase)
            .scalar_subquery()
        )
        has_attachment = active_purchase_attachment_exists(tenant_id)
        purchased_quantity = (
            select(func.coalesce(func.sum(PurchaseItem.quantity), 0))
            .where(
                PurchaseItem.purchase_id == Purchase.id,
                PurchaseItem.tenant_id == tenant_id,
            )
            .correlate(Purchase)
            .scalar_subquery()
        )
        confirmed_returned_quantity = (
            select(func.coalesce(func.sum(PurchaseReturnItem.quantity), 0))
            .join(
                PurchaseReturn,
                (PurchaseReturn.id == PurchaseReturnItem.purchase_return_id)
                & (PurchaseReturn.tenant_id == tenant_id),
            )
            .where(
                PurchaseReturnItem.tenant_id == tenant_id,
                PurchaseReturn.purchase_id == Purchase.id,
                PurchaseReturn.status == "confirmed",
            )
            .correlate(Purchase)
            .scalar_subquery()
        )
        return_status = case(
            (confirmed_returned_quantity <= 0, "none"),
            (
                (purchased_quantity > 0)
                & (confirmed_returned_quantity >= purchased_quantity),
                "full",
            ),
            else_="partial",
        )
        filters = build_purchase_filters(
            tenant_id,
            search=search,
            supplier=supplier,
            supplier_id=supplier_id,
            status=status,
            document_type=document_type,
            date_from=date_from,
            date_to=date_to,
            created_by_user_id=created_by_user_id,
            attachment_status=attachment_status,
        )
        statement = (
            select(
                Purchase,
                item_count.label("item_count"),
                has_attachment.label("has_attachment"),
                return_status.label("return_status"),
            )
            .where(*filters)
            .options(
                selectinload(
                    Purchase.created_by_user.and_(User.tenant_id == tenant_id)
                )
            )
        )
        summary_statement = select(
            func.count(Purchase.id).label("purchase_count"),
            func.coalesce(func.sum(Purchase.subtotal_ars), 0).label("subtotal_ars"),
            func.coalesce(func.sum(Purchase.tax_total_ars), 0).label("tax_total_ars"),
            func.coalesce(func.sum(Purchase.total_ars), 0).label("total_ars"),
        ).where(*filters)

        sort_columns = {
            "purchase_date": Purchase.purchase_date,
            "created_at": Purchase.created_at,
            "total_ars": Purchase.total_ars,
            "supplier_name": func.lower(Purchase.supplier_name),
            "status": Purchase.status,
        }
        order = asc if sort_direction == "asc" else desc
        statement = statement.order_by(order(sort_columns[sort_by]), order(Purchase.id))
        statement = statement.offset((page - 1) * page_size).limit(page_size)
        rows = self.db.execute(statement).all()
        summary = dict(self.db.execute(summary_statement).mappings().one())
        return [
            (row[0], int(row[1] or 0), bool(row[2]), str(row[3])) for row in rows
        ], summary

    def list_creator_options(self, tenant_id: uuid.UUID) -> list[dict]:
        statement = (
            select(User.id, User.full_name, User.email, User.is_active)
            .join(
                Purchase,
                (Purchase.created_by_user_id == User.id)
                & (Purchase.tenant_id == tenant_id),
            )
            .where(User.tenant_id == tenant_id)
            .distinct()
            .order_by(func.lower(User.full_name).asc(), User.id.asc())
        )
        return [dict(row) for row in self.db.execute(statement).mappings().all()]

    def replace_items(self, purchase: Purchase, items: list[PurchaseItem]) -> None:
        purchase.items.clear()
        self.db.flush()
        purchase.items.extend(items)
        self.db.add(purchase)
        self.db.flush()

    def save(self, purchase: Purchase) -> Purchase:
        self.db.add(purchase)
        self.db.flush()
        return purchase

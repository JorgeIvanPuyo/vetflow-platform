from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.purchase_attachment import PurchaseAttachment
from app.models.user import User


class PurchaseAttachmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active(
        self,
        tenant_id: uuid.UUID,
        purchase_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> PurchaseAttachment | None:
        statement = (
            select(PurchaseAttachment)
            .where(
                PurchaseAttachment.tenant_id == tenant_id,
                PurchaseAttachment.purchase_id == purchase_id,
                PurchaseAttachment.is_active.is_(True),
            )
            .options(
                selectinload(
                    PurchaseAttachment.uploaded_by_user.and_(User.tenant_id == tenant_id)
                ),
                selectinload(
                    PurchaseAttachment.replaced_by_user.and_(User.tenant_id == tenant_id)
                ),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def create(self, attachment: PurchaseAttachment) -> PurchaseAttachment:
        self.db.add(attachment)
        self.db.flush()
        return attachment

    def save(self, attachment: PurchaseAttachment) -> PurchaseAttachment:
        self.db.add(attachment)
        self.db.flush()
        return attachment

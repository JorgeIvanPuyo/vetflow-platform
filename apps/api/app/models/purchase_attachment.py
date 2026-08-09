from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class PurchaseAttachment(BaseModel):
    __tablename__ = "purchase_attachments"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_purchase_attachments_size_positive"),
        CheckConstraint("length(sha256) = 64", name="ck_purchase_attachments_sha256_length"),
        Index(
            "uq_purchase_attachments_active_purchase",
            "purchase_id",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active = 1"),
        ),
        Index(
            "ix_purchase_attachments_tenant_purchase",
            "tenant_id",
            "purchase_id",
        ),
        Index(
            "ix_purchase_attachments_tenant_sha256",
            "tenant_id",
            "sha256",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    purchase_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("purchases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    bucket_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    replaced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    replaced_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    purchase: Mapped[Purchase] = relationship("Purchase", back_populates="attachments")
    uploaded_by_user: Mapped[User | None] = relationship(
        "User", foreign_keys=[uploaded_by_user_id]
    )
    replaced_by_user: Mapped[User | None] = relationship(
        "User", foreign_keys=[replaced_by_user_id]
    )

    @property
    def uploaded_by_user_name(self) -> str | None:
        if (
            self.uploaded_by_user is None
            or self.uploaded_by_user.tenant_id != self.tenant_id
        ):
            return None
        return self.uploaded_by_user.full_name

    @property
    def uploaded_by_user_email(self) -> str | None:
        if (
            self.uploaded_by_user is None
            or self.uploaded_by_user.tenant_id != self.tenant_id
        ):
            return None
        return self.uploaded_by_user.email

    @property
    def replaced_by_user_name(self) -> str | None:
        if (
            self.replaced_by_user is None
            or self.replaced_by_user.tenant_id != self.tenant_id
        ):
            return None
        return self.replaced_by_user.full_name

    @property
    def replaced_by_user_email(self) -> str | None:
        if (
            self.replaced_by_user is None
            or self.replaced_by_user.tenant_id != self.tenant_id
        ):
            return None
        return self.replaced_by_user.email

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


PURCHASE_RETURN_STATUSES = ("draft", "confirmed", "cancelled")
PURCHASE_RETURN_DOCUMENT_TYPES = ("credit_note", "return_delivery_note", "other")


class PurchaseReturn(BaseModel):
    __tablename__ = "purchase_returns"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'cancelled')",
            name="ck_purchase_returns_status",
        ),
        CheckConstraint(
            "document_type IS NULL OR document_type IN "
            "('credit_note', 'return_delivery_note', 'other')",
            name="ck_purchase_returns_document_type",
        ),
        CheckConstraint("length(currency) = 3 AND currency = upper(currency)", name="ck_purchase_returns_currency"),
        CheckConstraint(
            "subtotal_ars >= 0 AND tax_total_ars >= 0 AND total_ars >= 0",
            name="ck_purchase_returns_totals_non_negative",
        ),
        Index(
            "ix_purchase_returns_tenant_return_date",
            "tenant_id",
            "return_date",
        ),
        Index(
            "ix_purchase_returns_tenant_status_return_date",
            "tenant_id",
            "status",
            "return_date",
        ),
        Index(
            "ix_purchase_returns_tenant_purchase",
            "tenant_id",
            "purchase_id",
        ),
        Index(
            "ix_purchase_returns_tenant_supplier",
            "tenant_id",
            "supplier_id",
        ),
        Index(
            "ix_purchase_returns_tenant_created_by",
            "tenant_id",
            "created_by_user_id",
        ),
        Index(
            "ix_purchase_returns_tenant_inventory_operation",
            "tenant_id",
            "inventory_operation_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    purchase_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("purchases.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("suppliers.id"), nullable=False, index=True
    )
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier_tax_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    return_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="draft", server_default="draft", index=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    document_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    document_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal_ars: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    tax_total_ars: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    total_ars: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    inventory_operation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="purchase_returns")
    purchase: Mapped[Purchase] = relationship("Purchase", back_populates="returns")
    supplier: Mapped[Supplier] = relationship("Supplier", back_populates="purchase_returns")
    created_by_user: Mapped[User | None] = relationship(
        "User", foreign_keys=[created_by_user_id]
    )
    confirmed_by_user: Mapped[User | None] = relationship(
        "User", foreign_keys=[confirmed_by_user_id]
    )
    cancelled_by_user: Mapped[User | None] = relationship(
        "User", foreign_keys=[cancelled_by_user_id]
    )
    items: Mapped[list[PurchaseReturnItem]] = relationship(
        "PurchaseReturnItem",
        back_populates="purchase_return",
        cascade="all, delete-orphan",
        order_by="PurchaseReturnItem.line_number",
    )
    attachments: Mapped[list[PurchaseReturnAttachment]] = relationship(
        "PurchaseReturnAttachment",
        back_populates="purchase_return",
        cascade="all, delete-orphan",
        order_by="desc(PurchaseReturnAttachment.uploaded_at)",
    )

    @property
    def attachment(self) -> PurchaseReturnAttachment | None:
        return next((item for item in self.attachments if item.is_active), None)

    @property
    def attachment_status(self) -> str:
        return "attached" if self.attachment is not None else "pending"

    @property
    def attachment_history(self) -> list[PurchaseReturnAttachment]:
        return [item for item in self.attachments if not item.is_active]

    @property
    def item_count(self) -> int:
        return len(self.items)

    @staticmethod
    def _same_tenant_user_value(user, tenant_id: uuid.UUID, field: str):
        if user is None or user.tenant_id != tenant_id:
            return None
        return getattr(user, field)

    @property
    def created_by_user_name(self) -> str | None:
        return self._same_tenant_user_value(
            self.created_by_user, self.tenant_id, "full_name"
        )

    @property
    def created_by_user_email(self) -> str | None:
        return self._same_tenant_user_value(
            self.created_by_user, self.tenant_id, "email"
        )

    @property
    def confirmed_by_user_name(self) -> str | None:
        return self._same_tenant_user_value(
            self.confirmed_by_user, self.tenant_id, "full_name"
        )

    @property
    def confirmed_by_user_email(self) -> str | None:
        return self._same_tenant_user_value(
            self.confirmed_by_user, self.tenant_id, "email"
        )

    @property
    def cancelled_by_user_name(self) -> str | None:
        return self._same_tenant_user_value(
            self.cancelled_by_user, self.tenant_id, "full_name"
        )

    @property
    def cancelled_by_user_email(self) -> str | None:
        return self._same_tenant_user_value(
            self.cancelled_by_user, self.tenant_id, "email"
        )


class PurchaseReturnItem(BaseModel):
    __tablename__ = "purchase_return_items"
    __table_args__ = (
        CheckConstraint(
            "line_number > 0", name="ck_purchase_return_items_line_number_positive"
        ),
        CheckConstraint(
            "quantity > 0", name="ck_purchase_return_items_quantity_positive"
        ),
        CheckConstraint(
            "quantity = trunc(quantity)",
            name="ck_purchase_return_items_quantity_integer",
        ),
        CheckConstraint(
            "unit_price_without_tax_ars >= 0",
            name="ck_purchase_return_items_unit_price_non_negative",
        ),
        CheckConstraint(
            "tax_rate_percentage >= 0 AND tax_rate_percentage <= 100",
            name="ck_purchase_return_items_tax_rate_range",
        ),
        CheckConstraint(
            "line_subtotal_ars >= 0 AND line_tax_ars >= 0 AND line_total_ars >= 0",
            name="ck_purchase_return_items_totals_non_negative",
        ),
        UniqueConstraint(
            "purchase_return_id",
            "purchase_item_id",
            name="uq_purchase_return_items_return_purchase_item",
        ),
        UniqueConstraint(
            "purchase_return_id",
            "line_number",
            name="uq_purchase_return_items_return_line_number",
        ),
        Index(
            "ix_purchase_return_items_tenant_return",
            "tenant_id",
            "purchase_return_id",
        ),
        Index(
            "ix_purchase_return_items_tenant_purchase_item",
            "tenant_id",
            "purchase_item_id",
        ),
        Index(
            "ix_purchase_return_items_tenant_inventory_item",
            "tenant_id",
            "inventory_item_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    purchase_return_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("purchase_returns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purchase_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("purchase_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    internal_code_snapshot: Mapped[str] = mapped_column(String(16), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price_without_tax_ars: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )
    tax_rate_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    line_subtotal_ars: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    line_tax_ars: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    line_total_ars: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)

    purchase_return: Mapped[PurchaseReturn] = relationship(
        "PurchaseReturn", back_populates="items"
    )
    purchase_item: Mapped[PurchaseItem] = relationship(
        "PurchaseItem", back_populates="return_items"
    )
    inventory_item: Mapped[InventoryItem] = relationship("InventoryItem")

    @property
    def purchased_quantity(self) -> Decimal:
        return self.purchase_item.quantity

    @property
    def confirmed_returned_quantity(self) -> Decimal:
        return self.purchase_item.confirmed_returned_quantity

    @property
    def returnable_quantity(self) -> Decimal:
        return self.purchase_item.returnable_quantity


class PurchaseReturnAttachment(BaseModel):
    __tablename__ = "purchase_return_attachments"
    __table_args__ = (
        CheckConstraint(
            "size_bytes > 0", name="ck_purchase_return_attachments_size_positive"
        ),
        CheckConstraint(
            "length(sha256) = 64",
            name="ck_purchase_return_attachments_sha256_length",
        ),
        Index(
            "uq_purchase_return_attachments_active_return",
            "purchase_return_id",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active = 1"),
        ),
        Index(
            "ix_purchase_return_attachments_tenant_return",
            "tenant_id",
            "purchase_return_id",
        ),
        Index(
            "ix_purchase_return_attachments_tenant_sha256",
            "tenant_id",
            "sha256",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    purchase_return_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("purchase_returns.id", ondelete="CASCADE"),
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
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    replaced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    replaced_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    purchase_return: Mapped[PurchaseReturn] = relationship(
        "PurchaseReturn", back_populates="attachments"
    )
    uploaded_by_user: Mapped[User | None] = relationship(
        "User", foreign_keys=[uploaded_by_user_id]
    )
    replaced_by_user: Mapped[User | None] = relationship(
        "User", foreign_keys=[replaced_by_user_id]
    )

    def _user_value(self, user, field: str):
        if user is None or user.tenant_id != self.tenant_id:
            return None
        return getattr(user, field)

    @property
    def uploaded_by_user_name(self) -> str | None:
        return self._user_value(self.uploaded_by_user, "full_name")

    @property
    def uploaded_by_user_email(self) -> str | None:
        return self._user_value(self.uploaded_by_user, "email")

    @property
    def replaced_by_user_name(self) -> str | None:
        return self._user_value(self.replaced_by_user, "full_name")

    @property
    def replaced_by_user_email(self) -> str | None:
        return self._user_value(self.replaced_by_user, "email")

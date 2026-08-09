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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


PURCHASE_STATUSES = (
    "draft",
    "cancelled",
    "received",
    "partially_received",
    "returned",
    "reversed",
)
PURCHASE_DOCUMENT_TYPES = ("invoice", "receipt", "ticket", "delivery_note", "other")


class Purchase(BaseModel):
    __tablename__ = "purchases"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'cancelled', 'received', 'partially_received', 'returned', 'reversed')",
            name="ck_purchases_status",
        ),
        CheckConstraint("currency = 'ARS'", name="ck_purchases_currency"),
        CheckConstraint("subtotal_ars >= 0", name="ck_purchases_subtotal_non_negative"),
        CheckConstraint("tax_total_ars >= 0", name="ck_purchases_tax_total_non_negative"),
        CheckConstraint("total_ars >= 0", name="ck_purchases_total_non_negative"),
        Index("ix_purchases_tenant_purchase_date", "tenant_id", "purchase_date"),
        Index(
            "ix_purchases_tenant_status_purchase_date",
            "tenant_id",
            "status",
            "purchase_date",
        ),
        Index("ix_purchases_tenant_supplier", "tenant_id", "supplier_name"),
        Index("ix_purchases_tenant_supplier_id", "tenant_id", "supplier_id"),
        Index("ix_purchases_tenant_document", "tenant_id", "document_number"),
        Index("ix_purchases_tenant_created_by", "tenant_id", "created_by_user_id"),
        Index(
            "ix_purchases_tenant_inventory_operation",
            "tenant_id",
            "inventory_operation_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("suppliers.id"), nullable=False, index=True
    )
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier_tax_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    document_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    document_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="ARS", server_default="ARS"
    )
    subtotal_ars: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    tax_total_ars: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    total_ars: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="draft", server_default="draft", index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    inventory_operation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    reversal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reversal_operation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    reversal_cost_warning: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="purchases")
    supplier: Mapped[Supplier] = relationship("Supplier", back_populates="purchases")
    created_by_user: Mapped[User | None] = relationship(
        "User", foreign_keys=[created_by_user_id]
    )
    cancelled_by_user: Mapped[User | None] = relationship(
        "User", foreign_keys=[cancelled_by_user_id]
    )
    received_by_user: Mapped[User | None] = relationship(
        "User", foreign_keys=[received_by_user_id]
    )
    reversed_by_user: Mapped[User | None] = relationship(
        "User", foreign_keys=[reversed_by_user_id]
    )
    items: Mapped[list[PurchaseItem]] = relationship(
        "PurchaseItem",
        back_populates="purchase",
        cascade="all, delete-orphan",
        order_by="PurchaseItem.line_number",
    )
    attachments: Mapped[list[PurchaseAttachment]] = relationship(
        "PurchaseAttachment",
        back_populates="purchase",
        cascade="all, delete-orphan",
        order_by="desc(PurchaseAttachment.uploaded_at)",
    )

    @property
    def attachment(self) -> PurchaseAttachment | None:
        return next((attachment for attachment in self.attachments if attachment.is_active), None)

    @property
    def attachment_status(self) -> str:
        return "attached" if self.attachment is not None else "pending"

    @property
    def attachment_history(self) -> list[PurchaseAttachment]:
        return [attachment for attachment in self.attachments if not attachment.is_active]

    @property
    def created_by_user_name(self) -> str | None:
        if self.created_by_user is None or self.created_by_user.tenant_id != self.tenant_id:
            return None
        return self.created_by_user.full_name

    @property
    def created_by_user_email(self) -> str | None:
        if self.created_by_user is None or self.created_by_user.tenant_id != self.tenant_id:
            return None
        return self.created_by_user.email

    @property
    def cancelled_by_user_name(self) -> str | None:
        if self.cancelled_by_user is None or self.cancelled_by_user.tenant_id != self.tenant_id:
            return None
        return self.cancelled_by_user.full_name

    @property
    def cancelled_by_user_email(self) -> str | None:
        if self.cancelled_by_user is None or self.cancelled_by_user.tenant_id != self.tenant_id:
            return None
        return self.cancelled_by_user.email

    @property
    def received_by_user_name(self) -> str | None:
        if self.received_by_user is None or self.received_by_user.tenant_id != self.tenant_id:
            return None
        return self.received_by_user.full_name

    @property
    def received_by_user_email(self) -> str | None:
        if self.received_by_user is None or self.received_by_user.tenant_id != self.tenant_id:
            return None
        return self.received_by_user.email

    @property
    def reversed_by_user_name(self) -> str | None:
        if self.reversed_by_user is None or self.reversed_by_user.tenant_id != self.tenant_id:
            return None
        return self.reversed_by_user.full_name

    @property
    def reversed_by_user_email(self) -> str | None:
        if self.reversed_by_user is None or self.reversed_by_user.tenant_id != self.tenant_id:
            return None
        return self.reversed_by_user.email

    @property
    def reversal_warnings(self) -> list[str]:
        if not self.reversal_cost_warning:
            return []
        return [
            "El stock se revirtió, pero se conservó un costo de catálogo modificado posteriormente."
        ]


class PurchaseItem(BaseModel):
    __tablename__ = "purchase_items"
    __table_args__ = (
        CheckConstraint("line_number > 0", name="ck_purchase_items_line_number_positive"),
        CheckConstraint("quantity > 0", name="ck_purchase_items_quantity_positive"),
        CheckConstraint(
            "quantity = trunc(quantity)",
            name="ck_purchase_items_quantity_integer",
        ),
        CheckConstraint(
            "unit_price_without_tax_ars >= 0",
            name="ck_purchase_items_unit_price_non_negative",
        ),
        CheckConstraint(
            "tax_rate_percentage >= 0 AND tax_rate_percentage <= 100",
            name="ck_purchase_items_tax_rate_range",
        ),
        CheckConstraint(
            "unit_price_with_tax_ars >= 0 AND line_subtotal_ars >= 0 "
            "AND line_tax_ars >= 0 AND line_total_ars >= 0",
            name="ck_purchase_items_calculated_amounts_non_negative",
        ),
        UniqueConstraint(
            "purchase_id", "line_number", name="uq_purchase_items_purchase_line_number"
        ),
        UniqueConstraint(
            "purchase_id", "inventory_item_id", name="uq_purchase_items_purchase_inventory_item"
        ),
        Index(
            "ix_purchase_items_tenant_inventory_item", "tenant_id", "inventory_item_id"
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    purchase_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False, index=True
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    internal_code_snapshot: Mapped[str] = mapped_column(String(16), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price_without_tax_ars: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tax_rate_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("21"), server_default="21"
    )
    unit_price_with_tax_ars: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    line_subtotal_ars: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    line_tax_ars: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    line_total_ars: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    previous_purchase_price_ars: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    previous_purchase_tax_rate_percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    purchase: Mapped[Purchase] = relationship("Purchase", back_populates="items")
    inventory_item: Mapped[InventoryItem] = relationship("InventoryItem")

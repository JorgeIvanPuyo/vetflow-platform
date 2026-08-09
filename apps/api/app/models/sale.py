from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Sale(BaseModel):
    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'cancelled', 'confirmed', 'invoiced', 'reversed')", name="ck_sales_status"),
        CheckConstraint("currency = 'ARS'", name="ck_sales_currency"),
        CheckConstraint("subtotal_ars >= 0 AND discount_total_ars >= 0 AND total_ars >= 0", name="ck_sales_totals_non_negative"),
        Index("ix_sales_tenant_sale_date", "tenant_id", "sale_date"),
        Index("ix_sales_tenant_status_sale_date", "tenant_id", "status", "sale_date"),
        Index("ix_sales_tenant_owner", "tenant_id", "owner_id"),
        Index("ix_sales_tenant_patient", "tenant_id", "patient_id"),
        Index("ix_sales_tenant_created_by", "tenant_id", "created_by_user_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("owners.id", ondelete="SET NULL"), nullable=True, index=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True)
    owner_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_document_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    owner_email_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    patient_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    patient_species_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="ARS", server_default="ARS")
    subtotal_ars: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"), server_default="0")
    discount_total_ars: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"), server_default="0")
    total_ars: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"), server_default="0")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", server_default="draft", index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="sales")
    owner: Mapped[Owner | None] = relationship("Owner", foreign_keys=[owner_id])
    patient: Mapped[Patient | None] = relationship("Patient", foreign_keys=[patient_id])
    created_by_user: Mapped[User | None] = relationship("User", foreign_keys=[created_by_user_id])
    cancelled_by_user: Mapped[User | None] = relationship("User", foreign_keys=[cancelled_by_user_id])
    items: Mapped[list[SaleItem]] = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan", order_by="SaleItem.line_order")

    @staticmethod
    def _user_value(user, tenant_id: uuid.UUID, field: str):
        return getattr(user, field) if user is not None and user.tenant_id == tenant_id else None

    @property
    def created_by_user_name(self) -> str | None:
        return self._user_value(self.created_by_user, self.tenant_id, "full_name")

    @property
    def created_by_user_email(self) -> str | None:
        return self._user_value(self.created_by_user, self.tenant_id, "email")

    @property
    def cancelled_by_user_name(self) -> str | None:
        return self._user_value(self.cancelled_by_user, self.tenant_id, "full_name")

    @property
    def cancelled_by_user_email(self) -> str | None:
        return self._user_value(self.cancelled_by_user, self.tenant_id, "email")

    @property
    def item_count(self) -> int:
        return len(self.items)


class SaleItem(BaseModel):
    __tablename__ = "sale_items"
    __table_args__ = (
        CheckConstraint("line_type IN ('product', 'service')", name="ck_sale_items_line_type"),
        CheckConstraint("quantity > 0", name="ck_sale_items_quantity_positive"),
        CheckConstraint("quantity = trunc(quantity)", name="ck_sale_items_quantity_integer"),
        CheckConstraint("unit_price_ars >= 0", name="ck_sale_items_unit_price_non_negative"),
        CheckConstraint("discount_percentage >= 0 AND discount_percentage <= 100", name="ck_sale_items_discount_range"),
        CheckConstraint("line_subtotal_ars >= 0 AND line_discount_ars >= 0 AND line_total_ars >= 0", name="ck_sale_items_totals_non_negative"),
        CheckConstraint("(line_type = 'product' AND inventory_item_id IS NOT NULL) OR (line_type = 'service' AND inventory_item_id IS NULL)", name="ck_sale_items_product_reference"),
        UniqueConstraint("sale_id", "line_order", name="uq_sale_items_sale_line_order"),
        Index("ix_sale_items_tenant_inventory_item", "tenant_id", "inventory_item_id"),
        Index("ix_sale_items_tenant_line_type", "tenant_id", "line_type"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    sale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True)
    line_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=True, index=True)
    service_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    description_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    internal_code_snapshot: Mapped[str | None] = mapped_column(String(32), nullable=True)
    unit_snapshot: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price_ars: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0"), server_default="0")
    line_subtotal_ars: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    line_discount_ars: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    line_total_ars: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    line_order: Mapped[int] = mapped_column(Integer, nullable=False)

    sale: Mapped[Sale] = relationship("Sale", back_populates="items")
    inventory_item: Mapped[InventoryItem | None] = relationship("InventoryItem")

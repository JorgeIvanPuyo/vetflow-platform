from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


PAYMENT_METHOD_TYPES = (
    "cash",
    "bank_transfer",
    "debit_card",
    "credit_card",
    "digital_wallet",
    "other",
)


class PaymentMethod(BaseModel):
    __tablename__ = "payment_methods"
    __table_args__ = (
        CheckConstraint(
            "type IN ('cash', 'bank_transfer', 'debit_card', 'credit_card', 'digital_wallet', 'other')",
            name="ck_payment_methods_type",
        ),
        CheckConstraint("sort_order >= 0", name="ck_payment_methods_sort_order"),
        Index(
            "uq_payment_methods_active_label",
            "tenant_id",
            "normalized_label",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active = 1"),
        ),
        Index("ix_payment_methods_tenant_active_order", "tenant_id", "is_active", "sort_order"),
        Index("ix_payment_methods_tenant_type", "tenant_id", "type"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_label: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    payments: Mapped[list[SalePayment]] = relationship("SalePayment", back_populates="payment_method")


class SalePayment(BaseModel):
    __tablename__ = "sale_payments"
    __table_args__ = (
        CheckConstraint("amount_ars > 0", name="ck_sale_payments_amount_positive"),
        CheckConstraint(
            "payment_method_type_snapshot IN ('cash', 'bank_transfer', 'debit_card', 'credit_card', 'digital_wallet', 'other')",
            name="ck_sale_payments_method_type",
        ),
        CheckConstraint(
            "(is_active AND voided_at IS NULL AND voided_by_user_id IS NULL AND void_reason IS NULL) OR "
            "(NOT is_active AND voided_at IS NOT NULL AND void_reason IS NOT NULL)",
            name="ck_sale_payments_void_state",
        ),
        Index("ix_sale_payments_tenant_sale", "tenant_id", "sale_id"),
        Index("ix_sale_payments_tenant_method", "tenant_id", "payment_method_id"),
        Index("ix_sale_payments_tenant_received", "tenant_id", "received_at"),
        Index("ix_sale_payments_tenant_creator", "tenant_id", "created_by_user_id"),
        Index(
            "ix_sale_payments_tenant_sale_active",
            "tenant_id",
            "sale_id",
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active = 1"),
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    sale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sales.id", ondelete="RESTRICT"), nullable=False, index=True)
    payment_method_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("payment_methods.id", ondelete="RESTRICT"), nullable=False, index=True)
    payment_method_label_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    payment_method_type_snapshot: Mapped[str] = mapped_column(String(30), nullable=False)
    amount_ars: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    sale: Mapped[Sale] = relationship("Sale", back_populates="payments")
    payment_method: Mapped[PaymentMethod] = relationship("PaymentMethod", back_populates="payments")
    created_by_user: Mapped[User | None] = relationship("User", foreign_keys=[created_by_user_id])
    voided_by_user: Mapped[User | None] = relationship("User", foreign_keys=[voided_by_user_id])

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
    def voided_by_user_name(self) -> str | None:
        return self._user_value(self.voided_by_user, self.tenant_id, "full_name")

    @property
    def voided_by_user_email(self) -> str | None:
        return self._user_value(self.voided_by_user, self.tenant_id, "email")

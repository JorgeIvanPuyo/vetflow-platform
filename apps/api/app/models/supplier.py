from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Supplier(BaseModel):
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "tax_id", name="uq_suppliers_tenant_tax_id"),
        Index("ix_suppliers_tenant_active_name", "tenant_id", "is_active", "name"),
        Index("ix_suppliers_tenant_updated_at", "tenant_id", "updated_at"),
        Index(
            "ux_suppliers_tenant_normalized_name_active",
            "tenant_id",
            "normalized_name",
            unique=True,
            postgresql_where=text("is_active IS TRUE"),
            sqlite_where=text("is_active = 1"),
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tax_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="suppliers")
    created_by_user: Mapped[User | None] = relationship("User")
    purchases: Mapped[list[Purchase]] = relationship("Purchase", back_populates="supplier")
    purchase_returns: Mapped[list[PurchaseReturn]] = relationship(
        "PurchaseReturn",
        back_populates="supplier",
    )

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

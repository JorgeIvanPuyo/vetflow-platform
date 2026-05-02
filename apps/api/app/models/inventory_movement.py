from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class InventoryMovement(BaseModel):
    __tablename__ = "inventory_movements"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("inventory_items.id"),
        nullable=False,
        index=True,
    )
    movement_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_cost_ars: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_cost_ars: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    unit_sale_price_ars: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    total_sale_price_ars: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    supplier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_patient_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("patients.id"),
        nullable=True,
        index=True,
    )
    related_consultation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("consultations.id"),
        nullable=True,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="inventory_movements")
    inventory_item: Mapped[InventoryItem] = relationship(
        "InventoryItem",
        back_populates="movements",
    )
    related_patient: Mapped[Patient | None] = relationship("Patient")
    related_consultation: Mapped[Consultation | None] = relationship("Consultation")
    created_by_user: Mapped[User | None] = relationship("User")

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

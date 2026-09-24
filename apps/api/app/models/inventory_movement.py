from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class InventoryMovement(BaseModel):
    __tablename__ = "inventory_movements"
    __table_args__ = (
        UniqueConstraint(
            "reverses_movement_id",
            name="uq_inventory_movements_reverses_movement_id",
        ),
    )

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
    stock_before: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    stock_after: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    operation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    reverses_movement_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("inventory_movements.id"),
        nullable=True,
    )
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
    reverses_movement: Mapped[InventoryMovement | None] = relationship(
        "InventoryMovement",
        remote_side="InventoryMovement.id",
        foreign_keys=[reverses_movement_id],
        back_populates="reversed_by_movement",
    )
    reversed_by_movement: Mapped[InventoryMovement | None] = relationship(
        "InventoryMovement",
        foreign_keys="[InventoryMovement.reverses_movement_id]",
        back_populates="reverses_movement",
        uselist=False,
    )

    @property
    def reversed_by_movement_id(self) -> uuid.UUID | None:
        if self.reversed_by_movement is None:
            return None
        if self.reversed_by_movement.tenant_id != self.tenant_id:
            return None
        return self.reversed_by_movement.id

    @property
    def reversal_status(self) -> str:
        if self.movement_type == "reversal":
            return "reversal"
        if self.reversed_by_movement_id is not None:
            return "reversed"
        return "active"

    @property
    def inventory_item_name(self) -> str | None:
        if self.inventory_item is None or self.inventory_item.tenant_id != self.tenant_id:
            return None
        return self.inventory_item.name

    @property
    def inventory_item_internal_code(self) -> str | None:
        if self.inventory_item is None or self.inventory_item.tenant_id != self.tenant_id:
            return None
        return self.inventory_item.internal_code

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

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class InventoryBulkOperation(BaseModel):
    __tablename__ = "inventory_bulk_operations"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    operation_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    selection_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    filters_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    request_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    selected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    affected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    excluded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reversed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflict_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    reversal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list[InventoryBulkOperationItem]] = relationship(
        "InventoryBulkOperationItem",
        back_populates="operation",
        order_by="InventoryBulkOperationItem.created_at",
    )
    created_by_user: Mapped[User | None] = relationship("User", foreign_keys=[created_by_user_id])
    reversed_by_user: Mapped[User | None] = relationship("User", foreign_keys=[reversed_by_user_id])

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
    def reversed_by_user_name(self) -> str | None:
        if self.reversed_by_user is None or self.reversed_by_user.tenant_id != self.tenant_id:
            return None
        return self.reversed_by_user.full_name

    @property
    def reversed_by_user_email(self) -> str | None:
        if self.reversed_by_user is None or self.reversed_by_user.tenant_id != self.tenant_id:
            return None
        return self.reversed_by_user.email


class InventoryBulkOperationItem(BaseModel):
    __tablename__ = "inventory_bulk_operation_items"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    operation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("inventory_bulk_operations.id"),
        nullable=False,
        index=True,
    )
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("inventory_items.id"),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(String(80), nullable=False)
    old_value_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    product_updated_at_snapshot: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    reverted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    operation: Mapped[InventoryBulkOperation] = relationship(
        "InventoryBulkOperation",
        back_populates="items",
    )
    inventory_item: Mapped[InventoryItem] = relationship("InventoryItem")

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

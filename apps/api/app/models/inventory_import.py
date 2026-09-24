from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class InventoryImport(BaseModel):
    __tablename__ = "inventory_imports"

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
    mode: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    operation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    result_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rows: Mapped[list[InventoryImportRow]] = relationship(
        "InventoryImportRow",
        back_populates="inventory_import",
        order_by="InventoryImportRow.row_number",
    )
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


class InventoryImportRow(BaseModel):
    __tablename__ = "inventory_import_rows"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("inventory_imports.id"),
        nullable=False,
        index=True,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    normalized_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    existing_inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("inventory_items.id"),
        nullable=True,
        index=True,
    )
    match_type: Mapped[str] = mapped_column(String(50), nullable=False)
    proposed_action: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    errors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    product_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    changed_fields: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    stock_current: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    stock_target: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    stock_delta: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    expected_movement_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    inventory_import: Mapped[InventoryImport] = relationship(
        "InventoryImport",
        back_populates="rows",
    )
    existing_inventory_item: Mapped[InventoryItem | None] = relationship("InventoryItem")

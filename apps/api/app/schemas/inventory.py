import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


InventoryCategory = Literal["medication", "vaccine", "supply", "food", "other"]
InventoryUnit = Literal[
    "unit",
    "tablet",
    "capsule",
    "ampoule",
    "dose",
    "pipette",
    "bottle",
    "vial",
    "syringe",
    "ml",
    "liter",
    "gram",
    "kg",
    "pair",
    "box",
    "package",
    "other",
]
InventoryStatusFilter = Literal[
    "low_stock",
    "expiring_soon",
    "expired",
    "active",
    "inactive",
]
InventorySortBy = Literal["name", "current_stock", "expiration_date", "created_at", "updated_at"]
SortOrder = Literal["asc", "desc"]
InventoryMovementType = Literal["entry", "exit", "adjustment"]
InventoryExitReason = Literal[
    "sale",
    "consultation_use",
    "inventory_adjustment",
    "expired_discard",
    "damaged",
    "other",
]


class InventoryItemBase(BaseModel):
    name: str
    category: InventoryCategory
    subcategory: str | None = None
    unit: InventoryUnit
    supplier: str | None = None
    lot_number: str | None = None
    expiration_date: date | None = None
    current_stock: Decimal = Field(default=Decimal("0"), ge=0)
    minimum_stock: Decimal = Field(default=Decimal("0"), ge=0)
    purchase_price_ars: Decimal | None = Field(default=None, ge=0)
    profit_margin_percentage: Decimal = Field(default=Decimal("35"), ge=0)
    sale_price_ars: Decimal | None = Field(default=None, ge=0)
    round_sale_price: bool = False
    notes: str | None = None
    is_active: bool = True


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    name: str | None = None
    category: InventoryCategory | None = None
    subcategory: str | None = None
    unit: InventoryUnit | None = None
    supplier: str | None = None
    lot_number: str | None = None
    expiration_date: date | None = None
    current_stock: Decimal | None = Field(default=None, ge=0)
    minimum_stock: Decimal | None = Field(default=None, ge=0)
    purchase_price_ars: Decimal | None = Field(default=None, ge=0)
    profit_margin_percentage: Decimal | None = Field(default=None, ge=0)
    sale_price_ars: Decimal | None = Field(default=None, ge=0)
    round_sale_price: bool | None = None
    notes: str | None = None
    is_active: bool | None = None


class InventoryItemRead(InventoryItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    created_by_user_id: uuid.UUID | None = None
    is_low_stock: bool
    is_expiring_soon: bool
    is_expired: bool
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_by_user_id")
    def serialize_created_by_user_id(
        self,
        value: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if self.created_by_user_name or self.created_by_user_email:
            return value
        return None


class InventorySummaryRead(BaseModel):
    total_items: int
    low_stock_count: int
    expiring_soon_count: int
    expired_count: int


class InventoryMovementEntryCreate(BaseModel):
    quantity: Decimal = Field(gt=0)
    total_cost_ars: Decimal | None = Field(default=None, ge=0)
    unit_cost_ars: Decimal | None = Field(default=None, ge=0)
    supplier: str | None = None
    notes: str | None = None


class InventoryMovementExitCreate(BaseModel):
    quantity: Decimal = Field(gt=0)
    reason: InventoryExitReason = "other"
    unit_sale_price_ars: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None
    related_patient_id: uuid.UUID | None = None
    related_consultation_id: uuid.UUID | None = None


class InventoryMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    inventory_item_id: uuid.UUID
    movement_type: InventoryMovementType
    reason: str | None = None
    quantity: Decimal
    unit_cost_ars: Decimal | None = None
    total_cost_ars: Decimal | None = None
    unit_sale_price_ars: Decimal | None = None
    total_sale_price_ars: Decimal | None = None
    supplier: str | None = None
    notes: str | None = None
    related_patient_id: uuid.UUID | None = None
    related_consultation_id: uuid.UUID | None = None
    created_by_user_id: uuid.UUID | None = None
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    created_at: datetime

    @field_serializer("created_by_user_id")
    def serialize_created_by_user_id(
        self,
        value: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if self.created_by_user_name or self.created_by_user_email:
            return value
        return None

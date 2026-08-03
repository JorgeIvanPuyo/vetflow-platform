import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


InventoryCategory = Literal["medication", "vaccine", "supply", "food", "accessory", "other"]
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
InventoryStockStatus = Literal["in_stock", "low_stock", "out_of_stock", "negative"]
InventorySortBy = Literal[
    "name",
    "internal_code",
    "current_stock",
    "sale_price_ars",
    "updated_at",
]
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


class InventoryItemWriteBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    category: InventoryCategory
    subcategory: str | None = Field(default=None, max_length=100)
    brand: str | None = Field(default=None, max_length=150)
    unit: InventoryUnit
    supplier: str | None = Field(default=None, max_length=255)
    lot_number: str | None = Field(default=None, max_length=120)
    expiration_date: date | None = None
    minimum_stock: Decimal = Field(default=Decimal("0"), ge=0)
    purchase_price_ars: Decimal | None = Field(default=None, ge=0)
    purchase_tax_rate_percentage: Decimal = Field(
        default=Decimal("21"),
        ge=0,
        le=100,
    )
    profit_margin_percentage: Decimal = Field(default=Decimal("35"), ge=0)
    sale_price_ars: Decimal | None = Field(default=None, ge=0)
    sale_tax_rate_percentage: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        le=100,
    )
    round_sale_price: bool = False
    notes: str | None = None
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def strip_required_string(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("String should have at least 1 character")
        return value

    @field_validator("subcategory", "brand", "supplier", "lot_number", "notes", mode="before")
    @classmethod
    def strip_optional_string(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        value = value.strip()
        return value or None


class InventoryItemCreate(InventoryItemWriteBase):
    pass


class InventoryItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: InventoryCategory | None = None
    subcategory: str | None = Field(default=None, max_length=100)
    brand: str | None = Field(default=None, max_length=150)
    unit: InventoryUnit | None = None
    supplier: str | None = Field(default=None, max_length=255)
    lot_number: str | None = Field(default=None, max_length=120)
    expiration_date: date | None = None
    minimum_stock: Decimal | None = Field(default=None, ge=0)
    purchase_price_ars: Decimal | None = Field(default=None, ge=0)
    purchase_tax_rate_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    profit_margin_percentage: Decimal | None = Field(default=None, ge=0)
    sale_price_ars: Decimal | None = Field(default=None, ge=0)
    sale_tax_rate_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    round_sale_price: bool | None = None
    notes: str | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_optional_required_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("String should have at least 1 character")
        return value

    @field_validator("subcategory", "brand", "supplier", "lot_number", "notes", mode="before")
    @classmethod
    def strip_optional_string(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        value = value.strip()
        return value or None


class InventoryItemRead(InventoryItemWriteBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    internal_code: str
    current_stock: Decimal
    created_by_user_id: uuid.UUID | None = None
    purchase_tax_amount_ars: Decimal | None = None
    purchase_price_with_tax_ars: Decimal | None = None
    sale_tax_amount_ars: Decimal | None = None
    sale_price_with_tax_ars: Decimal | None = None
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


class InventoryFilterOptionsRead(BaseModel):
    brands: list[str]
    suppliers: list[str]


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

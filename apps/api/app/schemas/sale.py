import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from app.schemas.sale_fiscal import FiscalStatus, SaleFiscalDocumentRead
from app.schemas.payment import PaymentStatus, SalePaymentRead


SaleStatus = Literal["draft", "confirmed", "cancelled", "reversed"]
SaleLineType = Literal["product", "service"]
SaleSortBy = Literal["sale_date", "created_at", "total_ars", "status"]
SaleSortDirection = Literal["asc", "desc"]


class SaleProductItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    line_type: Literal["product"]
    inventory_item_id: uuid.UUID
    quantity: Decimal = Field(gt=0, multiple_of=Decimal("1"))
    unit_price_ars: Decimal | None = Field(default=None, ge=0)
    discount_percentage: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class SaleServiceItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    line_type: Literal["service"]
    service_id: uuid.UUID | None = None
    description: str = Field(min_length=1, max_length=255)
    quantity: Decimal = Field(gt=0, multiple_of=Decimal("1"))
    unit_price_ars: Decimal = Field(ge=0)
    discount_percentage: Decimal = Field(default=Decimal("0"), ge=0, le=100)

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("String should have at least 1 character")
        return value


SaleItemInput = Annotated[SaleProductItemInput | SaleServiceItemInput, Field(discriminator="line_type")]


class SaleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_id: uuid.UUID | None = None
    patient_id: uuid.UUID | None = None
    sale_date: date
    notes: str | None = Field(default=None, max_length=2000)
    items: list[SaleItemInput] = Field(min_length=1, max_length=200)

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value):
        return value.strip() or None if isinstance(value, str) else value


class SaleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_id: uuid.UUID | None = None
    patient_id: uuid.UUID | None = None
    sale_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    items: list[SaleItemInput] | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value):
        return value.strip() or None if isinstance(value, str) else value

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for field_name in ("sale_date", "items"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class SaleCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("String should have at least 1 character")
        return value


class SaleConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: Literal[True]


class SaleReverse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("String should have at least 1 character")
        return value


class SaleItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    line_type: SaleLineType
    inventory_item_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    description_snapshot: str
    internal_code_snapshot: str | None = None
    unit_snapshot: str
    quantity: Decimal
    unit_price_ars: Decimal
    discount_percentage: Decimal
    line_subtotal_ars: Decimal
    line_discount_ars: Decimal
    line_total_ars: Decimal
    line_order: int
    created_at: datetime
    updated_at: datetime


class SaleSummaryRead(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID | None = None
    patient_id: uuid.UUID | None = None
    owner_name_snapshot: str | None = None
    patient_name_snapshot: str | None = None
    sale_date: date
    currency: Literal["USD", "ARS"]
    subtotal_ars: Decimal
    discount_total_ars: Decimal
    total_ars: Decimal
    status: SaleStatus
    fiscal_status: FiscalStatus | None = None
    paid_total_ars: Decimal
    balance_due_ars: Decimal
    payment_status: PaymentStatus | None = None
    payment_requires_attention: bool = False
    item_count: int
    created_by_user_id: uuid.UUID | None = None
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_by_user_id")
    def serialize_created_by(self, value: uuid.UUID | None) -> uuid.UUID | None:
        return value if self.created_by_user_name or self.created_by_user_email else None


class SaleDetailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    owner_id: uuid.UUID | None = None
    patient_id: uuid.UUID | None = None
    owner_name_snapshot: str | None = None
    owner_document_snapshot: str | None = None
    owner_email_snapshot: str | None = None
    patient_name_snapshot: str | None = None
    patient_species_snapshot: str | None = None
    sale_date: date
    currency: Literal["USD", "ARS"]
    subtotal_ars: Decimal
    discount_total_ars: Decimal
    total_ars: Decimal
    notes: str | None = None
    status: SaleStatus
    fiscal_status: FiscalStatus | None = None
    fiscal_document: SaleFiscalDocumentRead | None = None
    paid_total_ars: Decimal
    balance_due_ars: Decimal
    payment_status: PaymentStatus | None = None
    payment_requires_attention: bool = False
    payments: list[SalePaymentRead]
    created_by_user_id: uuid.UUID | None = None
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    cancelled_at: datetime | None = None
    cancelled_by_user_id: uuid.UUID | None = None
    cancelled_by_user_name: str | None = None
    cancelled_by_user_email: str | None = None
    cancellation_reason: str | None = None
    confirmed_at: datetime | None = None
    confirmed_by_user_id: uuid.UUID | None = None
    confirmed_by_user_name: str | None = None
    confirmed_by_user_email: str | None = None
    inventory_operation_id: uuid.UUID | None = None
    reversed_at: datetime | None = None
    reversed_by_user_id: uuid.UUID | None = None
    reversed_by_user_name: str | None = None
    reversed_by_user_email: str | None = None
    reversal_reason: str | None = None
    reversal_operation_id: uuid.UUID | None = None
    items: list[SaleItemRead]
    created_at: datetime
    updated_at: datetime

    @field_serializer(
        "created_by_user_id",
        "cancelled_by_user_id",
        "confirmed_by_user_id",
        "reversed_by_user_id",
    )
    def serialize_user_id(self, value: uuid.UUID | None, info) -> uuid.UUID | None:
        prefix = info.field_name.removesuffix("_id")
        return value if getattr(self, f"{prefix}_name") or getattr(self, f"{prefix}_email") else None

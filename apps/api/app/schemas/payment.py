import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


PaymentMethodType = Literal["cash", "bank_transfer", "debit_card", "credit_card", "digital_wallet", "other"]
PaymentStatus = Literal["unpaid", "partial", "paid", "requires_attention"]


def _trim(value):
    return value.strip() or None if isinstance(value, str) else value


class PaymentMethodCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=120)
    type: PaymentMethodType
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=999999)

    @field_validator("label", mode="before")
    @classmethod
    def normalize_label(cls, value):
        return _trim(value)


class PaymentMethodUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str | None = Field(default=None, min_length=1, max_length=120)
    type: PaymentMethodType | None = None
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=999999)

    @field_validator("label", mode="before")
    @classmethod
    def normalize_label(cls, value):
        return _trim(value)


class PaymentMethodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    label: str
    type: PaymentMethodType
    is_active: bool
    sort_order: int
    has_payments: bool = False
    created_at: datetime
    updated_at: datetime


class SalePaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payment_method_id: uuid.UUID
    amount_ars: Decimal = Field(gt=0, decimal_places=2, max_digits=16)
    received_at: datetime
    reference: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("reference", "notes", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        return _trim(value)


class SalePaymentVoid(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value):
        return _trim(value)


class SalePaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sale_id: uuid.UUID
    payment_method_id: uuid.UUID
    payment_method_label_snapshot: str
    payment_method_type_snapshot: PaymentMethodType
    amount_ars: Decimal
    received_at: datetime
    reference: str | None = None
    notes: str | None = None
    created_by_user_id: uuid.UUID | None = None
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    is_active: bool
    voided_at: datetime | None = None
    voided_by_user_id: uuid.UUID | None = None
    voided_by_user_name: str | None = None
    voided_by_user_email: str | None = None
    void_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_by_user_id", "voided_by_user_id")
    def serialize_user_id(self, value: uuid.UUID | None, info) -> uuid.UUID | None:
        prefix = info.field_name.removesuffix("_id")
        return value if getattr(self, f"{prefix}_name") or getattr(self, f"{prefix}_email") else None


class SalePaymentSummary(BaseModel):
    paid_total_ars: Decimal
    balance_due_ars: Decimal
    payment_status: PaymentStatus | None = None
    payment_requires_attention: bool = False

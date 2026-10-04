import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_serializer

from app.schemas.payment import PaymentStatus


class ReceivableSaleRead(BaseModel):
    sale_id: uuid.UUID
    sale_date: date
    confirmed_at: datetime
    patient_id: uuid.UUID | None
    patient_name_snapshot: str | None
    currency: Literal["USD", "ARS"]
    total_ars: Decimal
    paid_total_ars: Decimal
    balance_due_ars: Decimal
    payment_status: PaymentStatus

    @field_serializer("total_ars", "paid_total_ars", "balance_due_ars", when_used="json")
    def serialize_money(self, value: Decimal) -> str:
        return format(value, ".2f")


class OwnerReceivablesRead(BaseModel):
    owner_id: uuid.UUID
    tracking_configured: bool
    tracking_started_at: datetime | None
    currency: Literal["USD", "ARS"] | None
    locale: str | None
    total_outstanding_ars: Decimal
    open_sales_count: int
    sales: list[ReceivableSaleRead]

    @field_serializer("total_outstanding_ars", when_used="json")
    def serialize_money(self, value: Decimal) -> str:
        return format(value, ".2f")


class ReceivablesActivityEventRead(BaseModel):
    event_id: str
    type: Literal["sale_confirmed", "payment_recorded", "payment_cancelled", "sale_reversed"]
    occurred_at: datetime
    sale_id: uuid.UUID
    sale_date: date
    patient_id: uuid.UUID | None
    patient_name_snapshot: str | None
    currency: Literal["USD", "ARS"]
    payment_id: uuid.UUID | None
    amount_ars: Decimal | None
    payment_method_label: str | None
    reference: str | None
    notes: str | None
    reason: str | None
    payment_is_active: bool | None

    @field_serializer("amount_ars", when_used="json")
    def serialize_money(self, value: Decimal | None) -> str | None:
        return format(value, ".2f") if value is not None else None


class OwnerReceivablesActivityRead(BaseModel):
    owner_id: uuid.UUID
    tracking_configured: bool
    tracking_started_at: datetime | None
    currency: Literal["USD", "ARS"] | None
    locale: str | None
    events: list[ReceivablesActivityEventRead]

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator


class ReportMethod(BaseModel):
    payment_method_id: uuid.UUID
    label: str
    is_active: bool


class PaymentMethodTotal(ReportMethod):
    amount_ars: Decimal
    payment_count: int


class PaymentReportSummary(BaseModel):
    total_amount_ars: Decimal
    payment_count: int
    by_method: list[PaymentMethodTotal]


class ReportPayment(BaseModel):
    payment_id: uuid.UUID
    received_at: datetime
    payment_method_id: uuid.UUID
    payment_method_label: str
    amount_ars: Decimal
    sale_id: uuid.UUID
    owner_id: uuid.UUID | None
    owner_name: str | None
    patient_id: uuid.UUID | None
    patient_name: str | None
    reference: str | None
    created_by_user_id: uuid.UUID | None
    created_by_user_name: str | None

    @field_validator("received_at", mode="after")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        # SQLite drops tzinfo on reads; production timestamptz remains aware.
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class PaymentReport(BaseModel):
    date_from: date
    date_to: date
    timezone: str
    currency_code: str
    locale: str
    summary: PaymentReportSummary
    methods: list[ReportMethod]
    payments: list[ReportPayment]

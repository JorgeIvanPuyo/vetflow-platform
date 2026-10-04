import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.catalog_item import CatalogItemRead
from app.schemas.service import ServiceRead


class ClinicProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    display_name: str | None = None
    logo_url: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    notes: str | None = None
    timezone: str

    @model_validator(mode="after")
    def apply_display_name_fallback(self) -> "ClinicProfileRead":
        if self.display_name is None:
            self.display_name = self.name
        return self


class ClinicProfileUpdate(BaseModel):
    display_name: str | None = None
    logo_url: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    notes: str | None = None
    timezone: str | None = None


class ClinicTeamMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    is_active: bool


class ClinicTeamMemberUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_full_name(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class TenantPreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    receivables_tracking_started_at: datetime | None
    currency_code: str
    locale: str
    default_appointment_duration_minutes: int
    appointment_duration_options: list[int]
    catalog_template_version: str
    default_purchase_tax_rate: Decimal
    default_sale_tax_rate: Decimal
    default_profit_margin: Decimal
    money_rounding_increment: Decimal

    @field_validator("receivables_tracking_started_at")
    @classmethod
    def read_cutoff_as_utc(cls, value: datetime | None) -> datetime | None:
        # SQLite test/dev storage loses tzinfo; stored naive values are UTC.
        return (value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)) if value else None


class TenantPreferenceUpdate(BaseModel):
    receivables_tracking_started_at: AwareDatetime | None = None
    receivables_tracking_start_date: date | None = None

    @model_validator(mode="after")
    def validate_cutoff_input(self) -> "TenantPreferenceUpdate":
        if "receivables_tracking_start_date" in self.model_fields_set:
            if self.receivables_tracking_start_date is None:
                raise ValueError("La fecha de inicio es obligatoria")
            if "receivables_tracking_started_at" in self.model_fields_set:
                raise ValueError("Envía una fecha de inicio o un timestamp, no ambos")
        return self

    @field_validator("receivables_tracking_started_at")
    @classmethod
    def normalize_receivables_cutoff(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None

    currency_code: str | None = None
    locale: str | None = None
    default_appointment_duration_minutes: int | None = Field(default=None, gt=0, le=480)
    appointment_duration_options: list[int] | None = None
    default_purchase_tax_rate: Decimal | None = Field(default=None, ge=0, le=100)
    default_sale_tax_rate: Decimal | None = Field(default=None, ge=0, le=100)
    default_profit_margin: Decimal | None = Field(default=None, ge=0)
    money_rounding_increment: Decimal | None = Field(default=None, gt=0)


class ClinicConfigurationRead(BaseModel):
    preferences: TenantPreferenceRead | None = None
    services: list[ServiceRead] | None = None
    catalogs: dict[str, list[CatalogItemRead]] | None = None

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    currency_code: str
    locale: str
    default_appointment_duration_minutes: int
    appointment_duration_options: list[int]
    catalog_template_version: str
    default_purchase_tax_rate: Decimal
    default_sale_tax_rate: Decimal
    default_profit_margin: Decimal
    money_rounding_increment: Decimal


class TenantPreferenceUpdate(BaseModel):
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

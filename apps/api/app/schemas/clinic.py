import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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

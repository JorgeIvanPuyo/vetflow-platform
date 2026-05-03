import uuid

from pydantic import BaseModel, ConfigDict, model_validator


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

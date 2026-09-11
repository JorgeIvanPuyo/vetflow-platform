import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


ServiceKind = Literal[
    "consultation",
    "follow_up",
    "vaccine",
    "deworming",
    "exam",
    "procedure",
    "other",
]


class ServiceBase(BaseModel):
    price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    kind: ServiceKind
    default_duration_minutes: int = Field(gt=0, le=480)
    calendar_color: str = Field(default="#2563eb", min_length=1, max_length=32)
    is_bookable: bool = True
    sort_order: int = 0

    @field_validator("code", "name", "description", "calendar_color", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    kind: ServiceKind | None = None
    default_duration_minutes: int | None = Field(default=None, gt=0, le=480)
    calendar_color: str | None = Field(default=None, min_length=1, max_length=32)
    is_bookable: bool | None = None
    sort_order: int | None = None

    @field_validator("code", "name", "description", "calendar_color", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class ServiceRead(ServiceBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    normalized_name: str
    is_active: bool
    created_by_user_id: uuid.UUID | None = None
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


class ServiceReorderItem(BaseModel):
    id: uuid.UUID
    sort_order: int


class ServiceReorderRequest(BaseModel):
    items: list[ServiceReorderItem] = Field(min_length=1)

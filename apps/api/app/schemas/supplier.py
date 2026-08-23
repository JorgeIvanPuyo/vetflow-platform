import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class SupplierBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    document_id: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = None
    address: str | None = None
    notes: str | None = None

    @field_validator(
        "name", "document_id", "phone", "email", "address", "notes", mode="before"
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    document_id: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = None
    address: str | None = None
    notes: str | None = None

    @field_validator(
        "name", "document_id", "phone", "email", "address", "notes", mode="before"
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class SupplierRead(SupplierBase):
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

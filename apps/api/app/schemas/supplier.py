from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


SupplierSortBy = Literal["name", "updated_at"]
SortDirection = Literal["asc", "desc"]
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def clean_name(value: str) -> str:
    value = " ".join(value.split())
    if not value:
        raise ValueError("String should have at least 1 character")
    return value


def normalize_name(value: str) -> str:
    return clean_name(value).casefold()


def clean_optional_string(value):
    if value is None or not isinstance(value, str):
        return value
    value = " ".join(value.split())
    return value or None


class SupplierCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    tax_id: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return clean_name(value)

    @field_validator("tax_id", "phone", "email", "address", "notes", mode="before")
    @classmethod
    def validate_optional_strings(cls, value):
        return clean_optional_string(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is not None and EMAIL_PATTERN.fullmatch(value) is None:
            raise ValueError("Invalid email address")
        return value


class SupplierUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    tax_id: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return clean_name(value) if value is not None else None

    @field_validator("tax_id", "phone", "email", "address", "notes", mode="before")
    @classmethod
    def validate_optional_strings(cls, value):
        return clean_optional_string(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is not None and EMAIL_PATTERN.fullmatch(value) is None:
            raise ValueError("Invalid email address")
        return value


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    normalized_name: str
    tax_id: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    notes: str | None = None
    is_active: bool
    created_by_user_id: uuid.UUID | None = None
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_by_user_id")
    def serialize_created_by_user_id(self, value: uuid.UUID | None) -> uuid.UUID | None:
        if self.created_by_user_name or self.created_by_user_email:
            return value
        return None


class SupplierSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    normalized_name: str
    tax_id: str | None = None
    phone: str | None = None
    email: str | None = None
    is_active: bool
    created_by_user_id: uuid.UUID | None = None
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    updated_at: datetime

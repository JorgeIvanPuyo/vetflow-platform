import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer


class PatientBase(BaseModel):
    name: str
    species: str
    breed: str | None = None
    sex: str | None = None
    estimated_age: str | None = None
    birth_date: date | None = None
    weight_kg: Decimal | None = None
    allergies: str | None = None
    chronic_conditions: str | None = None


class PatientCreate(PatientBase):
    owner_id: uuid.UUID


class PatientUpdate(BaseModel):
    owner_id: uuid.UUID | None = None
    name: str | None = None
    species: str | None = None
    breed: str | None = None
    sex: str | None = None
    estimated_age: str | None = None
    birth_date: date | None = None
    weight_kg: Decimal | None = None
    allergies: str | None = None
    chronic_conditions: str | None = None


class PatientRead(PatientBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    owner_id: uuid.UUID
    created_by_user_id: uuid.UUID | None
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

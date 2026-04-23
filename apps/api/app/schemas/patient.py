import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


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
    created_at: datetime
    updated_at: datetime

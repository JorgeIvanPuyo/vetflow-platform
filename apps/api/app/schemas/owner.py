import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OwnerBase(BaseModel):
    full_name: str
    document_id: str | None = None
    phone: str
    email: str | None = None
    address: str | None = None


class OwnerCreate(OwnerBase):
    pass


class OwnerUpdate(BaseModel):
    full_name: str | None = None
    document_id: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None


class OwnerRead(OwnerBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

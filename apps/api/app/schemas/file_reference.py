import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FileReferenceBase(BaseModel):
    name: str
    file_type: str
    description: str | None = None
    external_url: str | None = None


class FileReferenceCreate(FileReferenceBase):
    pass


class FileReferenceUpdate(BaseModel):
    name: str | None = None
    file_type: str | None = None
    description: str | None = None
    external_url: str | None = None


class FileReferenceRead(FileReferenceBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    patient_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

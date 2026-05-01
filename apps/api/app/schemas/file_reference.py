import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer


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

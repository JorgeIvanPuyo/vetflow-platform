import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer


PREVENTIVE_CARE_TYPES = {"vaccine", "deworming", "other"}


class PreventiveCareBase(BaseModel):
    name: str
    care_type: str
    applied_at: datetime
    next_due_at: datetime | None = None
    lot_number: str | None = None
    notes: str | None = None


class PreventiveCareCreate(PreventiveCareBase):
    pass


class PreventiveCareUpdate(BaseModel):
    name: str | None = None
    care_type: str | None = None
    applied_at: datetime | None = None
    next_due_at: datetime | None = None
    lot_number: str | None = None
    notes: str | None = None


class PreventiveCareRead(PreventiveCareBase):
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

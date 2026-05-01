import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer


AppointmentType = Literal[
    "consultation",
    "follow_up",
    "vaccine",
    "deworming",
    "exam",
    "other",
]
AppointmentStatus = Literal["scheduled", "completed", "cancelled", "no_show"]


class AppointmentBase(BaseModel):
    patient_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    assigned_user_id: uuid.UUID | None = None
    title: str
    reason: str | None = None
    appointment_type: AppointmentType
    status: AppointmentStatus = "scheduled"
    start_at: datetime
    end_at: datetime
    notes: str | None = None


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentUpdate(BaseModel):
    patient_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    assigned_user_id: uuid.UUID | None = None
    title: str | None = None
    reason: str | None = None
    appointment_type: AppointmentType | None = None
    status: AppointmentStatus | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    notes: str | None = None


class AppointmentRead(AppointmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    created_by_user_id: uuid.UUID | None
    patient_name: str | None = None
    owner_name: str | None = None
    assigned_user_name: str | None = None
    assigned_user_email: str | None = None
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("assigned_user_id")
    def serialize_assigned_user_id(
        self,
        value: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if self.assigned_user_name or self.assigned_user_email:
            return value
        return None

    @field_serializer("created_by_user_id")
    def serialize_created_by_user_id(
        self,
        value: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if self.created_by_user_name or self.created_by_user_email:
            return value
        return None

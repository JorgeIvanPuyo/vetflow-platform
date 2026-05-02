import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


FollowUpType = Literal[
    "consultation_control",
    "vaccine",
    "deworming",
    "exam_review",
    "other",
]
FollowUpStatus = Literal["pending", "scheduled", "completed", "cancelled", "overdue"]
FollowUpSourceType = Literal["consultation", "preventive_care", "exam", "manual"]


class FollowUpBase(BaseModel):
    owner_id: uuid.UUID | None = None
    assigned_user_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    follow_up_type: FollowUpType
    due_at: datetime
    notes: str | None = None
    source_type: FollowUpSourceType | None = None
    source_id: uuid.UUID | None = None


class FollowUpCreate(FollowUpBase):
    patient_id: uuid.UUID
    create_appointment: bool = False
    appointment_duration_minutes: int = Field(default=30, ge=1, le=1440)


class FollowUpUpdate(BaseModel):
    assigned_user_id: uuid.UUID | None = None
    title: str | None = None
    description: str | None = None
    follow_up_type: FollowUpType | None = None
    status: FollowUpStatus | None = None
    due_at: datetime | None = None
    notes: str | None = None
    appointment_id: uuid.UUID | None = None


class FollowUpCancel(BaseModel):
    notes: str | None = None


class FollowUpRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    patient_id: uuid.UUID
    owner_id: uuid.UUID | None = None
    assigned_user_id: uuid.UUID | None = None
    created_by_user_id: uuid.UUID | None = None
    source_type: FollowUpSourceType | None = None
    source_id: uuid.UUID | None = None
    appointment_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    follow_up_type: FollowUpType
    status: FollowUpStatus
    due_at: datetime
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    notes: str | None = None
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

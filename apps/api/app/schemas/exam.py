import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer


EXAM_STATUSES = {"requested", "performed", "result_loaded"}


class ExamBase(BaseModel):
    exam_type: str
    requested_at: datetime
    observations: str | None = None


class ExamCreate(ExamBase):
    patient_id: uuid.UUID
    consultation_id: uuid.UUID | None = None


class ExamUpdate(BaseModel):
    exam_type: str | None = None
    status: str | None = None
    performed_at: datetime | None = None
    result_summary: str | None = None
    result_detail: str | None = None
    observations: str | None = None


class ExamRead(ExamBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    patient_id: uuid.UUID
    consultation_id: uuid.UUID | None
    requested_by_user_id: uuid.UUID | None
    requested_by_user_name: str | None = None
    requested_by_user_email: str | None = None
    status: str
    performed_at: datetime | None
    result_summary: str | None
    result_detail: str | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("requested_by_user_id")
    def serialize_requested_by_user_id(
        self,
        value: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if self.requested_by_user_name or self.requested_by_user_email:
            return value
        return None

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.schemas.exam import ExamRead
from app.schemas.file_reference import FileReferenceRead
from app.schemas.patient import PatientRead
from app.schemas.preventive_care import PreventiveCareRead


CONSULTATION_STATUSES = {"draft", "completed"}
STUDY_REQUEST_TYPES = {"laboratory", "exam", "other"}


class ConsultationBase(BaseModel):
    visit_date: datetime
    reason: str
    anamnesis: str | None = None
    clinical_exam: str | None = None
    presumptive_diagnosis: str | None = None
    diagnostic_plan: str | None = None
    therapeutic_plan: str | None = None
    final_diagnosis: str | None = None
    indications: str | None = None
    status: Literal["draft", "completed"] = "draft"
    current_step: int | None = None
    symptoms: str | None = None
    symptom_duration: str | None = None
    relevant_history: str | None = None
    habits_and_diet: str | None = None
    temperature_c: float | None = None
    current_weight_kg: float | None = None
    heart_rate: int | None = None
    respiratory_rate: int | None = None
    mucous_membranes: str | None = None
    hydration: str | None = None
    physical_exam_findings: str | None = None
    diagnostic_tags: list[str] | None = None
    diagnostic_plan_notes: str | None = None
    therapeutic_plan_notes: str | None = None
    next_control_date: date | None = None
    consultation_summary: str | None = None
    reminder_requested: bool = False


class ConsultationCreate(ConsultationBase):
    patient_id: uuid.UUID


class ConsultationUpdate(BaseModel):
    visit_date: datetime | None = None
    reason: str | None = None
    anamnesis: str | None = None
    clinical_exam: str | None = None
    presumptive_diagnosis: str | None = None
    diagnostic_plan: str | None = None
    therapeutic_plan: str | None = None
    final_diagnosis: str | None = None
    indications: str | None = None
    status: Literal["draft", "completed"] | None = None
    current_step: int | None = None
    symptoms: str | None = None
    symptom_duration: str | None = None
    relevant_history: str | None = None
    habits_and_diet: str | None = None
    temperature_c: float | None = None
    current_weight_kg: float | None = None
    heart_rate: int | None = None
    respiratory_rate: int | None = None
    mucous_membranes: str | None = None
    hydration: str | None = None
    physical_exam_findings: str | None = None
    diagnostic_tags: list[str] | None = None
    diagnostic_plan_notes: str | None = None
    therapeutic_plan_notes: str | None = None
    next_control_date: date | None = None
    consultation_summary: str | None = None
    reminder_requested: bool | None = None


class ConsultationStepUpdate(ConsultationUpdate):
    pass


class ConsultationMedicationCreate(BaseModel):
    medication_name: str
    dose_or_quantity: str | None = None
    instructions: str | None = None


class ConsultationMedicationRead(ConsultationMedicationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    consultation_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ConsultationStudyRequestCreate(BaseModel):
    name: str
    study_type: Literal["laboratory", "exam", "other"]
    notes: str | None = None


class ConsultationStudyRequestRead(ConsultationStudyRequestCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    consultation_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ConsultationRead(ConsultationBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    patient_id: uuid.UUID
    created_by_user_id: uuid.UUID | None
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    attending_user_id: uuid.UUID | None
    attending_user_name: str | None = None
    attending_user_email: str | None = None
    created_at: datetime
    updated_at: datetime
    medications: list[ConsultationMedicationRead] = Field(default_factory=list)
    study_requests: list[ConsultationStudyRequestRead] = Field(default_factory=list)

    @field_serializer("created_by_user_id")
    def serialize_created_by_user_id(
        self,
        value: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if self.created_by_user_name or self.created_by_user_email:
            return value
        return None

    @field_serializer("attending_user_id")
    def serialize_attending_user_id(
        self,
        value: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if self.attending_user_name or self.attending_user_email:
            return value
        return None


class TimelineUserTrace(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str


class ClinicalHistoryTimelineItem(BaseModel):
    type: str
    id: uuid.UUID
    date: datetime
    title: str
    summary: str
    created_by: TimelineUserTrace | None = None
    attended_by: TimelineUserTrace | None = None
    requested_by: TimelineUserTrace | None = None


class ClinicalHistoryRead(BaseModel):
    patient: PatientRead
    consultations: list[ConsultationRead]
    exams: list[ExamRead]
    preventive_care: list[PreventiveCareRead] = Field(default_factory=list)
    file_references: list[FileReferenceRead] = Field(default_factory=list)
    timeline: list[ClinicalHistoryTimelineItem]

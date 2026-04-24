import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.exam import ExamRead
from app.schemas.patient import PatientRead


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


class ConsultationRead(ConsultationBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    patient_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ClinicalHistoryTimelineItem(BaseModel):
    type: str
    id: uuid.UUID
    date: datetime
    title: str
    summary: str


class ClinicalHistoryRead(BaseModel):
    patient: PatientRead
    consultations: list[ConsultationRead]
    exams: list[ExamRead]
    timeline: list[ClinicalHistoryTimelineItem]

import uuid
from datetime import datetime

from pydantic import BaseModel


class DashboardPeriodRead(BaseModel):
    date_from: datetime
    date_to: datetime


class DashboardCardsRead(BaseModel):
    appointments_today: int
    follow_ups_upcoming: int
    follow_ups_overdue: int
    consultations_recent: int
    preventive_care_upcoming: int
    files_recent: int


class DashboardAppointmentItemRead(BaseModel):
    id: uuid.UUID
    title: str
    appointment_type: str
    status: str
    start_at: datetime
    end_at: datetime
    patient_name: str | None = None
    owner_name: str | None = None
    assigned_user_name: str | None = None


class DashboardFollowUpItemRead(BaseModel):
    id: uuid.UUID
    title: str
    follow_up_type: str
    status: str
    due_at: datetime
    patient_name: str | None = None
    owner_name: str | None = None
    assigned_user_name: str | None = None


class DashboardConsultationItemRead(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str | None = None
    reason: str
    status: str
    visit_date: datetime
    attending_user_name: str | None = None
    created_by_user_name: str | None = None


class DashboardPreventiveCareItemRead(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str | None = None
    name: str
    care_type: str
    next_due_at: datetime
    created_by_user_name: str | None = None


class DashboardFileItemRead(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str | None = None
    name: str
    file_type: str
    uploaded_at: datetime
    created_by_user_name: str | None = None


class DashboardVeterinarianActivityRead(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    appointments_today_count: int
    consultations_recent_count: int
    follow_ups_pending_count: int


class DashboardSummaryRead(BaseModel):
    period: DashboardPeriodRead
    cards: DashboardCardsRead
    appointments_today: list[DashboardAppointmentItemRead]
    upcoming_follow_ups: list[DashboardFollowUpItemRead]
    overdue_follow_ups: list[DashboardFollowUpItemRead]
    recent_consultations: list[DashboardConsultationItemRead]
    upcoming_preventive_care: list[DashboardPreventiveCareItemRead]
    recent_files: list[DashboardFileItemRead]
    activity_by_veterinarian: list[DashboardVeterinarianActivityRead]

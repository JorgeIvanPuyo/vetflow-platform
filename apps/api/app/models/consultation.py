from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Consultation(BaseModel):
    __tablename__ = "consultations"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("patients.id"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    attending_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    visit_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    anamnesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    clinical_exam: Mapped[str | None] = mapped_column(Text, nullable=True)
    presumptive_diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnostic_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    therapeutic_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    indications: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="draft",
        server_default="draft",
        index=True,
    )
    current_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    symptoms: Mapped[str | None] = mapped_column(Text, nullable=True)
    symptom_duration: Mapped[str | None] = mapped_column(String(255), nullable=True)
    relevant_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    habits_and_diet: Mapped[str | None] = mapped_column(Text, nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    respiratory_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mucous_membranes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hydration: Mapped[str | None] = mapped_column(String(255), nullable=True)
    physical_exam_findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnostic_tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    diagnostic_plan_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    therapeutic_plan_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_control_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    consultation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminder_requested: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="consultations")
    patient: Mapped[Patient] = relationship("Patient", back_populates="consultations")
    created_by_user: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[created_by_user_id],
    )
    attending_user: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[attending_user_id],
    )
    exams: Mapped[list[Exam]] = relationship("Exam", back_populates="consultation")
    medications: Mapped[list[ConsultationMedication]] = relationship(
        "ConsultationMedication",
        back_populates="consultation",
    )
    study_requests: Mapped[list[ConsultationStudyRequest]] = relationship(
        "ConsultationStudyRequest",
        back_populates="consultation",
    )

    @property
    def created_by_user_name(self) -> str | None:
        if self.created_by_user is None or self.created_by_user.tenant_id != self.tenant_id:
            return None
        return self.created_by_user.full_name

    @property
    def created_by_user_email(self) -> str | None:
        if self.created_by_user is None or self.created_by_user.tenant_id != self.tenant_id:
            return None
        return self.created_by_user.email

    @property
    def attending_user_name(self) -> str | None:
        if self.attending_user is None or self.attending_user.tenant_id != self.tenant_id:
            return None
        return self.attending_user.full_name

    @property
    def attending_user_email(self) -> str | None:
        if self.attending_user is None or self.attending_user.tenant_id != self.tenant_id:
            return None
        return self.attending_user.email


class ConsultationMedication(BaseModel):
    __tablename__ = "consultation_medications"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    consultation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("consultations.id"),
        nullable=False,
        index=True,
    )
    medication_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dose_or_quantity: Mapped[str | None] = mapped_column(String(255), nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    consultation: Mapped[Consultation] = relationship(
        "Consultation",
        back_populates="medications",
    )


class ConsultationStudyRequest(BaseModel):
    __tablename__ = "consultation_study_requests"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    consultation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("consultations.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    study_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    consultation: Mapped[Consultation] = relationship(
        "Consultation",
        back_populates="study_requests",
    )

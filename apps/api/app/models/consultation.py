from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
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

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="consultations")
    patient: Mapped[Patient] = relationship("Patient", back_populates="consultations")
    exams: Mapped[list[Exam]] = relationship("Exam", back_populates="consultation")

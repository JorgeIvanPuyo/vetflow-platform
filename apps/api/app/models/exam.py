from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Exam(BaseModel):
    __tablename__ = "exams"

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
    consultation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("consultations.id"),
        nullable=True,
        index=True,
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    exam_type: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    performed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    observations: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="exams")
    patient: Mapped[Patient] = relationship("Patient", back_populates="exams")
    consultation: Mapped[Consultation | None] = relationship(
        "Consultation",
        back_populates="exams",
    )
    requested_by_user: Mapped[User | None] = relationship("User")

    @property
    def requested_by_user_name(self) -> str | None:
        if (
            self.requested_by_user is None
            or self.requested_by_user.tenant_id != self.tenant_id
        ):
            return None
        return self.requested_by_user.full_name

    @property
    def requested_by_user_email(self) -> str | None:
        if (
            self.requested_by_user is None
            or self.requested_by_user.tenant_id != self.tenant_id
        ):
            return None
        return self.requested_by_user.email

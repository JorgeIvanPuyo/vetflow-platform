from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Appointment(BaseModel):
    __tablename__ = "appointments"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("patients.id"),
        nullable=True,
        index=True,
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("owners.id"),
        nullable=True,
        index=True,
    )
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    appointment_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="scheduled",
        server_default="scheduled",
        index=True,
    )
    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="appointments")
    patient: Mapped[Patient | None] = relationship("Patient")
    owner: Mapped[Owner | None] = relationship("Owner")
    assigned_user: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[assigned_user_id],
    )
    created_by_user: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[created_by_user_id],
    )

    @property
    def patient_name(self) -> str | None:
        if self.patient is None or self.patient.tenant_id != self.tenant_id:
            return None
        return self.patient.name

    @property
    def owner_name(self) -> str | None:
        if self.owner is None or self.owner.tenant_id != self.tenant_id:
            return None
        return self.owner.full_name

    @property
    def assigned_user_name(self) -> str | None:
        if self.assigned_user is None or self.assigned_user.tenant_id != self.tenant_id:
            return None
        return self.assigned_user.full_name

    @property
    def assigned_user_email(self) -> str | None:
        if self.assigned_user is None or self.assigned_user.tenant_id != self.tenant_id:
            return None
        return self.assigned_user.email

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

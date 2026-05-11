from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Patient(BaseModel):
    __tablename__ = "patients"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("owners.id"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    species: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    breed: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sex: Mapped[str | None] = mapped_column(String(50), nullable=True)
    estimated_age: Mapped[str | None] = mapped_column(String(100), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    chronic_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_bucket_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_object_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    photo_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    photo_uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    tenant: Mapped[Tenant] = relationship("Tenant")
    owner: Mapped[Owner] = relationship("Owner", back_populates="patients")
    created_by_user: Mapped[User | None] = relationship("User")
    consultations: Mapped[list[Consultation]] = relationship(
        "Consultation",
        back_populates="patient",
    )
    exams: Mapped[list[Exam]] = relationship("Exam", back_populates="patient")
    preventive_care_records: Mapped[list[PatientPreventiveCare]] = relationship(
        "PatientPreventiveCare",
        back_populates="patient",
    )
    file_references: Mapped[list[PatientFileReference]] = relationship(
        "PatientFileReference",
        back_populates="patient",
    )
    follow_ups: Mapped[list[FollowUp]] = relationship(
        "FollowUp",
        back_populates="patient",
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

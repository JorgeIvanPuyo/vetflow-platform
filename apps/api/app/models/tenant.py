from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Tenant(BaseModel):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    logo_object_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    users: Mapped[list[User]] = relationship("User", back_populates="tenant")
    owners: Mapped[list[Owner]] = relationship("Owner", back_populates="tenant")
    consultations: Mapped[list[Consultation]] = relationship(
        "Consultation",
        back_populates="tenant",
    )
    exams: Mapped[list[Exam]] = relationship("Exam", back_populates="tenant")
    appointments: Mapped[list[Appointment]] = relationship(
        "Appointment",
        back_populates="tenant",
    )
    follow_ups: Mapped[list[FollowUp]] = relationship(
        "FollowUp",
        back_populates="tenant",
    )
    inventory_items: Mapped[list[InventoryItem]] = relationship(
        "InventoryItem",
        back_populates="tenant",
    )
    inventory_movements: Mapped[list[InventoryMovement]] = relationship(
        "InventoryMovement",
        back_populates="tenant",
    )

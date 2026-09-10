from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Service(BaseModel):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('consultation', 'follow_up', 'vaccine', 'deworming', 'exam', 'procedure', 'other')",
            name="ck_services_kind",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    default_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    calendar_color: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="#2563eb",
        server_default="#2563eb",
    )
    is_bookable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="services")
    created_by_user: Mapped[User | None] = relationship("User")
    appointments: Mapped[list[Appointment]] = relationship(
        "Appointment",
        back_populates="service",
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


Index(
    "ux_services_tenant_normalized_name_active",
    Service.tenant_id,
    Service.normalized_name,
    unique=True,
    sqlite_where=Service.is_active.is_(True),
    postgresql_where=Service.is_active.is_(True),
)

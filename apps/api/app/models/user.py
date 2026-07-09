from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.roles import DEFAULT_ROLE
from app.models.base import BaseModel


class User(BaseModel):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('superadmin', 'medico_veterinario', 'contador')",
            name="ck_users_role",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DEFAULT_ROLE,
        server_default=DEFAULT_ROLE,
    )

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="users")

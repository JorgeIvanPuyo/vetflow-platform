from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Tenant(BaseModel):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    users: Mapped[list[User]] = relationship("User", back_populates="tenant")
    owners: Mapped[list[Owner]] = relationship("Owner", back_populates="tenant")

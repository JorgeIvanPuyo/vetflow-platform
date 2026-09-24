from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, JSON, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class TenantPreference(BaseModel):
    __tablename__ = "tenant_preferences"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
        server_default="USD",
    )
    locale: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="es-PA",
        server_default="es-PA",
    )
    default_appointment_duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        server_default="30",
    )
    appointment_duration_options: Mapped[list[int]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: [15, 30, 45, 60],
    )
    catalog_template_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="regional-v1",
        server_default="regional-v1",
    )
    default_purchase_tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    default_sale_tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    default_profit_margin: Mapped[Decimal] = mapped_column(
        Numeric(8, 2),
        nullable=False,
        default=Decimal("35"),
        server_default="35",
    )
    money_rounding_increment: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("10"),
        server_default="10",
    )

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="preferences")

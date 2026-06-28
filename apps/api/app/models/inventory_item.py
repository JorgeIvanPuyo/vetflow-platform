from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


MONEY_QUANTUM = Decimal("0.01")
HUNDRED = Decimal("100")
ZERO = Decimal("0")


class InventoryItem(BaseModel):
    __tablename__ = "inventory_items"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    subcategory: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    supplier: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    lot_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    current_stock: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    minimum_stock: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    purchase_price_ars: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    purchase_tax_rate_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=ZERO,
        server_default="0",
    )
    profit_margin_percentage: Mapped[Decimal] = mapped_column(
        Numeric(8, 2),
        nullable=False,
        default=Decimal("35"),
        server_default="35",
    )
    sale_price_ars: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    sale_tax_rate_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=ZERO,
        server_default="0",
    )
    round_sale_price: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="inventory_items")
    created_by_user: Mapped[User | None] = relationship("User")
    movements: Mapped[list[InventoryMovement]] = relationship(
        "InventoryMovement",
        back_populates="inventory_item",
    )

    @property
    def is_low_stock(self) -> bool:
        return self.current_stock <= self.minimum_stock

    @property
    def is_expired(self) -> bool:
        if self.expiration_date is None:
            return False
        return self.expiration_date < date.today()

    @property
    def is_expiring_soon(self) -> bool:
        if self.expiration_date is None or self.is_expired:
            return False
        today = date.today()
        return today <= self.expiration_date <= today + timedelta(days=30)

    @property
    def purchase_tax_amount_ars(self) -> Decimal | None:
        return self._tax_amount(
            self.purchase_price_ars,
            self.purchase_tax_rate_percentage,
        )

    @property
    def purchase_price_with_tax_ars(self) -> Decimal | None:
        return self._price_with_tax(
            self.purchase_price_ars,
            self.purchase_tax_rate_percentage,
        )

    @property
    def sale_tax_amount_ars(self) -> Decimal | None:
        return self._tax_amount(
            self.sale_price_ars,
            self.sale_tax_rate_percentage,
        )

    @property
    def sale_price_with_tax_ars(self) -> Decimal | None:
        return self._price_with_tax(
            self.sale_price_ars,
            self.sale_tax_rate_percentage,
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

    def _tax_amount(
        self,
        price: Decimal | None,
        tax_rate_percentage: Decimal | None,
    ) -> Decimal | None:
        if price is None:
            return None
        tax_rate = tax_rate_percentage if tax_rate_percentage is not None else ZERO
        return (price * tax_rate / HUNDRED).quantize(
            MONEY_QUANTUM,
            rounding=ROUND_HALF_UP,
        )

    def _price_with_tax(
        self,
        price: Decimal | None,
        tax_rate_percentage: Decimal | None,
    ) -> Decimal | None:
        if price is None:
            return None
        tax_amount = self._tax_amount(price, tax_rate_percentage) or ZERO
        return (price + tax_amount).quantize(
            MONEY_QUANTUM,
            rounding=ROUND_HALF_UP,
        )

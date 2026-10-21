from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.fiscal_configuration import FiscalPolicy, FiscalSeries
from app.models.payment import PaymentMethod


class FiscalConfigurationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def policy(self, tenant_id: uuid.UUID, *, for_update: bool = False) -> FiscalPolicy | None:
        statement = select(FiscalPolicy).where(FiscalPolicy.tenant_id == tenant_id)
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def series(self, tenant_id: uuid.UUID) -> list[FiscalSeries]:
        return list(self.db.scalars(select(FiscalSeries).where(FiscalSeries.tenant_id == tenant_id).order_by(FiscalSeries.environment, FiscalSeries.point_of_sale, FiscalSeries.document_type, FiscalSeries.id)))

    def get_series(self, tenant_id: uuid.UUID, series_id: uuid.UUID, *, for_update: bool = False) -> FiscalSeries | None:
        statement = select(FiscalSeries).where(FiscalSeries.tenant_id == tenant_id, FiscalSeries.id == series_id)
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def payment_methods(self, tenant_id: uuid.UUID) -> list[PaymentMethod]:
        return list(self.db.scalars(select(PaymentMethod).where(PaymentMethod.tenant_id == tenant_id).order_by(PaymentMethod.sort_order, PaymentMethod.label, PaymentMethod.id)))

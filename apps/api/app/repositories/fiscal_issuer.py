from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.sale_fiscal import FiscalIssuer
from app.models.user import User


class FiscalIssuerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, issuer: FiscalIssuer) -> FiscalIssuer:
        self.db.add(issuer)
        self.db.flush()
        return issuer

    def save(self, issuer: FiscalIssuer) -> FiscalIssuer:
        self.db.add(issuer)
        self.db.flush()
        return issuer

    def get_by_id(
        self, tenant_id: uuid.UUID, issuer_id: uuid.UUID, *, for_update: bool = False
    ) -> FiscalIssuer | None:
        statement = (
            select(FiscalIssuer)
            .where(
                FiscalIssuer.tenant_id == tenant_id,
                FiscalIssuer.id == issuer_id,
            )
            .options(
                selectinload(
                    FiscalIssuer.user.and_(User.tenant_id == tenant_id)
                )
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def get_by_user(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID
    ) -> FiscalIssuer | None:
        return self.db.scalar(
            select(FiscalIssuer).where(
                FiscalIssuer.tenant_id == tenant_id,
                FiscalIssuer.user_id == user_id,
            )
        )

    def list(self, tenant_id: uuid.UUID, *, active_only: bool) -> list[FiscalIssuer]:
        filters = [FiscalIssuer.tenant_id == tenant_id]
        if active_only:
            filters.append(FiscalIssuer.is_active.is_(True))
        statement = (
            select(FiscalIssuer)
            .where(*filters)
            .options(
                selectinload(
                    FiscalIssuer.user.and_(User.tenant_id == tenant_id)
                )
            )
            .order_by(
                FiscalIssuer.is_active.desc(), func.lower(FiscalIssuer.display_name)
            )
        )
        return list(self.db.scalars(statement).all())

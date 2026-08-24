import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.service import Service


class ServiceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, service: Service) -> Service:
        self.db.add(service)
        self.db.flush()
        self.db.refresh(service)
        return service

    def get_by_id(self, tenant_id: uuid.UUID, service_id: uuid.UUID) -> Service | None:
        statement = (
            select(Service)
            .where(
                Service.id == service_id,
                Service.tenant_id == tenant_id,
            )
            .options(selectinload(Service.created_by_user))
        )
        return self.db.scalar(statement)

    def get_active_by_normalized_name(
        self,
        tenant_id: uuid.UUID,
        normalized_name: str,
    ) -> Service | None:
        statement = select(Service).where(
            Service.tenant_id == tenant_id,
            Service.normalized_name == normalized_name,
            Service.is_active.is_(True),
        )
        return self.db.scalar(statement)

    def get_by_normalized_name(
        self,
        tenant_id: uuid.UUID,
        normalized_name: str,
    ) -> Service | None:
        # is_active is only guaranteed unique among active rows (see the partial
        # unique index), so an inactive normalized_name can have duplicates. Prefer
        # the active match, then the most recently touched inactive one.
        statement = (
            select(Service)
            .where(
                Service.tenant_id == tenant_id,
                Service.normalized_name == normalized_name,
            )
            .order_by(Service.is_active.desc(), Service.updated_at.desc())
        )
        return self.db.scalars(statement).first()

    def list(
        self,
        tenant_id: uuid.UUID,
        *,
        include_inactive: bool,
        bookable_only: bool = False,
    ) -> list[Service]:
        statement: Select[tuple[Service]] = (
            select(Service)
            .where(Service.tenant_id == tenant_id)
            .options(selectinload(Service.created_by_user))
        )
        if not include_inactive:
            statement = statement.where(Service.is_active.is_(True))
        if bookable_only:
            statement = statement.where(Service.is_bookable.is_(True))
        return list(
            self.db.scalars(
                statement.order_by(Service.sort_order.asc(), func.lower(Service.name).asc())
            ).all()
        )

    def update(self, service: Service, updates: dict) -> Service:
        for field, value in updates.items():
            setattr(service, field, value)
        self.db.add(service)
        self.db.flush()
        self.db.refresh(service)
        return service

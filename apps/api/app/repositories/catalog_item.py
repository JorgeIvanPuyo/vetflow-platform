from __future__ import annotations

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.catalog_item import CatalogItem


class CatalogItemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, item: CatalogItem) -> CatalogItem:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_by_id(
        self,
        tenant_id: uuid.UUID,
        catalog_type: str,
        item_id: uuid.UUID,
    ) -> CatalogItem | None:
        statement = (
            select(CatalogItem)
            .where(
                CatalogItem.id == item_id,
                CatalogItem.tenant_id == tenant_id,
                CatalogItem.catalog_type == catalog_type,
            )
            .options(selectinload(CatalogItem.created_by_user))
        )
        return self.db.scalar(statement)

    def get_active_by_normalized_name(
        self,
        tenant_id: uuid.UUID,
        catalog_type: str,
        normalized_name: str,
    ) -> CatalogItem | None:
        statement = select(CatalogItem).where(
            CatalogItem.tenant_id == tenant_id,
            CatalogItem.catalog_type == catalog_type,
            CatalogItem.normalized_name == normalized_name,
            CatalogItem.is_active.is_(True),
        )
        return self.db.scalar(statement)

    def get_by_normalized_name(
        self,
        tenant_id: uuid.UUID,
        catalog_type: str,
        normalized_name: str,
    ) -> CatalogItem | None:
        # is_active is only guaranteed unique among active rows (see the partial
        # unique index), so an inactive normalized_name can have duplicates. Prefer
        # the active match, then the most recently touched inactive one.
        statement = (
            select(CatalogItem)
            .where(
                CatalogItem.tenant_id == tenant_id,
                CatalogItem.catalog_type == catalog_type,
                CatalogItem.normalized_name == normalized_name,
            )
            .order_by(CatalogItem.is_active.desc(), CatalogItem.updated_at.desc())
        )
        return self.db.scalars(statement).first()

    def list(
        self,
        tenant_id: uuid.UUID,
        catalog_type: str,
        *,
        include_inactive: bool,
    ) -> list[CatalogItem]:
        statement: Select[tuple[CatalogItem]] = (
            select(CatalogItem)
            .where(
                CatalogItem.tenant_id == tenant_id,
                CatalogItem.catalog_type == catalog_type,
            )
            .options(selectinload(CatalogItem.created_by_user))
        )
        if not include_inactive:
            statement = statement.where(CatalogItem.is_active.is_(True))
        return list(
            self.db.scalars(
                statement.order_by(
                    CatalogItem.sort_order.asc(),
                    func.lower(CatalogItem.name).asc(),
                )
            ).all()
        )

    def list_active_by_types(
        self,
        tenant_id: uuid.UUID,
        catalog_types: tuple[str, ...],
    ) -> list[CatalogItem]:
        statement = (
            select(CatalogItem)
            .where(
                CatalogItem.tenant_id == tenant_id,
                CatalogItem.catalog_type.in_(catalog_types),
                CatalogItem.is_active.is_(True),
            )
            .options(selectinload(CatalogItem.created_by_user))
            .order_by(
                CatalogItem.catalog_type.asc(),
                CatalogItem.sort_order.asc(),
                func.lower(CatalogItem.name).asc(),
            )
        )
        return list(self.db.scalars(statement).all())

    def update(self, item: CatalogItem, updates: dict) -> CatalogItem:
        for field, value in updates.items():
            setattr(item, field, value)
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

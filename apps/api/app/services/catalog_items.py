import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.catalog_item import CatalogItem
from app.models.user import User
from app.repositories.catalog_item import CatalogItemRepository
from app.repositories.user import UserRepository
from app.schemas.catalog_item import (
    CATALOG_TYPES,
    PARENT_CATALOG_TYPES,
    CatalogItemCreate,
    CatalogItemReorderRequest,
    CatalogItemUpdate,
)
from app.services.catalog_defaults import DEFAULT_CATALOG_ITEM_TEMPLATES
from app.services.normalization import normalize_name


class CatalogItemService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.catalog_item_repository = CatalogItemRepository(db)
        self.user_repository = UserRepository(db)

    def create_item(
        self,
        tenant_id: uuid.UUID,
        catalog_type: str,
        payload: CatalogItemCreate,
        *,
        created_by_user_id: uuid.UUID | None = None,
    ) -> CatalogItem:
        self._validate_catalog_type(catalog_type)
        self._validate_optional_user(tenant_id, created_by_user_id)
        self._validate_parent(tenant_id, catalog_type, payload.parent_id)
        normalized_name = normalize_name(payload.name)
        self._ensure_active_name_available(tenant_id, catalog_type, normalized_name)
        item = CatalogItem(
            tenant_id=tenant_id,
            catalog_type=catalog_type,
            normalized_name=normalized_name,
            created_by_user_id=created_by_user_id,
            **payload.model_dump(),
        )
        try:
            self.catalog_item_repository.create(item)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(
                409,
                "catalog_item_duplicate_name",
                "An active catalog item with this name already exists",
            ) from exc
        return self.get_item(tenant_id, catalog_type, item.id)

    def list_items(
        self,
        tenant_id: uuid.UUID,
        catalog_type: str,
        *,
        include_inactive: bool = False,
    ) -> list[CatalogItem]:
        self._validate_catalog_type(catalog_type)
        return self.catalog_item_repository.list(
            tenant_id,
            catalog_type,
            include_inactive=include_inactive,
        )

    def get_item(
        self,
        tenant_id: uuid.UUID,
        catalog_type: str,
        item_id: uuid.UUID,
    ) -> CatalogItem:
        self._validate_catalog_type(catalog_type)
        item = self.catalog_item_repository.get_by_id(tenant_id, catalog_type, item_id)
        if item is None:
            raise AppError(404, "catalog_item_not_found", "Catalog item not found")
        return item

    def update_item(
        self,
        tenant_id: uuid.UUID,
        catalog_type: str,
        item_id: uuid.UUID,
        payload: CatalogItemUpdate,
    ) -> CatalogItem:
        item = self.get_item(tenant_id, catalog_type, item_id)
        updates = payload.model_dump(exclude_unset=True)
        for field in ("name", "sort_order"):
            if field in updates and updates[field] is None:
                raise AppError(422, "validation_error", f"{field} cannot be null")

        if "parent_id" in updates:
            self._validate_parent(tenant_id, catalog_type, updates["parent_id"])

        if "name" in updates:
            normalized_name = normalize_name(updates["name"])
            if item.normalized_name != normalized_name or not item.is_active:
                self._ensure_active_name_available(
                    tenant_id,
                    catalog_type,
                    normalized_name,
                    exclude_item_id=item.id,
                )
            updates["normalized_name"] = normalized_name

        try:
            updated_item = self.catalog_item_repository.update(item, updates)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(
                409,
                "catalog_item_duplicate_name",
                "An active catalog item with this name already exists",
            ) from exc
        return self.get_item(tenant_id, catalog_type, updated_item.id)

    def activate_item(
        self,
        tenant_id: uuid.UUID,
        catalog_type: str,
        item_id: uuid.UUID,
    ) -> CatalogItem:
        item = self.get_item(tenant_id, catalog_type, item_id)
        self._ensure_active_name_available(
            tenant_id,
            catalog_type,
            item.normalized_name,
            exclude_item_id=item.id,
        )
        try:
            updated_item = self.catalog_item_repository.update(item, {"is_active": True})
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(
                409,
                "catalog_item_duplicate_name",
                "An active catalog item with this name already exists",
            ) from exc
        return self.get_item(tenant_id, catalog_type, updated_item.id)

    def deactivate_item(
        self,
        tenant_id: uuid.UUID,
        catalog_type: str,
        item_id: uuid.UUID,
    ) -> CatalogItem:
        item = self.get_item(tenant_id, catalog_type, item_id)
        updated_item = self.catalog_item_repository.update(item, {"is_active": False})
        self.db.commit()
        return self.get_item(tenant_id, catalog_type, updated_item.id)

    def reorder_items(
        self,
        tenant_id: uuid.UUID,
        catalog_type: str,
        payload: CatalogItemReorderRequest,
    ) -> list[CatalogItem]:
        self._validate_catalog_type(catalog_type)
        seen: set[uuid.UUID] = set()
        for entry in payload.items:
            if entry.id in seen:
                raise AppError(
                    422,
                    "validation_error",
                    "Duplicate catalog item id in reorder payload",
                )
            seen.add(entry.id)

        for entry in payload.items:
            item = self.get_item(tenant_id, catalog_type, entry.id)
            self.catalog_item_repository.update(item, {"sort_order": entry.sort_order})

        self.db.commit()
        return self.list_items(tenant_id, catalog_type, include_inactive=True)

    def restore_defaults(
        self,
        tenant_id: uuid.UUID,
        catalog_type: str,
    ) -> list[CatalogItem]:
        self._validate_catalog_type(catalog_type)
        templates = DEFAULT_CATALOG_ITEM_TEMPLATES.get(catalog_type, ())
        for template in templates:
            normalized_name = normalize_name(str(template["name"]))
            existing = self.catalog_item_repository.get_by_normalized_name(
                tenant_id,
                catalog_type,
                normalized_name,
            )
            if existing is None:
                self.catalog_item_repository.create(
                    CatalogItem(
                        tenant_id=tenant_id,
                        catalog_type=catalog_type,
                        normalized_name=normalized_name,
                        **template,
                    )
                )
            elif not existing.is_active:
                # Reactivate only: never overwrite a name/description/sort_order the
                # tenant may have already customized before deactivating it.
                self.catalog_item_repository.update(existing, {"is_active": True})
        self.db.commit()
        return self.list_items(tenant_id, catalog_type, include_inactive=True)

    def list_active_grouped(self, tenant_id: uuid.UUID) -> dict[str, list[CatalogItem]]:
        grouped: dict[str, list[CatalogItem]] = {
            catalog_type: [] for catalog_type in CATALOG_TYPES
        }
        for item in self.catalog_item_repository.list_active_by_types(
            tenant_id,
            CATALOG_TYPES,
        ):
            grouped[item.catalog_type].append(item)
        return grouped

    def _validate_catalog_type(self, catalog_type: str) -> None:
        if catalog_type not in CATALOG_TYPES:
            raise AppError(
                422,
                "invalid_catalog_type",
                f"catalog_type must be one of: {', '.join(CATALOG_TYPES)}",
            )

    def _ensure_active_name_available(
        self,
        tenant_id: uuid.UUID,
        catalog_type: str,
        normalized_name: str,
        *,
        exclude_item_id: uuid.UUID | None = None,
    ) -> None:
        existing = self.catalog_item_repository.get_active_by_normalized_name(
            tenant_id,
            catalog_type,
            normalized_name,
        )
        if existing is not None and existing.id != exclude_item_id:
            raise AppError(
                409,
                "catalog_item_duplicate_name",
                "An active catalog item with this name already exists",
            )

    def _validate_parent(
        self,
        tenant_id: uuid.UUID,
        catalog_type: str,
        parent_id: uuid.UUID | None,
    ) -> None:
        if parent_id is None:
            return
        expected_parent_type = PARENT_CATALOG_TYPES.get(catalog_type)
        if expected_parent_type is None:
            raise AppError(
                422,
                "invalid_catalog_parent",
                f"{catalog_type} does not support parent_id",
            )
        parent = self.catalog_item_repository.get_by_id(
            tenant_id,
            expected_parent_type,
            parent_id,
        )
        if parent is None:
            raise AppError(404, "catalog_item_not_found", "Parent catalog item not found")

    def _validate_optional_user(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> None:
        if user_id is None:
            return
        user = self.user_repository.get_by_id(tenant_id, user_id)
        if user is not None:
            return
        user_any_tenant = self.db.get(User, user_id)
        if user_any_tenant is not None:
            raise AppError(
                409,
                "invalid_cross_tenant_access",
                "User does not belong to the provided tenant",
            )
        raise AppError(404, "user_not_found", "User not found")

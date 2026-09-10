import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.service import Service
from app.models.user import User
from app.repositories.service import ServiceRepository
from app.repositories.user import UserRepository
from app.schemas.service import ServiceCreate, ServiceReorderRequest, ServiceUpdate
from app.services.catalog_defaults import DEFAULT_SERVICE_TEMPLATES
from app.services.normalization import normalize_name


class ServiceCatalogService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.service_repository = ServiceRepository(db)
        self.user_repository = UserRepository(db)

    def create_service(
        self,
        tenant_id: uuid.UUID,
        payload: ServiceCreate,
        *,
        created_by_user_id: uuid.UUID | None = None,
    ) -> Service:
        self._validate_optional_user(tenant_id, created_by_user_id)
        normalized_name = normalize_service_name(payload.name)
        self._ensure_active_name_available(tenant_id, normalized_name)
        service = Service(
            tenant_id=tenant_id,
            normalized_name=normalized_name,
            created_by_user_id=created_by_user_id,
            **payload.model_dump(),
        )
        try:
            self.service_repository.create(service)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(
                409,
                "service_duplicate_name",
                "An active service with this name already exists",
            ) from exc
        return self.get_service(tenant_id, service.id)

    def list_services(
        self,
        tenant_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        bookable_only: bool = False,
    ) -> list[Service]:
        return self.service_repository.list(
            tenant_id,
            include_inactive=include_inactive,
            bookable_only=bookable_only,
        )

    def get_service(self, tenant_id: uuid.UUID, service_id: uuid.UUID) -> Service:
        service = self.service_repository.get_by_id(tenant_id, service_id)
        if service is None:
            raise AppError(404, "service_not_found", "Service not found")
        return service

    def update_service(
        self,
        tenant_id: uuid.UUID,
        service_id: uuid.UUID,
        payload: ServiceUpdate,
    ) -> Service:
        service = self.get_service(tenant_id, service_id)
        updates = payload.model_dump(exclude_unset=True)
        for field in ("code", "name", "kind", "default_duration_minutes", "calendar_color"):
            if field in updates and updates[field] is None:
                raise AppError(422, "validation_error", f"{field} cannot be null")

        if "name" in updates:
            normalized_name = normalize_service_name(updates["name"])
            if service.normalized_name != normalized_name or not service.is_active:
                self._ensure_active_name_available(
                    tenant_id,
                    normalized_name,
                    exclude_service_id=service.id,
                )
            updates["normalized_name"] = normalized_name

        try:
            updated_service = self.service_repository.update(service, updates)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(
                409,
                "service_duplicate_name",
                "An active service with this name already exists",
            ) from exc
        return self.get_service(tenant_id, updated_service.id)

    def activate_service(self, tenant_id: uuid.UUID, service_id: uuid.UUID) -> Service:
        service = self.get_service(tenant_id, service_id)
        self._ensure_active_name_available(
            tenant_id,
            service.normalized_name,
            exclude_service_id=service.id,
        )
        try:
            updated_service = self.service_repository.update(service, {"is_active": True})
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(
                409,
                "service_duplicate_name",
                "An active service with this name already exists",
            ) from exc
        return self.get_service(tenant_id, updated_service.id)

    def deactivate_service(self, tenant_id: uuid.UUID, service_id: uuid.UUID) -> Service:
        service = self.get_service(tenant_id, service_id)
        updated_service = self.service_repository.update(service, {"is_active": False})
        self.db.commit()
        return self.get_service(tenant_id, updated_service.id)

    def reorder_services(
        self,
        tenant_id: uuid.UUID,
        payload: ServiceReorderRequest,
    ) -> list[Service]:
        seen: set[uuid.UUID] = set()
        for item in payload.items:
            if item.id in seen:
                raise AppError(422, "validation_error", "Duplicate service id in reorder payload")
            seen.add(item.id)

        services: list[Service] = []
        for item in payload.items:
            service = self.get_service(tenant_id, item.id)
            services.append(self.service_repository.update(service, {"sort_order": item.sort_order}))

        self.db.commit()
        return self.list_services(tenant_id, include_inactive=True)

    def restore_defaults(self, tenant_id: uuid.UUID) -> list[Service]:
        for template in DEFAULT_SERVICE_TEMPLATES:
            normalized_name = normalize_service_name(str(template["name"]))
            existing = self.service_repository.get_by_normalized_name(
                tenant_id,
                normalized_name,
            )
            if existing is None:
                self.service_repository.create(
                    Service(
                        tenant_id=tenant_id,
                        normalized_name=normalized_name,
                        **template,
                    )
                )
            elif not existing.is_active:
                # Reactivate only: never overwrite fields the tenant may have already
                # customized before deactivating it.
                self.service_repository.update(existing, {"is_active": True})
        self.db.commit()
        return self.list_services(tenant_id, include_inactive=True)

    def _ensure_active_name_available(
        self,
        tenant_id: uuid.UUID,
        normalized_name: str,
        *,
        exclude_service_id: uuid.UUID | None = None,
    ) -> None:
        existing = self.service_repository.get_active_by_normalized_name(
            tenant_id,
            normalized_name,
        )
        if existing is not None and existing.id != exclude_service_id:
            raise AppError(
                409,
                "service_duplicate_name",
                "An active service with this name already exists",
            )

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


def normalize_service_name(value: str) -> str:
    return normalize_name(value)

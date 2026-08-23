import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.supplier import Supplier
from app.repositories.supplier import SupplierRepository
from app.schemas.supplier import SupplierCreate, SupplierUpdate
from app.services.normalization import normalize_name


class SupplierService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.supplier_repository = SupplierRepository(db)

    def create_supplier(
        self,
        tenant_id: uuid.UUID,
        payload: SupplierCreate,
        *,
        created_by_user_id: uuid.UUID | None = None,
    ) -> Supplier:
        normalized_name = normalize_name(payload.name)
        self._ensure_active_name_available(tenant_id, normalized_name)
        supplier = Supplier(
            tenant_id=tenant_id,
            normalized_name=normalized_name,
            created_by_user_id=created_by_user_id,
            **payload.model_dump(),
        )
        try:
            self.supplier_repository.create(supplier)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(
                409,
                "supplier_duplicate_name",
                "An active supplier with this name already exists",
            ) from exc
        return self.get_supplier(tenant_id, supplier.id)

    def list_suppliers(
        self,
        tenant_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> list[Supplier]:
        return self.supplier_repository.list(tenant_id, include_inactive=include_inactive)

    def get_supplier(self, tenant_id: uuid.UUID, supplier_id: uuid.UUID) -> Supplier:
        supplier = self.supplier_repository.get_by_id(tenant_id, supplier_id)
        if supplier is None:
            raise AppError(404, "supplier_not_found", "Supplier not found")
        return supplier

    def update_supplier(
        self,
        tenant_id: uuid.UUID,
        supplier_id: uuid.UUID,
        payload: SupplierUpdate,
    ) -> Supplier:
        supplier = self.get_supplier(tenant_id, supplier_id)
        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates and updates["name"] is None:
            raise AppError(422, "validation_error", "name cannot be null")

        if "name" in updates:
            normalized_name = normalize_name(updates["name"])
            if supplier.normalized_name != normalized_name or not supplier.is_active:
                self._ensure_active_name_available(
                    tenant_id,
                    normalized_name,
                    exclude_supplier_id=supplier.id,
                )
            updates["normalized_name"] = normalized_name

        try:
            updated_supplier = self.supplier_repository.update(supplier, updates)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(
                409,
                "supplier_duplicate_name",
                "An active supplier with this name already exists",
            ) from exc
        return self.get_supplier(tenant_id, updated_supplier.id)

    def activate_supplier(self, tenant_id: uuid.UUID, supplier_id: uuid.UUID) -> Supplier:
        supplier = self.get_supplier(tenant_id, supplier_id)
        self._ensure_active_name_available(
            tenant_id,
            supplier.normalized_name,
            exclude_supplier_id=supplier.id,
        )
        try:
            updated_supplier = self.supplier_repository.update(supplier, {"is_active": True})
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(
                409,
                "supplier_duplicate_name",
                "An active supplier with this name already exists",
            ) from exc
        return self.get_supplier(tenant_id, updated_supplier.id)

    def deactivate_supplier(self, tenant_id: uuid.UUID, supplier_id: uuid.UUID) -> Supplier:
        supplier = self.get_supplier(tenant_id, supplier_id)
        updated_supplier = self.supplier_repository.update(supplier, {"is_active": False})
        self.db.commit()
        return self.get_supplier(tenant_id, updated_supplier.id)

    def _ensure_active_name_available(
        self,
        tenant_id: uuid.UUID,
        normalized_name: str,
        *,
        exclude_supplier_id: uuid.UUID | None = None,
    ) -> None:
        existing = self.supplier_repository.get_active_by_normalized_name(
            tenant_id,
            normalized_name,
        )
        if existing is not None and existing.id != exclude_supplier_id:
            raise AppError(
                409,
                "supplier_duplicate_name",
                "An active supplier with this name already exists",
            )

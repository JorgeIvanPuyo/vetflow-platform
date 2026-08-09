from __future__ import annotations

import uuid
from datetime import UTC, datetime
from math import ceil

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.supplier import Supplier
from app.repositories.supplier import SupplierRepository
from app.repositories.user import UserRepository
from app.schemas.supplier import SupplierCreate, SupplierUpdate, normalize_name


class SupplierService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = SupplierRepository(db)
        self.user_repository = UserRepository(db)

    def create(
        self,
        tenant_id: uuid.UUID,
        payload: SupplierCreate,
        *,
        created_by_user_id: uuid.UUID | None,
    ) -> Supplier:
        self._validate_optional_user(tenant_id, created_by_user_id)
        normalized_name = normalize_name(payload.name)
        self._ensure_unique(tenant_id, normalized_name, payload.tax_id)
        supplier = Supplier(
            tenant_id=tenant_id,
            name=payload.name,
            normalized_name=normalized_name,
            tax_id=payload.tax_id,
            phone=payload.phone,
            email=payload.email,
            address=payload.address,
            notes=payload.notes,
            is_active=True,
            created_by_user_id=created_by_user_id,
        )
        try:
            self.repository.create(supplier)
            self.db.commit()
        except IntegrityError as exc:
            self._handle_integrity_error(exc)
        except Exception:
            self.db.rollback()
            raise
        return self.get(tenant_id, supplier.id)

    def get(self, tenant_id: uuid.UUID, supplier_id: uuid.UUID) -> Supplier:
        supplier = self.repository.get_by_id(tenant_id, supplier_id)
        if supplier is None:
            raise AppError(404, "supplier_not_found", "Proveedor no encontrado")
        return supplier

    def list(
        self,
        tenant_id: uuid.UUID,
        *,
        search: str | None,
        is_active: bool,
        page: int,
        page_size: int,
        sort_by: str,
        sort_direction: str,
    ) -> tuple[list[Supplier], dict]:
        rows, total = self.repository.list(
            tenant_id,
            search=search.strip() if search and search.strip() else None,
            is_active=is_active,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_direction=sort_direction,
        )
        return rows, {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": ceil(total / page_size) if total else 0,
        }

    def update(
        self, tenant_id: uuid.UUID, supplier_id: uuid.UUID, payload: SupplierUpdate
    ) -> Supplier:
        supplier = self.repository.get_by_id(tenant_id, supplier_id, for_update=True)
        if supplier is None:
            raise AppError(404, "supplier_not_found", "Proveedor no encontrado")
        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates:
            if updates["name"] is None:
                raise AppError(422, "validation_error", "name cannot be null")
            updates["normalized_name"] = normalize_name(updates["name"])
        if "is_active" in updates and updates["is_active"] is None:
            raise AppError(422, "validation_error", "is_active cannot be null")
        self._ensure_unique(
            tenant_id,
            updates.get("normalized_name", supplier.normalized_name),
            updates.get("tax_id", supplier.tax_id),
            exclude_id=supplier.id,
        )
        for field_name, value in updates.items():
            setattr(supplier, field_name, value)
        supplier.updated_at = datetime.now(UTC)
        self.db.add(supplier)
        self._commit_with_conflict_handling()
        return self.get(tenant_id, supplier_id)

    def _ensure_unique(
        self,
        tenant_id: uuid.UUID,
        normalized_name: str,
        tax_id: str | None,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        by_name = self.repository.get_by_normalized_name(tenant_id, normalized_name)
        if by_name is not None and by_name.id != exclude_id:
            raise AppError(
                409, "supplier_name_conflict", "Ya existe un proveedor con ese nombre"
            )
        if tax_id is not None:
            by_tax = self.repository.get_by_tax_id(tenant_id, tax_id)
            if by_tax is not None and by_tax.id != exclude_id:
                raise AppError(
                    409,
                    "supplier_tax_id_conflict",
                    "Ya existe un proveedor con esa identificación fiscal",
                )

    def _validate_optional_user(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID | None
    ) -> None:
        if user_id is not None and self.user_repository.get_by_id(tenant_id, user_id) is None:
            raise AppError(404, "user_not_found", "Usuario no encontrado")

    def _commit_with_conflict_handling(self) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self._handle_integrity_error(exc)
        except Exception:
            self.db.rollback()
            raise

    def _handle_integrity_error(self, exc: IntegrityError) -> None:
        self.db.rollback()
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", "")
        if constraint == "uq_suppliers_tenant_tax_id":
            raise AppError(
                409,
                "supplier_tax_id_conflict",
                "Ya existe un proveedor con esa identificación fiscal",
            ) from exc
        if constraint == "uq_suppliers_tenant_normalized_name":
            raise AppError(
                409,
                "supplier_name_conflict",
                "Ya existe un proveedor con ese nombre",
            ) from exc
        raise exc

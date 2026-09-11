import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context, require_clinic_admin
from app.db.session import get_db
from app.schemas.supplier import (
    SortDirection,
    SupplierCreate,
    SupplierRead,
    SupplierSortBy,
    SupplierSummaryRead,
    SupplierUpdate,
)
from app.services.supplier import SupplierService


router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    tenant: TenantContext = Depends(require_clinic_admin),
    db: Session = Depends(get_db),
) -> dict:
    supplier = SupplierService(db).create(
        tenant.tenant_id,
        payload,
        created_by_user_id=tenant.user_id,
    )
    return {
        "data": SupplierRead.model_validate(supplier).model_dump(mode="json"),
        "meta": {},
    }


@router.get("")
def list_suppliers(
    search: str | None = Query(default=None, max_length=255),
    is_active: bool | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: SupplierSortBy = Query(default="name"),
    sort_direction: SortDirection = Query(default="asc"),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    effective_is_active = is_active
    if effective_is_active is None and not include_inactive:
        effective_is_active = True

    suppliers, meta = SupplierService(db).list(
        tenant.tenant_id,
        search=search,
        is_active=effective_is_active,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_direction=sort_direction,
    )
    return {
        "data": [
            SupplierSummaryRead.model_validate(supplier).model_dump(mode="json")
            for supplier in suppliers
        ],
        "meta": meta,
    }


@router.get("/{supplier_id}")
def get_supplier(
    supplier_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    supplier = SupplierService(db).get(tenant.tenant_id, supplier_id)
    return {
        "data": SupplierRead.model_validate(supplier).model_dump(mode="json"),
        "meta": {},
    }


@router.patch("/{supplier_id}")
def update_supplier(
    supplier_id: uuid.UUID,
    payload: SupplierUpdate,
    tenant: TenantContext = Depends(require_clinic_admin),
    db: Session = Depends(get_db),
) -> dict:
    supplier = SupplierService(db).update(tenant.tenant_id, supplier_id, payload)
    return {
        "data": SupplierRead.model_validate(supplier).model_dump(mode="json"),
        "meta": {},
    }


@router.post("/{supplier_id}/activate")
def activate_supplier(
    supplier_id: uuid.UUID,
    tenant: TenantContext = Depends(require_clinic_admin),
    db: Session = Depends(get_db),
) -> dict:
    supplier = SupplierService(db).set_active(tenant.tenant_id, supplier_id, True)
    return {
        "data": SupplierRead.model_validate(supplier).model_dump(mode="json"),
        "meta": {},
    }


@router.post("/{supplier_id}/deactivate")
def deactivate_supplier(
    supplier_id: uuid.UUID,
    tenant: TenantContext = Depends(require_clinic_admin),
    db: Session = Depends(get_db),
) -> dict:
    supplier = SupplierService(db).set_active(tenant.tenant_id, supplier_id, False)
    return {
        "data": SupplierRead.model_validate(supplier).model_dump(mode="json"),
        "meta": {},
    }

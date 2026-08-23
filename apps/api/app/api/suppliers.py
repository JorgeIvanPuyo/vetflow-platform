import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context, require_clinic_admin
from app.db.session import get_db
from app.schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate
from app.services.supplier import SupplierService

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("")
def list_suppliers(
    include_inactive: bool = Query(default=False),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    suppliers = SupplierService(db).list_suppliers(
        tenant.tenant_id,
        include_inactive=include_inactive,
    )
    return {
        "data": [
            SupplierRead.model_validate(supplier).model_dump(mode="json")
            for supplier in suppliers
        ],
        "meta": {},
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    tenant: TenantContext = Depends(require_clinic_admin),
    db: Session = Depends(get_db),
) -> dict:
    supplier = SupplierService(db).create_supplier(
        tenant.tenant_id,
        payload,
        created_by_user_id=tenant.user_id,
    )
    return {
        "data": SupplierRead.model_validate(supplier).model_dump(mode="json"),
        "meta": {},
    }


@router.get("/{supplier_id}")
def get_supplier(
    supplier_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    supplier = SupplierService(db).get_supplier(tenant.tenant_id, supplier_id)
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
    supplier = SupplierService(db).update_supplier(
        tenant.tenant_id,
        supplier_id,
        payload,
    )
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
    supplier = SupplierService(db).activate_supplier(tenant.tenant_id, supplier_id)
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
    supplier = SupplierService(db).deactivate_supplier(tenant.tenant_id, supplier_id)
    return {
        "data": SupplierRead.model_validate(supplier).model_dump(mode="json"),
        "meta": {},
    }

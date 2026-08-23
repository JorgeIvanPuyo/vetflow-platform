import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context, require_clinic_admin
from app.db.session import get_db
from app.schemas.catalog_item import (
    CatalogItemCreate,
    CatalogItemRead,
    CatalogItemReorderRequest,
    CatalogItemUpdate,
)
from app.services.catalog_items import CatalogItemService

router = APIRouter(prefix="/clinic/catalogs", tags=["clinic-catalogs"])


@router.get("/{catalog_type}")
def list_catalog_items(
    catalog_type: str,
    include_inactive: bool = Query(default=False),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    items = CatalogItemService(db).list_items(
        tenant.tenant_id,
        catalog_type,
        include_inactive=include_inactive,
    )
    return {
        "data": [
            CatalogItemRead.model_validate(item).model_dump(mode="json")
            for item in items
        ],
        "meta": {},
    }


@router.post("/{catalog_type}", status_code=status.HTTP_201_CREATED)
def create_catalog_item(
    catalog_type: str,
    payload: CatalogItemCreate,
    tenant: TenantContext = Depends(require_clinic_admin),
    db: Session = Depends(get_db),
) -> dict:
    item = CatalogItemService(db).create_item(
        tenant.tenant_id,
        catalog_type,
        payload,
        created_by_user_id=tenant.user_id,
    )
    return {
        "data": CatalogItemRead.model_validate(item).model_dump(mode="json"),
        "meta": {},
    }


@router.patch("/{catalog_type}/reorder")
def reorder_catalog_items(
    catalog_type: str,
    payload: CatalogItemReorderRequest,
    tenant: TenantContext = Depends(require_clinic_admin),
    db: Session = Depends(get_db),
) -> dict:
    items = CatalogItemService(db).reorder_items(
        tenant.tenant_id,
        catalog_type,
        payload,
    )
    return {
        "data": [
            CatalogItemRead.model_validate(item).model_dump(mode="json")
            for item in items
        ],
        "meta": {},
    }


@router.patch("/{catalog_type}/{item_id}")
def update_catalog_item(
    catalog_type: str,
    item_id: uuid.UUID,
    payload: CatalogItemUpdate,
    tenant: TenantContext = Depends(require_clinic_admin),
    db: Session = Depends(get_db),
) -> dict:
    item = CatalogItemService(db).update_item(
        tenant.tenant_id,
        catalog_type,
        item_id,
        payload,
    )
    return {
        "data": CatalogItemRead.model_validate(item).model_dump(mode="json"),
        "meta": {},
    }


@router.post("/{catalog_type}/{item_id}/activate")
def activate_catalog_item(
    catalog_type: str,
    item_id: uuid.UUID,
    tenant: TenantContext = Depends(require_clinic_admin),
    db: Session = Depends(get_db),
) -> dict:
    item = CatalogItemService(db).activate_item(tenant.tenant_id, catalog_type, item_id)
    return {
        "data": CatalogItemRead.model_validate(item).model_dump(mode="json"),
        "meta": {},
    }


@router.post("/{catalog_type}/{item_id}/deactivate")
def deactivate_catalog_item(
    catalog_type: str,
    item_id: uuid.UUID,
    tenant: TenantContext = Depends(require_clinic_admin),
    db: Session = Depends(get_db),
) -> dict:
    item = CatalogItemService(db).deactivate_item(
        tenant.tenant_id,
        catalog_type,
        item_id,
    )
    return {
        "data": CatalogItemRead.model_validate(item).model_dump(mode="json"),
        "meta": {},
    }

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.inventory import (
    InventoryCategory,
    InventoryFilterOptionsRead,
    InventoryItemCreate,
    InventoryItemRead,
    InventoryItemUpdate,
    InventoryMovementEntryCreate,
    InventoryMovementRead,
    InventoryMovementType,
    InventoryMovementExitCreate,
    InventorySortBy,
    InventoryStockStatus,
    InventoryStatusFilter,
    InventorySummaryRead,
)
from app.services.inventory import InventoryService

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.post("/items", status_code=status.HTTP_201_CREATED)
def create_inventory_item(
    payload: InventoryItemCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    item = InventoryService(db).create_item(
        tenant.tenant_id,
        payload,
        created_by_user_id=tenant.user_id,
    )
    return {"data": InventoryItemRead.model_validate(item).model_dump(mode="json"), "meta": {}}


@router.get("/items")
def list_inventory_items(
    search: str | None = Query(default=None),
    q: str | None = Query(default=None),
    category: InventoryCategory | None = Query(default=None),
    brand: str | None = Query(default=None),
    supplier: str | None = Query(default=None),
    status_filter: InventoryStatusFilter | None = Query(default=None, alias="status"),
    stock_status: InventoryStockStatus | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    sort_by: InventorySortBy | None = Query(default=None),
    sort_direction: str | None = Query(default=None),
    sort_order: str | None = Query(default=None),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    items, meta = InventoryService(db).list_items(
        tenant.tenant_id,
        search=search if search is not None else q,
        category=category,
        brand=brand,
        supplier=supplier,
        status=status_filter,
        stock_status=stock_status,
        is_active=is_active,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_direction=_prefer_current_parameter(sort_direction, sort_order),
    )
    return {
        "data": [InventoryItemRead.model_validate(item).model_dump(mode="json") for item in items],
        "meta": meta,
    }


def _prefer_current_parameter(current_value: str | None, legacy_value: str | None) -> str | None:
    if current_value is not None and current_value.strip():
        return current_value.strip()
    if current_value is not None:
        return None
    if legacy_value is not None and legacy_value.strip():
        return legacy_value.strip()
    return None


@router.get("/filter-options")
def get_inventory_filter_options(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    options = InventoryService(db).get_filter_options(tenant.tenant_id)
    return {
        "data": InventoryFilterOptionsRead.model_validate(options).model_dump(mode="json"),
        "meta": {},
    }


@router.get("/summary")
def get_inventory_summary(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    summary = InventoryService(db).get_summary(tenant.tenant_id)
    return {
        "data": InventorySummaryRead.model_validate(summary).model_dump(mode="json"),
        "meta": {},
    }


@router.get("/items/{item_id}")
def get_inventory_item(
    item_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    item = InventoryService(db).get_item(tenant.tenant_id, item_id)
    return {"data": InventoryItemRead.model_validate(item).model_dump(mode="json"), "meta": {}}


@router.patch("/items/{item_id}")
def update_inventory_item(
    item_id: uuid.UUID,
    payload: InventoryItemUpdate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    item = InventoryService(db).update_item(tenant.tenant_id, item_id, payload)
    return {"data": InventoryItemRead.model_validate(item).model_dump(mode="json"), "meta": {}}


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inventory_item(
    item_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> Response:
    InventoryService(db).delete_item(tenant.tenant_id, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/items/{item_id}/movements/entry", status_code=status.HTTP_201_CREATED)
def register_entry_movement(
    item_id: uuid.UUID,
    payload: InventoryMovementEntryCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    movement = InventoryService(db).register_entry_movement(
        tenant.tenant_id,
        item_id,
        payload,
        created_by_user_id=tenant.user_id,
    )
    return {
        "data": InventoryMovementRead.model_validate(movement).model_dump(mode="json"),
        "meta": {},
    }


@router.post("/items/{item_id}/movements/exit", status_code=status.HTTP_201_CREATED)
def register_exit_movement(
    item_id: uuid.UUID,
    payload: InventoryMovementExitCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    movement = InventoryService(db).register_exit_movement(
        tenant.tenant_id,
        item_id,
        payload,
        created_by_user_id=tenant.user_id,
    )
    return {
        "data": InventoryMovementRead.model_validate(movement).model_dump(mode="json"),
        "meta": {},
    }


@router.get("/items/{item_id}/movements")
def list_item_movements(
    item_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    movement_type: InventoryMovementType | None = Query(default=None),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    movements, meta = InventoryService(db).list_movements(
        tenant.tenant_id,
        item_id,
        page=page,
        page_size=page_size,
        movement_type=movement_type,
    )
    return {
        "data": [
            InventoryMovementRead.model_validate(movement).model_dump(mode="json")
            for movement in movements
        ],
        "meta": meta,
    }

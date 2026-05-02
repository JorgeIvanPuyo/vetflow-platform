import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.inventory import (
    InventoryCategory,
    InventoryItemCreate,
    InventoryItemRead,
    InventoryItemUpdate,
    InventoryMovementEntryCreate,
    InventoryMovementRead,
    InventoryMovementType,
    InventoryMovementExitCreate,
    InventorySortBy,
    InventoryStatusFilter,
    InventorySummaryRead,
    SortOrder,
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
    q: str | None = Query(default=None),
    category: InventoryCategory | None = Query(default=None),
    supplier: str | None = Query(default=None),
    status_filter: InventoryStatusFilter | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    sort_by: InventorySortBy | None = Query(default=None),
    sort_order: SortOrder | None = Query(default=None),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    items, meta = InventoryService(db).list_items(
        tenant.tenant_id,
        q=q,
        category=category,
        supplier=supplier,
        status=status_filter,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return {
        "data": [InventoryItemRead.model_validate(item).model_dump(mode="json") for item in items],
        "meta": meta,
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

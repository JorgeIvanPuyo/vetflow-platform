import uuid
from datetime import date, datetime
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.inventory import (
    InventoryBulkOperationConfirmCreate,
    InventoryBulkOperationListItemRead,
    InventoryBulkOperationPreviewCreate,
    InventoryBulkOperationRead,
    InventoryBulkOperationReverseCreate,
    InventoryBulkOperationStatus,
    InventoryBulkOperationType,
    InventoryCategory,
    InventoryExportCreate,
    InventoryFilterOptionsRead,
    InventoryImportConfirmCreate,
    InventoryImportListItemRead,
    InventoryImportMode,
    InventoryImportRead,
    InventoryItemCreate,
    InventoryItemRead,
    InventoryItemUpdate,
    InventoryMovementDetailRead,
    InventoryMovementEntryCreate,
    InventoryMovementRead,
    InventoryMovementReverseCreate,
    InventoryReversalStatus,
    InventoryMovementType,
    InventoryMovementExitCreate,
    InventorySortBy,
    InventoryStockStatus,
    InventoryStatusFilter,
    InventorySummaryRead,
)
from app.services.inventory_bulk_operation import InventoryBulkOperationService
from app.services.inventory_export import InventoryExportService, XLSX_MEDIA_TYPE
from app.services.inventory import InventoryService
from app.services.inventory_import import InventoryImportService

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


@router.post("/export")
def export_inventory(
    payload: InventoryExportCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    export_file = InventoryExportService(db).export_inventory(tenant, payload)
    return StreamingResponse(
        BytesIO(export_file.content),
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{export_file.filename}"',
        },
    )


@router.post("/bulk-operations/preview", status_code=status.HTTP_201_CREATED)
def preview_inventory_bulk_operation(
    payload: InventoryBulkOperationPreviewCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    operation = InventoryBulkOperationService(db).preview_operation(tenant, payload)
    return {
        "data": InventoryBulkOperationRead.model_validate(operation).model_dump(mode="json"),
        "meta": getattr(operation, "items_meta", {}),
    }


@router.get("/bulk-operations")
def list_inventory_bulk_operations(
    status_filter: InventoryBulkOperationStatus | None = Query(default=None, alias="status"),
    operation_type: InventoryBulkOperationType | None = Query(default=None),
    created_by_user_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    date_from_dt = datetime.combine(date_from, datetime.min.time()) if date_from else None
    date_to_dt = datetime.combine(date_to, datetime.max.time()) if date_to else None
    operations, meta = InventoryBulkOperationService(db).list_operations(
        tenant.tenant_id,
        status=status_filter,
        operation_type=operation_type,
        created_by_user_id=created_by_user_id,
        date_from=date_from_dt,
        date_to=date_to_dt,
        page=page,
        page_size=page_size,
    )
    return {
        "data": [
            InventoryBulkOperationListItemRead.model_validate(operation).model_dump(mode="json")
            for operation in operations
        ],
        "meta": meta,
    }


@router.get("/bulk-operations/{operation_id}")
def get_inventory_bulk_operation(
    operation_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    row_status: str | None = Query(default=None),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    operation = InventoryBulkOperationService(db).get_operation(
        tenant.tenant_id,
        operation_id,
        page=page,
        page_size=page_size,
        status=row_status,
    )
    return {
        "data": InventoryBulkOperationRead.model_validate(operation).model_dump(mode="json"),
        "meta": getattr(operation, "items_meta", {}),
    }


@router.post("/bulk-operations/{operation_id}/confirm")
def confirm_inventory_bulk_operation(
    operation_id: uuid.UUID,
    payload: InventoryBulkOperationConfirmCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    operation = InventoryBulkOperationService(db).confirm_operation(
        tenant,
        operation_id,
        payload,
    )
    return {
        "data": InventoryBulkOperationRead.model_validate(operation).model_dump(mode="json"),
        "meta": getattr(operation, "items_meta", {}),
    }


@router.post("/bulk-operations/{operation_id}/reverse")
def reverse_inventory_bulk_operation(
    operation_id: uuid.UUID,
    payload: InventoryBulkOperationReverseCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    operation = InventoryBulkOperationService(db).reverse_operation(
        tenant,
        operation_id,
        payload,
    )
    return {
        "data": InventoryBulkOperationRead.model_validate(operation).model_dump(mode="json"),
        "meta": getattr(operation, "items_meta", {}),
    }


@router.get("/import/template")
def download_inventory_import_template(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    _ = tenant
    content = InventoryImportService(db).build_template()
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="vetflow_inventory_template.xlsx"',
        },
    )


@router.post("/import/preview", status_code=status.HTTP_201_CREATED)
async def preview_inventory_import(
    mode: InventoryImportMode = Form(...),
    file: UploadFile = File(...),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    inventory_import = await InventoryImportService(db).preview_import(
        tenant.tenant_id,
        mode=mode,
        upload_file=file,
        created_by_user_id=tenant.user_id,
    )
    return {
        "data": InventoryImportRead.model_validate(inventory_import).model_dump(mode="json"),
        "meta": {},
    }


@router.get("/imports")
def list_inventory_imports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    imports, meta = InventoryImportService(db).list_imports(
        tenant.tenant_id,
        page=page,
        page_size=page_size,
    )
    return {
        "data": [
            InventoryImportListItemRead.model_validate(inventory_import).model_dump(mode="json")
            for inventory_import in imports
        ],
        "meta": meta,
    }


@router.get("/import/{import_id}")
def get_inventory_import(
    import_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    inventory_import = InventoryImportService(db).get_import(tenant.tenant_id, import_id)
    return {
        "data": InventoryImportRead.model_validate(inventory_import).model_dump(mode="json"),
        "meta": {},
    }


@router.get("/import/{import_id}/result")
def get_inventory_import_result(
    import_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    inventory_import = InventoryImportService(db).get_import(tenant.tenant_id, import_id)
    return {
        "data": InventoryImportRead.model_validate(inventory_import).model_dump(mode="json"),
        "meta": {},
    }


@router.post("/import/{import_id}/confirm")
def confirm_inventory_import(
    import_id: uuid.UUID,
    payload: InventoryImportConfirmCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    inventory_import = InventoryImportService(db).confirm_import(
        tenant.tenant_id,
        import_id,
        payload,
        created_by_user_id=tenant.user_id,
    )
    return {
        "data": InventoryImportRead.model_validate(inventory_import).model_dump(mode="json"),
        "meta": {},
    }


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


@router.get("/movements")
def list_inventory_movements(
    search: str | None = Query(default=None),
    inventory_item_id: uuid.UUID | None = Query(default=None),
    movement_type: InventoryMovementType | None = Query(default=None),
    created_by_user_id: uuid.UUID | None = Query(default=None),
    source_type: str | None = Query(default=None),
    source_id: str | None = Query(default=None),
    operation_id: uuid.UUID | None = Query(default=None),
    reversal_status: InventoryReversalStatus = Query(default="all"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_direction: str = Query(default="desc"),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    movements, meta = InventoryService(db).list_movements(
        tenant.tenant_id,
        item_id=inventory_item_id,
        search=search,
        movement_type=movement_type,
        created_by_user_id=created_by_user_id,
        source_type=source_type,
        source_id=source_id,
        operation_id=operation_id,
        reversal_status=reversal_status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
        sort_direction=sort_direction,
    )
    return {
        "data": [
            InventoryMovementRead.model_validate(movement).model_dump(mode="json")
            for movement in movements
        ],
        "meta": meta,
    }


@router.get("/movements/{movement_id}")
def get_inventory_movement(
    movement_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    service = InventoryService(db)
    movement = service.get_movement(tenant.tenant_id, movement_id)
    can_be_reversed, reversal_block_reason = service.get_movement_reversal_status(movement)
    data = InventoryMovementRead.model_validate(movement).model_dump(mode="json")
    data["can_be_reversed"] = can_be_reversed
    data["reversal_block_reason"] = reversal_block_reason
    return {
        "data": InventoryMovementDetailRead.model_validate(data).model_dump(mode="json"),
        "meta": {},
    }


@router.post("/movements/{movement_id}/reverse", status_code=status.HTTP_201_CREATED)
def reverse_inventory_movement(
    movement_id: uuid.UUID,
    payload: InventoryMovementReverseCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    movement = InventoryService(db).reverse_movement(
        tenant.tenant_id,
        movement_id,
        payload,
        created_by_user_id=tenant.user_id,
    )
    return {
        "data": InventoryMovementRead.model_validate(movement).model_dump(mode="json"),
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
        item_id=item_id,
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

import uuid
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.purchase import (
    PurchaseCancel,
    PurchaseAttachmentRead,
    PurchaseAttachmentStatus,
    PurchaseCreate,
    PurchaseDetailRead,
    PurchaseDocumentType,
    PurchaseFunctionalStatus,
    PurchaseReceive,
    PurchaseReverseReceipt,
    PurchaseSortBy,
    PurchaseSummaryRead,
    PurchaseUpdate,
    SortDirection,
)
from app.services.purchase import PurchaseService
from app.services.purchase_attachment import (
    MAX_PURCHASE_ATTACHMENT_SIZE_BYTES,
    PurchaseAttachmentService,
)
from app.services.storage import (
    ObjectStorageService,
    get_purchase_attachment_storage_service,
)


router = APIRouter(prefix="/purchases", tags=["purchases"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_purchase(
    payload: PurchaseCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    purchase = PurchaseService(db).create(
        tenant.tenant_id, payload, created_by_user_id=tenant.user_id
    )
    return {"data": PurchaseDetailRead.model_validate(purchase).model_dump(mode="json"), "meta": {}}


@router.get("")
def list_purchases(
    search: str | None = Query(default=None, max_length=255),
    supplier: str | None = Query(default=None, max_length=255),
    supplier_id: uuid.UUID | None = Query(default=None),
    status_filter: PurchaseFunctionalStatus | None = Query(default=None, alias="status"),
    document_type: PurchaseDocumentType | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    created_by_user_id: uuid.UUID | None = Query(default=None),
    attachment_status: PurchaseAttachmentStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: PurchaseSortBy = Query(default="purchase_date"),
    sort_direction: SortDirection = Query(default="desc"),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    purchases, meta = PurchaseService(db).list(
        tenant.tenant_id,
        search=search,
        supplier=supplier,
        supplier_id=supplier_id,
        status=status_filter,
        document_type=document_type,
        date_from=date_from,
        date_to=date_to,
        created_by_user_id=created_by_user_id,
        attachment_status=attachment_status,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_direction=sort_direction,
    )
    return {
        "data": [PurchaseSummaryRead.model_validate(item).model_dump(mode="json") for item in purchases],
        "meta": meta,
    }


@router.get("/{purchase_id}")
def get_purchase(
    purchase_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    purchase = PurchaseService(db).get(tenant.tenant_id, purchase_id)
    return {"data": PurchaseDetailRead.model_validate(purchase).model_dump(mode="json"), "meta": {}}


@router.patch("/{purchase_id}")
def update_purchase(
    purchase_id: uuid.UUID,
    payload: PurchaseUpdate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    purchase = PurchaseService(db).update(tenant.tenant_id, purchase_id, payload)
    return {"data": PurchaseDetailRead.model_validate(purchase).model_dump(mode="json"), "meta": {}}


@router.post("/{purchase_id}/cancel")
def cancel_purchase(
    purchase_id: uuid.UUID,
    payload: PurchaseCancel,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    purchase = PurchaseService(db).cancel(
        tenant.tenant_id,
        purchase_id,
        payload,
        cancelled_by_user_id=tenant.user_id,
    )
    return {"data": PurchaseDetailRead.model_validate(purchase).model_dump(mode="json"), "meta": {}}


@router.post("/{purchase_id}/receive")
def receive_purchase(
    purchase_id: uuid.UUID,
    _: PurchaseReceive,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    purchase = PurchaseService(db).receive(
        tenant.tenant_id,
        purchase_id,
        received_by_user_id=tenant.user_id,
    )
    return {"data": PurchaseDetailRead.model_validate(purchase).model_dump(mode="json"), "meta": {}}


@router.post("/{purchase_id}/reverse-receipt")
def reverse_purchase_receipt(
    purchase_id: uuid.UUID,
    payload: PurchaseReverseReceipt,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    purchase = PurchaseService(db).reverse_receipt(
        tenant.tenant_id,
        purchase_id,
        reason=payload.reason,
        reversed_by_user_id=tenant.user_id,
    )
    return {"data": PurchaseDetailRead.model_validate(purchase).model_dump(mode="json"), "meta": {}}


@router.post("/{purchase_id}/attachment")
async def attach_purchase_document(
    purchase_id: uuid.UUID,
    file: UploadFile = File(...),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    storage: ObjectStorageService = Depends(get_purchase_attachment_storage_service),
) -> dict:
    content = await file.read(MAX_PURCHASE_ATTACHMENT_SIZE_BYTES + 1)
    attachment, idempotent = PurchaseAttachmentService(db, storage).attach(
        tenant.tenant_id,
        purchase_id,
        filename=file.filename,
        declared_content_type=file.content_type,
        content=content,
        uploaded_by_user_id=tenant.user_id,
    )
    return {
        "data": PurchaseAttachmentRead.model_validate(attachment).model_dump(mode="json"),
        "meta": {"attachment_status": "attached", "idempotent": idempotent},
    }


@router.get("/{purchase_id}/attachment")
def download_purchase_document(
    purchase_id: uuid.UUID,
    download: bool = Query(default=False),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    storage: ObjectStorageService = Depends(get_purchase_attachment_storage_service),
) -> Response:
    attachment, content = PurchaseAttachmentService(db, storage).download(
        tenant.tenant_id, purchase_id
    )
    disposition = "attachment" if download else "inline"
    encoded_filename = quote(attachment.original_filename, safe="")
    return Response(
        content=content,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": (
                f"{disposition}; filename=\"document\"; "
                f"filename*=UTF-8''{encoded_filename}"
            ),
            "Content-Length": str(len(content)),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )

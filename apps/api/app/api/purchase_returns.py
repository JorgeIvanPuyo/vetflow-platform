import uuid
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.purchase import PurchaseAttachmentStatus
from app.schemas.purchase_return import (
    PurchaseReturnAttachmentRead,
    PurchaseReturnCancel,
    PurchaseReturnConfirm,
    PurchaseReturnCreate,
    PurchaseReturnDetailRead,
    PurchaseReturnSortBy,
    PurchaseReturnSortDirection,
    PurchaseReturnStatus,
    PurchaseReturnSummaryRead,
    PurchaseReturnUpdate,
)
from app.services.purchase_return import PurchaseReturnService
from app.services.purchase_return_attachment import (
    MAX_PURCHASE_RETURN_ATTACHMENT_SIZE_BYTES,
    PurchaseReturnAttachmentService,
)
from app.services.storage import (
    ObjectStorageService,
    get_purchase_attachment_storage_service,
)


router = APIRouter(tags=["purchase-returns"])


@router.post(
    "/purchases/{purchase_id}/returns", status_code=status.HTTP_201_CREATED
)
def create_purchase_return(
    purchase_id: uuid.UUID,
    payload: PurchaseReturnCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    purchase_return = PurchaseReturnService(db).create(
        tenant.tenant_id,
        purchase_id,
        payload,
        created_by_user_id=tenant.user_id,
    )
    return {
        "data": PurchaseReturnDetailRead.model_validate(purchase_return).model_dump(
            mode="json"
        ),
        "meta": {},
    }


@router.get("/purchase-returns")
def list_purchase_returns(
    search: str | None = Query(default=None, max_length=255),
    supplier_id: uuid.UUID | None = Query(default=None),
    purchase_id: uuid.UUID | None = Query(default=None),
    status_filter: PurchaseReturnStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    created_by_user_id: uuid.UUID | None = Query(default=None),
    attachment_status: PurchaseAttachmentStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: PurchaseReturnSortBy = Query(default="return_date"),
    sort_direction: PurchaseReturnSortDirection = Query(default="desc"),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    returns, meta = PurchaseReturnService(db).list(
        tenant.tenant_id,
        search=search,
        supplier_id=supplier_id,
        purchase_id=purchase_id,
        status=status_filter,
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
        "data": [
            PurchaseReturnSummaryRead.model_validate(item).model_dump(mode="json")
            for item in returns
        ],
        "meta": meta,
    }


@router.get("/purchase-returns/{return_id}")
def get_purchase_return(
    return_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    purchase_return = PurchaseReturnService(db).get(tenant.tenant_id, return_id)
    return {
        "data": PurchaseReturnDetailRead.model_validate(purchase_return).model_dump(
            mode="json"
        ),
        "meta": {},
    }


@router.patch("/purchase-returns/{return_id}")
def update_purchase_return(
    return_id: uuid.UUID,
    payload: PurchaseReturnUpdate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    purchase_return = PurchaseReturnService(db).update(
        tenant.tenant_id, return_id, payload
    )
    return {
        "data": PurchaseReturnDetailRead.model_validate(purchase_return).model_dump(
            mode="json"
        ),
        "meta": {},
    }


@router.post("/purchase-returns/{return_id}/cancel")
def cancel_purchase_return(
    return_id: uuid.UUID,
    payload: PurchaseReturnCancel,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    purchase_return = PurchaseReturnService(db).cancel(
        tenant.tenant_id,
        return_id,
        reason=payload.reason,
        cancelled_by_user_id=tenant.user_id,
    )
    return {
        "data": PurchaseReturnDetailRead.model_validate(purchase_return).model_dump(
            mode="json"
        ),
        "meta": {},
    }


@router.post("/purchase-returns/{return_id}/confirm")
def confirm_purchase_return(
    return_id: uuid.UUID,
    _: PurchaseReturnConfirm,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    purchase_return = PurchaseReturnService(db).confirm(
        tenant.tenant_id,
        return_id,
        confirmed_by_user_id=tenant.user_id,
    )
    return {
        "data": PurchaseReturnDetailRead.model_validate(purchase_return).model_dump(
            mode="json"
        ),
        "meta": {},
    }


@router.post("/purchase-returns/{return_id}/attachment")
async def attach_purchase_return_document(
    return_id: uuid.UUID,
    file: UploadFile = File(...),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    storage: ObjectStorageService = Depends(get_purchase_attachment_storage_service),
) -> dict:
    content = await file.read(MAX_PURCHASE_RETURN_ATTACHMENT_SIZE_BYTES + 1)
    attachment, idempotent = PurchaseReturnAttachmentService(db, storage).attach(
        tenant.tenant_id,
        return_id,
        filename=file.filename,
        declared_content_type=file.content_type,
        content=content,
        uploaded_by_user_id=tenant.user_id,
    )
    return {
        "data": PurchaseReturnAttachmentRead.model_validate(attachment).model_dump(
            mode="json"
        ),
        "meta": {"attachment_status": "attached", "idempotent": idempotent},
    }


@router.get("/purchase-returns/{return_id}/attachment")
def download_purchase_return_document(
    return_id: uuid.UUID,
    download: bool = Query(default=False),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    storage: ObjectStorageService = Depends(get_purchase_attachment_storage_service),
) -> Response:
    attachment, content = PurchaseReturnAttachmentService(db, storage).download(
        tenant.tenant_id, return_id
    )
    disposition = "attachment" if download else "inline"
    encoded_filename = quote(attachment.original_filename, safe="")
    return Response(
        content=content,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": (
                f'{disposition}; filename="document"; '
                f"filename*=UTF-8''{encoded_filename}"
            ),
            "Content-Length": str(len(content)),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )

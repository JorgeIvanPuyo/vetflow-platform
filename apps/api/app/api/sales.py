import uuid
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.sale import (
    SaleCancel,
    SaleConfirm,
    SaleCreate,
    SaleDetailRead,
    SaleLineType,
    SaleReverse,
    SaleSortBy,
    SaleSortDirection,
    SaleStatus,
    SaleSummaryRead,
    SaleUpdate,
)
from app.schemas.sale_fiscal import FiscalStatus, SaleFiscalDocumentRead
from app.schemas.payment import PaymentStatus
from app.services.purchase_attachment import MAX_PURCHASE_ATTACHMENT_SIZE_BYTES
from app.services.sale import SaleService
from app.services.sale_fiscal_document import SaleFiscalDocumentService
from app.services.storage import (
    ObjectStorageService,
    get_purchase_attachment_storage_service,
)


router = APIRouter(prefix="/sales", tags=["sales"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_sale(payload: SaleCreate, tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> dict:
    sale = SaleService(db).create(tenant.tenant_id, payload, created_by_user_id=tenant.user_id)
    return {"data": SaleDetailRead.model_validate(sale).model_dump(mode="json"), "meta": {}}


@router.get("/filter-options")
def sale_filter_options(tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> dict:
    users = SaleService(db).list_creators(tenant.tenant_id)
    return {"data": {"creators": [{"id": user.id, "full_name": user.full_name, "email": user.email, "is_active": user.is_active} for user in users]}, "meta": {}}


@router.get("")
def list_sales(
    search: str | None = Query(default=None, max_length=255),
    owner_id: uuid.UUID | None = Query(default=None),
    patient_id: uuid.UUID | None = Query(default=None),
    sale_status: SaleStatus | None = Query(default=None, alias="status"),
    line_type: SaleLineType | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    created_by_user_id: uuid.UUID | None = Query(default=None),
    fiscal_status: FiscalStatus | None = Query(default=None),
    payment_status: PaymentStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: SaleSortBy = Query(default="sale_date"),
    sort_direction: SaleSortDirection = Query(default="desc"),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    sales, meta = SaleService(db).list(
        tenant.tenant_id,
        search=search.strip() if search and search.strip() else None,
        owner_id=owner_id, patient_id=patient_id, status=sale_status, line_type=line_type,
        date_from=date_from, date_to=date_to, created_by_user_id=created_by_user_id,
        fiscal_status=fiscal_status,
        payment_status=payment_status,
        page=page, page_size=page_size, sort_by=sort_by, sort_direction=sort_direction,
    )
    return {"data": [SaleSummaryRead.model_validate(item).model_dump(mode="json") for item in sales], "meta": meta}


@router.get("/{sale_id}")
def get_sale(sale_id: uuid.UUID, tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> dict:
    sale = SaleService(db).get(tenant.tenant_id, sale_id)
    return {"data": SaleDetailRead.model_validate(sale).model_dump(mode="json"), "meta": {}}


@router.patch("/{sale_id}")
def update_sale(sale_id: uuid.UUID, payload: SaleUpdate, tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> dict:
    sale = SaleService(db).update(tenant.tenant_id, sale_id, payload)
    return {"data": SaleDetailRead.model_validate(sale).model_dump(mode="json"), "meta": {}}


@router.post("/{sale_id}/cancel")
def cancel_sale(sale_id: uuid.UUID, payload: SaleCancel, tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> dict:
    sale = SaleService(db).cancel(tenant.tenant_id, sale_id, reason=payload.reason, cancelled_by_user_id=tenant.user_id)
    return {"data": SaleDetailRead.model_validate(sale).model_dump(mode="json"), "meta": {}}


@router.post("/{sale_id}/confirm")
def confirm_sale(
    sale_id: uuid.UUID,
    payload: SaleConfirm,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    sale = SaleService(db).confirm(
        tenant.tenant_id,
        sale_id,
        confirmed_by_user_id=tenant.user_id,
    )
    return {"data": SaleDetailRead.model_validate(sale).model_dump(mode="json"), "meta": {}}


@router.post("/{sale_id}/reverse")
def reverse_sale(
    sale_id: uuid.UUID,
    payload: SaleReverse,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    sale = SaleService(db).reverse(
        tenant.tenant_id,
        sale_id,
        reason=payload.reason,
        reversed_by_user_id=tenant.user_id,
    )
    return {"data": SaleDetailRead.model_validate(sale).model_dump(mode="json"), "meta": {}}


@router.post("/{sale_id}/fiscal-document", status_code=status.HTTP_201_CREATED)
async def create_sale_fiscal_document(
    sale_id: uuid.UUID,
    fiscal_issuer_id: uuid.UUID = Form(...),
    document_type: str = Form(...),
    document_code: str = Form(...),
    document_number: str = Form(...),
    issue_date: date = Form(...),
    file: UploadFile = File(...),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    storage: ObjectStorageService = Depends(get_purchase_attachment_storage_service),
) -> dict:
    content = await file.read(MAX_PURCHASE_ATTACHMENT_SIZE_BYTES + 1)
    document = SaleFiscalDocumentService(db, storage).create(
        tenant.tenant_id,
        sale_id,
        issuer_id=fiscal_issuer_id,
        document_type=document_type,
        document_code=document_code,
        document_number=document_number,
        issue_date=issue_date,
        filename=file.filename,
        declared_content_type=file.content_type,
        content=content,
        uploaded_by_user_id=tenant.user_id,
    )
    return {
        "data": SaleFiscalDocumentRead.model_validate(document).model_dump(mode="json"),
        "meta": {"fiscal_status": "documented"},
    }


@router.get("/{sale_id}/fiscal-document")
def get_sale_fiscal_document(
    sale_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    storage: ObjectStorageService = Depends(get_purchase_attachment_storage_service),
) -> dict:
    document = SaleFiscalDocumentService(db, storage).get(tenant.tenant_id, sale_id)
    return {
        "data": SaleFiscalDocumentRead.model_validate(document).model_dump(mode="json"),
        "meta": {},
    }


@router.patch("/{sale_id}/fiscal-document")
async def update_sale_fiscal_document(
    sale_id: uuid.UUID,
    fiscal_issuer_id: uuid.UUID | None = Form(default=None),
    document_type: str | None = Form(default=None),
    document_code: str | None = Form(default=None),
    document_number: str | None = Form(default=None),
    issue_date: date | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    storage: ObjectStorageService = Depends(get_purchase_attachment_storage_service),
) -> dict:
    content = (
        await file.read(MAX_PURCHASE_ATTACHMENT_SIZE_BYTES + 1)
        if file is not None
        else None
    )
    document = SaleFiscalDocumentService(db, storage).update(
        tenant.tenant_id,
        sale_id,
        issuer_id=fiscal_issuer_id,
        document_type=document_type,
        document_code=document_code,
        document_number=document_number,
        issue_date=issue_date,
        filename=file.filename if file else None,
        declared_content_type=file.content_type if file else None,
        content=content,
        updated_by_user_id=tenant.user_id,
    )
    return {
        "data": SaleFiscalDocumentRead.model_validate(document).model_dump(mode="json"),
        "meta": {},
    }


@router.get("/{sale_id}/fiscal-document/file")
def download_sale_fiscal_document(
    sale_id: uuid.UUID,
    download: bool = Query(default=False),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    storage: ObjectStorageService = Depends(get_purchase_attachment_storage_service),
) -> Response:
    document, content = SaleFiscalDocumentService(db, storage).download(
        tenant.tenant_id, sale_id
    )
    disposition = "attachment" if download else "inline"
    encoded_filename = quote(document.original_filename, safe="")
    return Response(
        content=content,
        media_type=document.content_type,
        headers={
            "Content-Disposition": (
                f'{disposition}; filename="document"; filename*=UTF-8\'\'{encoded_filename}'
            ),
            "Content-Length": str(len(content)),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )

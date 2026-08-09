import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.purchase import (
    PurchaseCancel,
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

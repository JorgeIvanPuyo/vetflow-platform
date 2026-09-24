import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.payment import (
    PaymentMethodCreate,
    PaymentMethodRead,
    PaymentMethodType,
    PaymentMethodUpdate,
    SalePaymentCreate,
    SalePaymentRead,
    SalePaymentVoid,
)
from app.services.payment import PaymentMethodService, SalePaymentService


router = APIRouter(tags=["sale-payments"])


@router.post("/payment-methods", status_code=status.HTTP_201_CREATED)
def create_payment_method(payload: PaymentMethodCreate, tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> dict:
    method = PaymentMethodService(db).create(tenant.tenant_id, payload, user_id=tenant.user_id)
    return {"data": PaymentMethodRead.model_validate(method).model_dump(mode="json"), "meta": {}}


@router.get("/payment-methods")
def list_payment_methods(
    active: bool | None = Query(default=None),
    method_type: PaymentMethodType | None = Query(default=None, alias="type"),
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    methods, meta = PaymentMethodService(db).list(tenant.tenant_id, active=active, method_type=method_type, search=search.strip() if search and search.strip() else None, page=page, page_size=page_size)
    return {"data": [PaymentMethodRead.model_validate(method).model_dump(mode="json") for method in methods], "meta": meta}


@router.get("/payment-methods/{method_id}")
def get_payment_method(method_id: uuid.UUID, tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> dict:
    method = PaymentMethodService(db).get(tenant.tenant_id, method_id)
    return {"data": PaymentMethodRead.model_validate(method).model_dump(mode="json"), "meta": {}}


@router.patch("/payment-methods/{method_id}")
def update_payment_method(method_id: uuid.UUID, payload: PaymentMethodUpdate, tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> dict:
    method = PaymentMethodService(db).update(tenant.tenant_id, method_id, payload, user_id=tenant.user_id)
    return {"data": PaymentMethodRead.model_validate(method).model_dump(mode="json"), "meta": {}}


@router.post("/sales/{sale_id}/payments", status_code=status.HTTP_201_CREATED)
def create_sale_payment(sale_id: uuid.UUID, payload: SalePaymentCreate, tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> dict:
    payment = SalePaymentService(db).create(tenant.tenant_id, sale_id, payload, user_id=tenant.user_id)
    return {"data": SalePaymentRead.model_validate(payment).model_dump(mode="json"), "meta": {}}


@router.get("/sales/{sale_id}/payments")
def list_sale_payments(sale_id: uuid.UUID, tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> dict:
    payments, summary = SalePaymentService(db).list(tenant.tenant_id, sale_id)
    return {"data": [SalePaymentRead.model_validate(payment).model_dump(mode="json") for payment in payments], "meta": summary}


@router.post("/sale-payments/{payment_id}/void")
def void_sale_payment(payment_id: uuid.UUID, payload: SalePaymentVoid, tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> dict:
    payment = SalePaymentService(db).void(tenant.tenant_id, payment_id, reason=payload.reason, user_id=tenant.user_id)
    return {"data": SalePaymentRead.model_validate(payment).model_dump(mode="json"), "meta": {}}

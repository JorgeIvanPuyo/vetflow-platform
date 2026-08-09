import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.fiscal_issuer import (
    FiscalIssuerCreate,
    FiscalIssuerRead,
    FiscalIssuerUpdate,
)
from app.services.fiscal_issuer import FiscalIssuerService


router = APIRouter(prefix="/fiscal-issuers", tags=["sale-fiscal-issuers"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_fiscal_issuer(
    payload: FiscalIssuerCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    issuer = FiscalIssuerService(db).create(tenant.tenant_id, payload)
    return {
        "data": FiscalIssuerRead.model_validate(issuer).model_dump(mode="json"),
        "meta": {},
    }


@router.get("")
def list_fiscal_issuers(
    active_only: bool = Query(default=False),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    issuers = FiscalIssuerService(db).list(
        tenant.tenant_id, active_only=active_only
    )
    return {
        "data": [
            FiscalIssuerRead.model_validate(issuer).model_dump(mode="json")
            for issuer in issuers
        ],
        "meta": {"total": len(issuers)},
    }


@router.get("/{issuer_id}")
def get_fiscal_issuer(
    issuer_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    issuer = FiscalIssuerService(db).get(tenant.tenant_id, issuer_id)
    return {
        "data": FiscalIssuerRead.model_validate(issuer).model_dump(mode="json"),
        "meta": {},
    }


@router.patch("/{issuer_id}")
def update_fiscal_issuer(
    issuer_id: uuid.UUID,
    payload: FiscalIssuerUpdate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    issuer = FiscalIssuerService(db).update(
        tenant.tenant_id, issuer_id, payload
    )
    return {
        "data": FiscalIssuerRead.model_validate(issuer).model_dump(mode="json"),
        "meta": {},
    }

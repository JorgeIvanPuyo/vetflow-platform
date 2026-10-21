import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.fiscal_configuration import FiscalPolicyUpdate, FiscalSeriesCreate, FiscalSeriesUpdate
from app.services.fiscal_configuration import FiscalConfigurationService


router = APIRouter(prefix="/fiscal/configuration", tags=["fiscal-configuration"])


@router.get("")
def get_fiscal_configuration(tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> dict:
    result = FiscalConfigurationService(db).configuration(tenant)
    return {"data": result.model_dump(mode="json"), "meta": {}}


@router.patch("/policy")
def update_fiscal_policy(payload: FiscalPolicyUpdate, tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> dict:
    result = FiscalConfigurationService(db).update_policy(tenant, payload)
    return {"data": result.model_dump(mode="json"), "meta": {}}


@router.post("/series", status_code=status.HTTP_201_CREATED)
def create_fiscal_series(payload: FiscalSeriesCreate, tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> dict:
    result = FiscalConfigurationService(db).create_series(tenant, payload)
    return {"data": result.model_dump(mode="json"), "meta": {}}


@router.patch("/series/{series_id}")
def update_fiscal_series(series_id: uuid.UUID, payload: FiscalSeriesUpdate, tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> dict:
    result = FiscalConfigurationService(db).update_series(tenant, series_id, payload)
    return {"data": result.model_dump(mode="json"), "meta": {}}

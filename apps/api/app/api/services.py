import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context, require_clinic_admin
from app.db.session import get_db
from app.schemas.service import (
    ServiceCreate,
    ServiceRead,
    ServiceReorderRequest,
    ServiceUpdate,
)
from app.services.service_catalog import ServiceCatalogService

router = APIRouter(prefix="/services", tags=["services"])


@router.get("")
def list_services(
    include_inactive: bool = Query(default=False),
    bookable_only: bool = Query(default=False),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    services = ServiceCatalogService(db).list_services(
        tenant.tenant_id,
        include_inactive=include_inactive,
        bookable_only=bookable_only,
    )
    return {
        "data": [
            ServiceRead.model_validate(service).model_dump(mode="json")
            for service in services
        ],
        "meta": {},
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_service(
    payload: ServiceCreate,
    tenant: TenantContext = Depends(require_clinic_admin),
    db: Session = Depends(get_db),
) -> dict:
    service = ServiceCatalogService(db).create_service(
        tenant.tenant_id,
        payload,
        created_by_user_id=tenant.user_id,
    )
    return {
        "data": ServiceRead.model_validate(service).model_dump(mode="json"),
        "meta": {},
    }


@router.patch("/reorder")
def reorder_services(
    payload: ServiceReorderRequest,
    tenant: TenantContext = Depends(require_clinic_admin),
    db: Session = Depends(get_db),
) -> dict:
    services = ServiceCatalogService(db).reorder_services(tenant.tenant_id, payload)
    return {
        "data": [
            ServiceRead.model_validate(service).model_dump(mode="json")
            for service in services
        ],
        "meta": {},
    }


@router.post("/restore-defaults")
def restore_default_services(
    tenant: TenantContext = Depends(require_clinic_admin),
    db: Session = Depends(get_db),
) -> dict:
    services = ServiceCatalogService(db).restore_defaults(tenant.tenant_id)
    return {
        "data": [
            ServiceRead.model_validate(service).model_dump(mode="json")
            for service in services
        ],
        "meta": {},
    }


@router.get("/{service_id}")
def get_service(
    service_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    service = ServiceCatalogService(db).get_service(tenant.tenant_id, service_id)
    return {
        "data": ServiceRead.model_validate(service).model_dump(mode="json"),
        "meta": {},
    }


@router.patch("/{service_id}")
def update_service(
    service_id: uuid.UUID,
    payload: ServiceUpdate,
    tenant: TenantContext = Depends(require_clinic_admin),
    db: Session = Depends(get_db),
) -> dict:
    service = ServiceCatalogService(db).update_service(
        tenant.tenant_id,
        service_id,
        payload,
    )
    return {
        "data": ServiceRead.model_validate(service).model_dump(mode="json"),
        "meta": {},
    }


@router.post("/{service_id}/activate")
def activate_service(
    service_id: uuid.UUID,
    tenant: TenantContext = Depends(require_clinic_admin),
    db: Session = Depends(get_db),
) -> dict:
    service = ServiceCatalogService(db).activate_service(tenant.tenant_id, service_id)
    return {
        "data": ServiceRead.model_validate(service).model_dump(mode="json"),
        "meta": {},
    }


@router.post("/{service_id}/deactivate")
def deactivate_service(
    service_id: uuid.UUID,
    tenant: TenantContext = Depends(require_clinic_admin),
    db: Session = Depends(get_db),
) -> dict:
    service = ServiceCatalogService(db).deactivate_service(tenant.tenant_id, service_id)
    return {
        "data": ServiceRead.model_validate(service).model_dump(mode="json"),
        "meta": {},
    }

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.fiscal_emission import FiscalEmissionCreate, FiscalEmissionIssue, FiscalEmissionReconcile, FiscalReadinessValidate
from app.schemas.payment import IdempotencyKey
from app.services.arca_emission import ArcaEmissionService


router = APIRouter(tags=["arca-emission"])


def get_arca_emission_service(db: Session = Depends(get_db)):
    service = ArcaEmissionService(db)
    try:
        yield service
    finally:
        service.close()


@router.get("/sales/{sale_id}/fiscal-emissions")
def list_emissions(sale_id: uuid.UUID, tenant: TenantContext = Depends(get_tenant_context), service: ArcaEmissionService = Depends(get_arca_emission_service)):
    return {"data": service.list(tenant, sale_id), "meta": {}}


@router.get("/fiscal/emission-pending")
def pending_emissions(tenant: TenantContext = Depends(get_tenant_context), service: ArcaEmissionService = Depends(get_arca_emission_service)):
    return {"data": service.list(tenant, pending_only=True), "meta": {}}


@router.post("/sales/{sale_id}/fiscal-emissions", status_code=status.HTTP_201_CREATED)
def prepare_emission(sale_id: uuid.UUID, payload: FiscalEmissionCreate, response: Response, idempotency_key: IdempotencyKey = Header(alias="Idempotency-Key"), tenant: TenantContext = Depends(get_tenant_context), service: ArcaEmissionService = Depends(get_arca_emission_service)):
    result = service.prepare(tenant, sale_id, payload, idempotency_key)
    response.headers["Idempotency-Replayed"] = str(service.idempotency_replayed).lower()
    if service.idempotency_replayed:
        response.status_code = status.HTTP_200_OK
    return {"data": result.model_dump(mode="json"), "meta": {}}


@router.post("/sales/{sale_id}/fiscal-emissions/{emission_id}/issue")
def issue_emission(sale_id: uuid.UUID, emission_id: uuid.UUID, payload: FiscalEmissionIssue, tenant: TenantContext = Depends(get_tenant_context), service: ArcaEmissionService = Depends(get_arca_emission_service)):
    return {"data": service.issue(tenant, sale_id, emission_id).model_dump(mode="json"), "meta": {}}


@router.post("/sales/{sale_id}/fiscal-emissions/{emission_id}/reconcile")
def reconcile_emission(sale_id: uuid.UUID, emission_id: uuid.UUID, payload: FiscalEmissionReconcile, tenant: TenantContext = Depends(get_tenant_context), service: ArcaEmissionService = Depends(get_arca_emission_service)):
    if payload.retry_same_request and not payload.confirm:
        raise AppError(422, "arca_exact_retry_confirmation_required", "Confirma explícitamente el reenvío de la misma solicitud y número")
    return {"data": service.reconcile(tenant, sale_id, emission_id, retry_same_request=payload.retry_same_request).model_dump(mode="json"), "meta": {}}


@router.post("/sales/{sale_id}/fiscal-emissions/{emission_id}/regenerate")
def regenerate_emission(sale_id: uuid.UUID, emission_id: uuid.UUID, tenant: TenantContext = Depends(get_tenant_context), service: ArcaEmissionService = Depends(get_arca_emission_service)):
    return {"data": service.regenerate(tenant, sale_id, emission_id).model_dump(mode="json"), "meta": {}}


@router.get("/sales/{sale_id}/fiscal-emissions/{emission_id}/file")
def download_emission(sale_id: uuid.UUID, emission_id: uuid.UUID, version_id: uuid.UUID | None = Query(default=None), tenant: TenantContext = Depends(get_tenant_context), service: ArcaEmissionService = Depends(get_arca_emission_service)):
    descriptor, content = service.download(tenant, sale_id, emission_id, version_id=version_id)
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": f"inline; filename=\"comprobante.pdf\"; filename*=UTF-8''{quote(descriptor.original_filename, safe='')}", "Content-Length": str(len(content)), "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/fiscal/emission-readiness")
def emission_readiness(series_id: uuid.UUID, tenant: TenantContext = Depends(get_tenant_context), service: ArcaEmissionService = Depends(get_arca_emission_service)):
    return {"data": service.readiness(tenant, series_id), "meta": {}}


@router.post("/fiscal/emission-readiness/validate")
def validate_readiness(payload: FiscalReadinessValidate, tenant: TenantContext = Depends(get_tenant_context), service: ArcaEmissionService = Depends(get_arca_emission_service)):
    return {"data": service.readiness(tenant, payload.series_id, validate=True), "meta": {}}

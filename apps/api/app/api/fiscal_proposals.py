import uuid

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.fiscal_proposal import FiscalManualAllocation, FiscalProposalApprove, FiscalProposalCancel, FiscalProposalGenerate, FiscalProposalUpdate
from app.schemas.payment import IdempotencyKey
from app.services.fiscal_proposal import FiscalProposalService


router = APIRouter(prefix="/sales/{sale_id}", tags=["fiscal-review"])


@router.get("/fiscal-review")
def fiscal_review(sale_id: uuid.UUID, tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    return {"data": FiscalProposalService(db).review(tenant, sale_id).model_dump(mode="json"), "meta": {}}


@router.post("/fiscal-proposals", status_code=status.HTTP_201_CREATED)
def generate_proposals(sale_id: uuid.UUID, payload: FiscalProposalGenerate, tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    return {"data": [row.model_dump(mode="json") for row in FiscalProposalService(db).generate(tenant, sale_id, payload)], "meta": {}}


@router.patch("/fiscal-proposals/{proposal_id}")
def review_proposal(sale_id: uuid.UUID, proposal_id: uuid.UUID, payload: FiscalProposalUpdate, tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    return {"data": FiscalProposalService(db).update(tenant, sale_id, proposal_id, payload).model_dump(mode="json"), "meta": {}}


@router.post("/fiscal-proposals/{proposal_id}/approve")
def approve_proposal(sale_id: uuid.UUID, proposal_id: uuid.UUID, payload: FiscalProposalApprove, response: Response, idempotency_key: IdempotencyKey = Header(alias="Idempotency-Key"), tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    service = FiscalProposalService(db)
    result = service.approve(tenant, sale_id, proposal_id, payload, idempotency_key)
    response.headers["Idempotency-Replayed"] = str(service.idempotency_replayed).lower()
    return {"data": result.model_dump(mode="json"), "meta": {"idempotency_replayed": service.idempotency_replayed}}


@router.post("/fiscal-proposals/{proposal_id}/cancel")
def cancel_proposal(sale_id: uuid.UUID, proposal_id: uuid.UUID, payload: FiscalProposalCancel, tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    return {"data": FiscalProposalService(db).cancel(tenant, sale_id, proposal_id, reason=payload.reason).model_dump(mode="json"), "meta": {}}


@router.post("/fiscal-documents/{document_id}/allocate")
def regularize_manual_document(sale_id: uuid.UUID, document_id: uuid.UUID, payload: FiscalManualAllocation, idempotency_key: IdempotencyKey = Header(alias="Idempotency-Key"), tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    return {"data": FiscalProposalService(db).regularize_manual(tenant, sale_id, document_id, payload, idempotency_key).model_dump(mode="json"), "meta": {}}

from fastapi import APIRouter, Depends

from app.core.tenant import TenantContext, get_tenant_context
from app.schemas.ai import (
    GenerateConsultationSummaryRequest,
    GenerateConsultationSummaryResponse,
    RewriteClinicalNoteRequest,
    RewriteClinicalNoteResponse,
)
from app.services.ai_service import AIService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/rewrite-clinical-note")
def rewrite_clinical_note(
    payload: RewriteClinicalNoteRequest,
    tenant: TenantContext = Depends(get_tenant_context),
) -> RewriteClinicalNoteResponse:
    suggestion = AIService().rewrite_clinical_note(
        field=payload.field,
        text=payload.text,
        patient_context=payload.patient_context,
        tenant_id=tenant.tenant_id,
        user_id=tenant.user_id,
    )
    return RewriteClinicalNoteResponse(suggestion=suggestion)


@router.post("/generate-consultation-summary")
def generate_consultation_summary(
    payload: GenerateConsultationSummaryRequest,
    tenant: TenantContext = Depends(get_tenant_context),
) -> GenerateConsultationSummaryResponse:
    summary = AIService().generate_consultation_summary(
        consultation=payload.consultation,
        summary_type=payload.summary_type,
        tenant_id=tenant.tenant_id,
        user_id=tenant.user_id,
    )
    return GenerateConsultationSummaryResponse(summary=summary)

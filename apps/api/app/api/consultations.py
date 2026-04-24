import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.common import ListMeta
from app.schemas.consultation import (
    ClinicalHistoryRead,
    ClinicalHistoryTimelineItem,
    ConsultationCreate,
    ConsultationRead,
    ConsultationUpdate,
)
from app.schemas.exam import ExamRead
from app.schemas.patient import PatientRead
from app.services.consultation import ConsultationService

router = APIRouter(tags=["consultations"])


@router.post("/consultations", status_code=status.HTTP_201_CREATED)
def create_consultation(
    payload: ConsultationCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    consultation = ConsultationService(db).create_consultation(
        tenant.tenant_id,
        payload,
    )
    return {
        "data": ConsultationRead.model_validate(consultation).model_dump(mode="json"),
        "meta": {},
    }


@router.get("/consultations/{consultation_id}")
def get_consultation(
    consultation_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    consultation = ConsultationService(db).get_consultation(
        tenant.tenant_id,
        consultation_id,
    )
    return {
        "data": ConsultationRead.model_validate(consultation).model_dump(mode="json"),
        "meta": {},
    }


@router.patch("/consultations/{consultation_id}")
def update_consultation(
    consultation_id: uuid.UUID,
    payload: ConsultationUpdate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    consultation = ConsultationService(db).update_consultation(
        tenant.tenant_id,
        consultation_id,
        payload,
    )
    return {
        "data": ConsultationRead.model_validate(consultation).model_dump(mode="json"),
        "meta": {},
    }


@router.get("/patients/{patient_id}/consultations")
def list_patient_consultations(
    patient_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    consultations, total = ConsultationService(db).list_patient_consultations(
        tenant.tenant_id,
        patient_id,
    )
    return {
        "data": [
            ConsultationRead.model_validate(consultation).model_dump(mode="json")
            for consultation in consultations
        ],
        "meta": ListMeta(
            page=1,
            page_size=len(consultations),
            total=total,
        ).model_dump(),
    }


@router.get("/patients/{patient_id}/clinical-history")
def get_patient_clinical_history(
    patient_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    patient, consultations, exams = ConsultationService(db).get_patient_clinical_history(
        tenant.tenant_id,
        patient_id,
    )
    timeline = [
        *[
            ClinicalHistoryTimelineItem(
                type="consultation",
                id=consultation.id,
                date=consultation.visit_date,
                title=consultation.reason,
                summary=_consultation_summary(consultation),
            )
            for consultation in consultations
        ],
        *[
            ClinicalHistoryTimelineItem(
                type="exam",
                id=exam.id,
                date=exam.requested_at,
                title=exam.exam_type,
                summary=_exam_summary(exam.status),
            )
            for exam in exams
        ],
    ]
    timeline.sort(key=lambda item: item.date, reverse=True)

    clinical_history = ClinicalHistoryRead(
        patient=PatientRead.model_validate(patient),
        consultations=[
            ConsultationRead.model_validate(consultation)
            for consultation in consultations
        ],
        exams=[ExamRead.model_validate(exam) for exam in exams],
        timeline=timeline,
    )
    return {"data": clinical_history.model_dump(mode="json"), "meta": {}}


def _consultation_summary(consultation) -> str:
    return (
        consultation.final_diagnosis
        or consultation.presumptive_diagnosis
        or consultation.clinical_exam
        or consultation.anamnesis
        or "Consultation registered"
    )


def _exam_summary(status: str) -> str:
    status_labels = {
        "requested": "Requested",
        "performed": "Performed",
        "result_loaded": "Result loaded",
    }
    return status_labels.get(status, status)

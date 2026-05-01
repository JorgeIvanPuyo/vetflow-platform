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
    ConsultationMedicationCreate,
    ConsultationMedicationRead,
    ConsultationRead,
    ConsultationStepUpdate,
    ConsultationStudyRequestCreate,
    ConsultationStudyRequestRead,
    ConsultationUpdate,
    TimelineUserTrace,
)
from app.schemas.exam import ExamRead
from app.schemas.file_reference import FileReferenceRead
from app.schemas.patient import PatientRead
from app.schemas.preventive_care import PreventiveCareRead
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
        created_by_user_id=tenant.user_id,
        attending_user_id=tenant.user_id,
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


@router.patch("/consultations/{consultation_id}/step")
def update_consultation_step(
    consultation_id: uuid.UUID,
    payload: ConsultationStepUpdate,
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


@router.delete(
    "/consultations/{consultation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_consultation(
    consultation_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> None:
    ConsultationService(db).delete_consultation(tenant.tenant_id, consultation_id)


@router.post(
    "/consultations/{consultation_id}/medications",
    status_code=status.HTTP_201_CREATED,
)
def create_consultation_medication(
    consultation_id: uuid.UUID,
    payload: ConsultationMedicationCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    medication = ConsultationService(db).create_medication(
        tenant.tenant_id,
        consultation_id,
        payload,
    )
    return {
        "data": ConsultationMedicationRead.model_validate(medication).model_dump(
            mode="json",
        ),
        "meta": {},
    }


@router.delete(
    "/consultation-medications/{medication_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_consultation_medication(
    medication_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> None:
    ConsultationService(db).delete_medication(tenant.tenant_id, medication_id)


@router.post(
    "/consultations/{consultation_id}/study-requests",
    status_code=status.HTTP_201_CREATED,
)
def create_consultation_study_request(
    consultation_id: uuid.UUID,
    payload: ConsultationStudyRequestCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    study_request = ConsultationService(db).create_study_request(
        tenant.tenant_id,
        consultation_id,
        payload,
    )
    return {
        "data": ConsultationStudyRequestRead.model_validate(study_request).model_dump(
            mode="json",
        ),
        "meta": {},
    }


@router.delete(
    "/consultation-study-requests/{study_request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_consultation_study_request(
    study_request_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> None:
    ConsultationService(db).delete_study_request(tenant.tenant_id, study_request_id)


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
    (
        patient,
        consultations,
        exams,
        preventive_care,
        file_references,
    ) = ConsultationService(db).get_patient_clinical_history(
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
                created_by=_user_trace(consultation.created_by_user, tenant.tenant_id),
                attended_by=_user_trace(consultation.attending_user, tenant.tenant_id),
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
                requested_by=_user_trace(exam.requested_by_user, tenant.tenant_id),
            )
            for exam in exams
        ],
        *[
            ClinicalHistoryTimelineItem(
                type="preventive_care",
                id=record.id,
                date=record.applied_at,
                title=record.name,
                summary=_preventive_care_summary(record),
                created_by=_user_trace(record.created_by_user, tenant.tenant_id),
            )
            for record in preventive_care
        ],
        *[
            ClinicalHistoryTimelineItem(
                type="file_reference",
                id=file_reference.id,
                date=file_reference.created_at,
                title=file_reference.name,
                summary=file_reference.file_type,
                created_by=_user_trace(
                    file_reference.created_by_user,
                    tenant.tenant_id,
                ),
            )
            for file_reference in file_references
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
        preventive_care=[
            PreventiveCareRead.model_validate(record) for record in preventive_care
        ],
        file_references=[
            FileReferenceRead.model_validate(file_reference)
            for file_reference in file_references
        ],
        timeline=timeline,
    )
    body = clinical_history.model_dump(mode="json")
    for item in body["timeline"]:
        for key in ("created_by", "attended_by", "requested_by"):
            if item.get(key) is None:
                item.pop(key, None)

    return {"data": body, "meta": {}}


def _consultation_summary(consultation) -> str:
    return (
        consultation.final_diagnosis
        or consultation.presumptive_diagnosis
        or consultation.consultation_summary
        or "Consultation registered"
    )


def _exam_summary(status: str) -> str:
    status_labels = {
        "requested": "Requested",
        "performed": "Performed",
        "result_loaded": "Result loaded",
    }
    return status_labels.get(status, status)


def _preventive_care_summary(record) -> str:
    care_type_labels = {
        "vaccine": "Vaccine",
        "deworming": "Deworming",
        "other": "Preventive care",
    }
    return record.lot_number or record.notes or care_type_labels.get(
        record.care_type,
        record.care_type,
    )


def _user_trace(user, tenant_id: uuid.UUID) -> TimelineUserTrace | None:
    if user is None or user.tenant_id != tenant_id:
        return None

    if not user.full_name and not user.email:
        return None

    return TimelineUserTrace(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
    )

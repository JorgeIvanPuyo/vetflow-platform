import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.common import ListMeta
from app.schemas.exam import ExamCreate, ExamRead, ExamUpdate
from app.services.exam import ExamService

router = APIRouter(tags=["exams"])


@router.post("/exams", status_code=status.HTTP_201_CREATED)
def create_exam(
    payload: ExamCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    exam = ExamService(db).create_exam(
        tenant.tenant_id,
        payload,
        requested_by_user_id=tenant.user_id,
    )
    return {"data": ExamRead.model_validate(exam).model_dump(mode="json"), "meta": {}}


@router.get("/exams/{exam_id}")
def get_exam(
    exam_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    exam = ExamService(db).get_exam(tenant.tenant_id, exam_id)
    return {"data": ExamRead.model_validate(exam).model_dump(mode="json"), "meta": {}}


@router.patch("/exams/{exam_id}")
def update_exam(
    exam_id: uuid.UUID,
    payload: ExamUpdate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    exam = ExamService(db).update_exam(tenant.tenant_id, exam_id, payload)
    return {"data": ExamRead.model_validate(exam).model_dump(mode="json"), "meta": {}}


@router.get("/patients/{patient_id}/exams")
def list_patient_exams(
    patient_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    exams, total = ExamService(db).list_patient_exams(tenant.tenant_id, patient_id)
    return {
        "data": [ExamRead.model_validate(exam).model_dump(mode="json") for exam in exams],
        "meta": ListMeta(page=1, page_size=len(exams), total=total).model_dump(),
    }


@router.get("/consultations/{consultation_id}/exams")
def list_consultation_exams(
    consultation_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    exams, total = ExamService(db).list_consultation_exams(
        tenant.tenant_id,
        consultation_id,
    )
    return {
        "data": [ExamRead.model_validate(exam).model_dump(mode="json") for exam in exams],
        "meta": ListMeta(page=1, page_size=len(exams), total=total).model_dump(),
    }

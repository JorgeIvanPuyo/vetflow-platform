import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.common import ListMeta
from app.schemas.patient import PatientCreate, PatientRead, PatientUpdate
from app.services.patient import PatientService

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    patient = PatientService(db).create_patient(
        tenant.tenant_id,
        payload,
        created_by_user_id=tenant.user_id,
    )
    return {
        "data": PatientRead.model_validate(patient).model_dump(mode="json"),
        "meta": {},
    }


@router.get("")
def list_patients(
    owner_id: uuid.UUID | None = Query(default=None),
    species: str | None = Query(default=None),
    search: str | None = Query(default=None),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    patients, total = PatientService(db).list_patients(
        tenant.tenant_id,
        owner_id=owner_id,
        species=species,
        search=search,
    )
    return {
        "data": [
            PatientRead.model_validate(patient).model_dump(mode="json")
            for patient in patients
        ],
        "meta": ListMeta(page=1, page_size=len(patients), total=total).model_dump(),
    }


@router.get("/{patient_id}")
def get_patient(
    patient_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    patient = PatientService(db).get_patient(tenant.tenant_id, patient_id)
    return {
        "data": PatientRead.model_validate(patient).model_dump(mode="json"),
        "meta": {},
    }


@router.patch("/{patient_id}")
def update_patient(
    patient_id: uuid.UUID,
    payload: PatientUpdate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    patient = PatientService(db).update_patient(tenant.tenant_id, patient_id, payload)
    return {
        "data": PatientRead.model_validate(patient).model_dump(mode="json"),
        "meta": {},
    }


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(
    patient_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> Response:
    PatientService(db).delete_patient(tenant.tenant_id, patient_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.common import ListMeta
from app.schemas.preventive_care import (
    PreventiveCareCreate,
    PreventiveCareRead,
    PreventiveCareUpdate,
)
from app.services.preventive_care import PreventiveCareService

router = APIRouter(tags=["preventive-care"])


@router.post(
    "/patients/{patient_id}/preventive-care",
    status_code=status.HTTP_201_CREATED,
)
def create_preventive_care(
    patient_id: uuid.UUID,
    payload: PreventiveCareCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    record = PreventiveCareService(db).create_preventive_care(
        tenant.tenant_id,
        patient_id,
        payload,
        created_by_user_id=tenant.user_id,
    )
    return {
        "data": PreventiveCareRead.model_validate(record).model_dump(mode="json"),
        "meta": {},
    }


@router.get("/patients/{patient_id}/preventive-care")
def list_patient_preventive_care(
    patient_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    records, total = PreventiveCareService(db).list_patient_preventive_care(
        tenant.tenant_id,
        patient_id,
    )
    return {
        "data": [
            PreventiveCareRead.model_validate(record).model_dump(mode="json")
            for record in records
        ],
        "meta": ListMeta(page=1, page_size=len(records), total=total).model_dump(),
    }


@router.get("/preventive-care/{record_id}")
def get_preventive_care(
    record_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    record = PreventiveCareService(db).get_preventive_care(
        tenant.tenant_id,
        record_id,
    )
    return {
        "data": PreventiveCareRead.model_validate(record).model_dump(mode="json"),
        "meta": {},
    }


@router.patch("/preventive-care/{record_id}")
def update_preventive_care(
    record_id: uuid.UUID,
    payload: PreventiveCareUpdate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    record = PreventiveCareService(db).update_preventive_care(
        tenant.tenant_id,
        record_id,
        payload,
    )
    return {
        "data": PreventiveCareRead.model_validate(record).model_dump(mode="json"),
        "meta": {},
    }


@router.delete("/preventive-care/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_preventive_care(
    record_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> Response:
    PreventiveCareService(db).delete_preventive_care(tenant.tenant_id, record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

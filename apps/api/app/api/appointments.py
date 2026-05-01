import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentRead,
    AppointmentStatus,
    AppointmentType,
    AppointmentUpdate,
)
from app.schemas.common import ListMeta
from app.services.appointment import AppointmentService

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: AppointmentCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    appointment = AppointmentService(db).create_appointment(
        tenant.tenant_id,
        payload,
        created_by_user_id=tenant.user_id,
    )
    return {
        "data": AppointmentRead.model_validate(appointment).model_dump(mode="json"),
        "meta": {},
    }


@router.get("")
def list_appointments(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    assigned_user_id: uuid.UUID | None = Query(default=None),
    patient_id: uuid.UUID | None = Query(default=None),
    owner_id: uuid.UUID | None = Query(default=None),
    status: AppointmentStatus | None = Query(default=None),
    appointment_type: AppointmentType | None = Query(default=None),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    appointments, total = AppointmentService(db).list_appointments(
        tenant.tenant_id,
        date_from=date_from,
        date_to=date_to,
        assigned_user_id=assigned_user_id,
        patient_id=patient_id,
        owner_id=owner_id,
        status=status,
        appointment_type=appointment_type,
    )
    return {
        "data": [
            AppointmentRead.model_validate(appointment).model_dump(mode="json")
            for appointment in appointments
        ],
        "meta": ListMeta(page=1, page_size=len(appointments), total=total).model_dump(),
    }


@router.get("/{appointment_id}")
def get_appointment(
    appointment_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    appointment = AppointmentService(db).get_appointment(
        tenant.tenant_id,
        appointment_id,
    )
    return {
        "data": AppointmentRead.model_validate(appointment).model_dump(mode="json"),
        "meta": {},
    }


@router.patch("/{appointment_id}")
def update_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentUpdate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    appointment = AppointmentService(db).update_appointment(
        tenant.tenant_id,
        appointment_id,
        payload,
    )
    return {
        "data": AppointmentRead.model_validate(appointment).model_dump(mode="json"),
        "meta": {},
    }


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_appointment(
    appointment_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> Response:
    AppointmentService(db).delete_appointment(tenant.tenant_id, appointment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

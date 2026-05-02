import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.common import ListMeta
from app.schemas.follow_up import (
    FollowUpCancel,
    FollowUpCreate,
    FollowUpRead,
    FollowUpStatus,
    FollowUpType,
    FollowUpUpdate,
)
from app.services.follow_up import FollowUpService

router = APIRouter(prefix="/follow-ups", tags=["follow-ups"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_follow_up(
    payload: FollowUpCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    follow_up = FollowUpService(db).create_follow_up(
        tenant.tenant_id,
        payload,
        created_by_user_id=tenant.user_id,
    )
    return {
        "data": FollowUpRead.model_validate(follow_up).model_dump(mode="json"),
        "meta": {},
    }


@router.get("")
def list_follow_ups(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    patient_id: uuid.UUID | None = Query(default=None),
    owner_id: uuid.UUID | None = Query(default=None),
    assigned_user_id: uuid.UUID | None = Query(default=None),
    status: FollowUpStatus | None = Query(default=None),
    follow_up_type: FollowUpType | None = Query(default=None),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    follow_ups, total = FollowUpService(db).list_follow_ups(
        tenant.tenant_id,
        date_from=date_from,
        date_to=date_to,
        patient_id=patient_id,
        owner_id=owner_id,
        assigned_user_id=assigned_user_id,
        status=status,
        follow_up_type=follow_up_type,
    )
    return {
        "data": [
            FollowUpRead.model_validate(follow_up).model_dump(mode="json")
            for follow_up in follow_ups
        ],
        "meta": ListMeta(page=1, page_size=len(follow_ups), total=total).model_dump(),
    }


@router.get("/{follow_up_id}")
def get_follow_up(
    follow_up_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    follow_up = FollowUpService(db).get_follow_up(tenant.tenant_id, follow_up_id)
    return {
        "data": FollowUpRead.model_validate(follow_up).model_dump(mode="json"),
        "meta": {},
    }


@router.patch("/{follow_up_id}")
def update_follow_up(
    follow_up_id: uuid.UUID,
    payload: FollowUpUpdate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    follow_up = FollowUpService(db).update_follow_up(
        tenant.tenant_id,
        follow_up_id,
        payload,
    )
    return {
        "data": FollowUpRead.model_validate(follow_up).model_dump(mode="json"),
        "meta": {},
    }


@router.post("/{follow_up_id}/complete")
def complete_follow_up(
    follow_up_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    follow_up = FollowUpService(db).complete_follow_up(tenant.tenant_id, follow_up_id)
    return {
        "data": FollowUpRead.model_validate(follow_up).model_dump(mode="json"),
        "meta": {},
    }


@router.post("/{follow_up_id}/cancel")
def cancel_follow_up(
    follow_up_id: uuid.UUID,
    payload: FollowUpCancel,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    follow_up = FollowUpService(db).cancel_follow_up(
        tenant.tenant_id,
        follow_up_id,
        payload,
    )
    return {
        "data": FollowUpRead.model_validate(follow_up).model_dump(mode="json"),
        "meta": {},
    }


@router.delete("/{follow_up_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_follow_up(
    follow_up_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> Response:
    FollowUpService(db).delete_follow_up(tenant.tenant_id, follow_up_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

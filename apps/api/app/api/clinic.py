from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.clinic import (
    ClinicProfileRead,
    ClinicProfileUpdate,
    ClinicTeamMemberRead,
)
from app.services.clinic import ClinicService

router = APIRouter(prefix="/clinic", tags=["clinic"])


@router.get("/profile")
def get_clinic_profile(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    profile = ClinicService(db).get_profile(tenant.tenant_id)
    return {
        "data": ClinicProfileRead.model_validate(profile).model_dump(mode="json"),
        "meta": {},
    }


@router.patch("/profile")
def update_clinic_profile(
    payload: ClinicProfileUpdate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    profile = ClinicService(db).update_profile(tenant.tenant_id, payload)
    return {
        "data": ClinicProfileRead.model_validate(profile).model_dump(mode="json"),
        "meta": {},
    }


@router.get("/team")
def get_clinic_team(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    team = ClinicService(db).list_team(tenant.tenant_id)
    return {
        "data": [
            ClinicTeamMemberRead.model_validate(member).model_dump(mode="json")
            for member in team
        ],
        "meta": {},
    }

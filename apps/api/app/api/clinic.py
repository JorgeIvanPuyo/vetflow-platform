from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.clinic import (
    ClinicProfileRead,
    ClinicProfileUpdate,
    ClinicTeamMemberRead,
)
from app.services.clinic import ClinicService
from app.services.storage import ClinicalFileStorageService, get_storage_service

router = APIRouter(prefix="/clinic", tags=["clinic"])


@router.get("/profile")
def get_clinic_profile(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    storage_service: ClinicalFileStorageService = Depends(get_storage_service),
) -> dict:
    service = ClinicService(db)
    profile = service.get_profile(tenant.tenant_id)
    return {
        "data": ClinicProfileRead.model_validate(
            service.build_profile_response(profile, storage_service=storage_service)
        ).model_dump(mode="json"),
        "meta": {},
    }


@router.patch("/profile")
def update_clinic_profile(
    payload: ClinicProfileUpdate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    storage_service: ClinicalFileStorageService = Depends(get_storage_service),
) -> dict:
    service = ClinicService(db)
    profile = service.update_profile(tenant.tenant_id, payload)
    return {
        "data": ClinicProfileRead.model_validate(
            service.build_profile_response(profile, storage_service=storage_service)
        ).model_dump(mode="json"),
        "meta": {},
    }


@router.post("/logo", status_code=status.HTTP_200_OK)
async def upload_clinic_logo(
    file: UploadFile = File(...),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    storage_service: ClinicalFileStorageService = Depends(get_storage_service),
) -> dict:
    content = await file.read()
    service = ClinicService(db)
    profile = service.upload_logo(
        tenant.tenant_id,
        original_filename=file.filename,
        content_type=file.content_type,
        content=content,
        storage_service=storage_service,
    )
    return {
        "data": ClinicProfileRead.model_validate(
            service.build_profile_response(profile, storage_service=storage_service)
        ).model_dump(mode="json"),
        "meta": {},
    }


@router.delete("/logo")
def delete_clinic_logo(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    storage_service: ClinicalFileStorageService = Depends(get_storage_service),
) -> dict:
    service = ClinicService(db)
    profile = service.delete_logo(
        tenant.tenant_id,
        storage_service=storage_service,
    )
    return {
        "data": ClinicProfileRead.model_validate(
            service.build_profile_response(profile, storage_service=storage_service)
        ).model_dump(mode="json"),
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

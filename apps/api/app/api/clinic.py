import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.tenant import TenantContext, get_tenant_context, require_clinic_admin
from app.db.session import get_db
from app.schemas.clinic import (
    ClinicConfigurationRead,
    ClinicProfileRead,
    ClinicProfileUpdate,
    ClinicTeamMemberRead,
    ClinicTeamMemberUpdate,
    TenantPreferenceRead,
    TenantPreferenceUpdate,
)
from app.schemas.catalog_item import CatalogItemRead
from app.schemas.service import ServiceRead
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


@router.patch("/team/{user_id}")
def update_clinic_team_member(
    user_id: uuid.UUID,
    payload: ClinicTeamMemberUpdate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    updated_user = ClinicService(db).update_team_member(
        tenant.tenant_id,
        user_id,
        payload,
    )
    return {
        "data": ClinicTeamMemberRead.model_validate(updated_user).model_dump(
            mode="json"
        ),
        "meta": {},
    }


@router.get("/preferences")
def get_clinic_preferences(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    preferences = ClinicService(db).get_preferences(tenant.tenant_id)
    return {
        "data": TenantPreferenceRead.model_validate(preferences).model_dump(mode="json"),
        "meta": {},
    }


@router.patch("/preferences")
def update_clinic_preferences(
    payload: TenantPreferenceUpdate,
    tenant: TenantContext = Depends(require_clinic_admin),
    db: Session = Depends(get_db),
) -> dict:
    preferences = ClinicService(db).update_preferences(tenant.tenant_id, payload)
    return {
        "data": TenantPreferenceRead.model_validate(preferences).model_dump(mode="json"),
        "meta": {},
    }


@router.get("/configuration")
def get_clinic_configuration(
    include: str = Query(default="preferences,services"),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    includes = {value.strip() for value in include.split(",") if value.strip()}
    allowed = {"preferences", "services", "catalogs"}
    if not includes or includes - allowed:
        raise AppError(
            422,
            "validation_error",
            "include must contain any of: preferences, services, catalogs",
        )

    configuration = ClinicService(db).get_configuration(
        tenant.tenant_id,
        include_preferences="preferences" in includes,
        include_services="services" in includes,
        include_catalogs="catalogs" in includes,
    )
    data = ClinicConfigurationRead(
        preferences=TenantPreferenceRead.model_validate(configuration["preferences"])
        if configuration["preferences"] is not None
        else None,
        services=[
            ServiceRead.model_validate(service)
            for service in configuration["services"]
        ]
        if configuration["services"] is not None
        else None,
        catalogs={
            catalog_type: [CatalogItemRead.model_validate(item) for item in items]
            for catalog_type, items in configuration["catalogs"].items()
        }
        if configuration["catalogs"] is not None
        else None,
    ).model_dump(mode="json")
    return {"data": data, "meta": {}}

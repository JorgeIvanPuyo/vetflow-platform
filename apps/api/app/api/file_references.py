import uuid

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.common import ListMeta
from app.schemas.file_reference import (
    FileDownloadUrlRead,
    FileReferenceCreate,
    FileReferenceRead,
    FileReferenceUpdate,
)
from app.services.file_reference import FileReferenceService
from app.services.storage import ClinicalFileStorageService, get_storage_service

router = APIRouter(tags=["file-references"])


@router.post(
    "/patients/{patient_id}/file-references",
    status_code=status.HTTP_201_CREATED,
)
def create_file_reference(
    patient_id: uuid.UUID,
    payload: FileReferenceCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    file_reference = FileReferenceService(db).create_file_reference(
        tenant.tenant_id,
        patient_id,
        payload,
        created_by_user_id=tenant.user_id,
    )
    return {
        "data": FileReferenceRead.model_validate(file_reference).model_dump(
            mode="json"
        ),
        "meta": {},
    }


@router.post(
    "/patients/{patient_id}/files/upload",
    status_code=status.HTTP_201_CREATED,
)
async def upload_patient_file(
    patient_id: uuid.UUID,
    name: str = Form(...),
    file_type: str = Form(...),
    description: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    storage_service: ClinicalFileStorageService = Depends(get_storage_service),
) -> dict:
    content = await file.read() if file is not None else None
    file_reference = FileReferenceService(db).upload_clinical_file(
        tenant.tenant_id,
        patient_id,
        name=name,
        file_type=file_type,
        description=description,
        original_filename=file.filename if file is not None else None,
        content_type=file.content_type if file is not None else None,
        content=content,
        created_by_user_id=tenant.user_id,
        storage_service=storage_service,
    )
    return {
        "data": FileReferenceRead.model_validate(file_reference).model_dump(
            mode="json"
        ),
        "meta": {},
    }


@router.get("/patients/{patient_id}/file-references")
def list_patient_file_references(
    patient_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    file_references, total = FileReferenceService(db).list_patient_file_references(
        tenant.tenant_id,
        patient_id,
    )
    return {
        "data": [
            FileReferenceRead.model_validate(file_reference).model_dump(mode="json")
            for file_reference in file_references
        ],
        "meta": ListMeta(
            page=1,
            page_size=len(file_references),
            total=total,
        ).model_dump(),
    }


@router.get("/file-references/{file_reference_id}/download-url")
def get_file_reference_download_url(
    file_reference_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    storage_service: ClinicalFileStorageService = Depends(get_storage_service),
) -> dict:
    download_url, expires_in_seconds = FileReferenceService(db).get_file_download_url(
        tenant.tenant_id,
        file_reference_id,
        storage_service=storage_service,
    )
    return {
        "data": FileDownloadUrlRead(
            download_url=download_url,
            expires_in_seconds=expires_in_seconds,
        ).model_dump(mode="json"),
        "meta": {},
    }


@router.get("/file-references/{file_reference_id}")
def get_file_reference(
    file_reference_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    file_reference = FileReferenceService(db).get_file_reference(
        tenant.tenant_id,
        file_reference_id,
    )
    return {
        "data": FileReferenceRead.model_validate(file_reference).model_dump(
            mode="json"
        ),
        "meta": {},
    }


@router.patch("/file-references/{file_reference_id}")
def update_file_reference(
    file_reference_id: uuid.UUID,
    payload: FileReferenceUpdate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    file_reference = FileReferenceService(db).update_file_reference(
        tenant.tenant_id,
        file_reference_id,
        payload,
    )
    return {
        "data": FileReferenceRead.model_validate(file_reference).model_dump(
            mode="json"
        ),
        "meta": {},
    }


@router.delete(
    "/file-references/{file_reference_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_file_reference(
    file_reference_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    storage_service: ClinicalFileStorageService = Depends(get_storage_service),
) -> Response:
    FileReferenceService(db).delete_file_reference(
        tenant.tenant_id,
        file_reference_id,
        storage_service=storage_service,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.common import ListMeta
from app.schemas.file_reference import (
    FileReferenceCreate,
    FileReferenceRead,
    FileReferenceUpdate,
)
from app.services.file_reference import FileReferenceService

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
) -> Response:
    FileReferenceService(db).delete_file_reference(
        tenant.tenant_id,
        file_reference_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

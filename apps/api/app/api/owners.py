import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.common import ListMeta
from app.schemas.owner import OwnerCreate, OwnerSortBy, OwnerUpdate
from app.services.owner import OwnerService
from app.services.receivables import OwnerReceivablesService

router = APIRouter(prefix="/owners", tags=["owners"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_owner(
    payload: OwnerCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    service = OwnerService(db)
    owner = service.create_owner(tenant.tenant_id, payload)
    return {"data": service.build_owner_response(tenant.tenant_id, owner), "meta": {}}


@router.get("")
def list_owners(
    search: str | None = Query(default=None),
    phone: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
    sort_by: OwnerSortBy = Query(default="created_at"),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    service = OwnerService(db)
    owners, total = service.list_owners(
        tenant.tenant_id,
        search=search,
        phone=phone,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
    )
    return {
        "data": service.build_owner_list_response(tenant.tenant_id, owners),
        "meta": ListMeta(
            page=page if page_size is not None else 1,
            page_size=page_size if page_size is not None else len(owners),
            total=total,
        ).model_dump(),
    }


@router.get("/{owner_id}")
def get_owner(
    owner_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    service = OwnerService(db)
    owner = service.get_owner(tenant.tenant_id, owner_id)
    return {"data": service.build_owner_response(tenant.tenant_id, owner), "meta": {}}


@router.get("/{owner_id}/receivables")
def get_owner_receivables(
    owner_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    patient_id: uuid.UUID | None = Query(default=None),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    data, meta = OwnerReceivablesService(db).get(tenant.tenant_id, owner_id, page=page, page_size=page_size,
        date_from=date_from, date_to=date_to, patient_id=patient_id)
    return {"data": data.model_dump(mode="json"), "meta": meta}


@router.get("/{owner_id}/receivables/activity")
def get_owner_receivables_activity(
    owner_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    data, meta = OwnerReceivablesService(db).activity(tenant.tenant_id, owner_id, page=page, page_size=page_size)
    return {"data": data.model_dump(mode="json"), "meta": meta}


@router.patch("/{owner_id}")
def update_owner(
    owner_id: uuid.UUID,
    payload: OwnerUpdate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    service = OwnerService(db)
    owner = service.update_owner(tenant.tenant_id, owner_id, payload)
    return {"data": service.build_owner_response(tenant.tenant_id, owner), "meta": {}}


@router.delete("/{owner_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_owner(
    owner_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> Response:
    OwnerService(db).delete_owner(
        tenant.tenant_id, owner_id, allow_patient_deletion=tenant.role in ("medico_veterinario", "superadmin"),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

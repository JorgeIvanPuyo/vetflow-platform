import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.common import ListMeta
from app.schemas.owner import OwnerCreate, OwnerRead, OwnerUpdate
from app.services.owner import OwnerService

router = APIRouter(prefix="/owners", tags=["owners"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_owner(
    payload: OwnerCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    owner = OwnerService(db).create_owner(tenant.tenant_id, payload)
    return {"data": OwnerRead.model_validate(owner).model_dump(mode="json"), "meta": {}}


@router.get("")
def list_owners(
    search: str | None = Query(default=None),
    phone: str | None = Query(default=None),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    owners, total = OwnerService(db).list_owners(
        tenant.tenant_id,
        search=search,
        phone=phone,
    )
    return {
        "data": [OwnerRead.model_validate(owner).model_dump(mode="json") for owner in owners],
        "meta": ListMeta(page=1, page_size=len(owners), total=total).model_dump(),
    }


@router.get("/{owner_id}")
def get_owner(
    owner_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    owner = OwnerService(db).get_owner(tenant.tenant_id, owner_id)
    return {"data": OwnerRead.model_validate(owner).model_dump(mode="json"), "meta": {}}


@router.patch("/{owner_id}")
def update_owner(
    owner_id: uuid.UUID,
    payload: OwnerUpdate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    owner = OwnerService(db).update_owner(tenant.tenant_id, owner_id, payload)
    return {"data": OwnerRead.model_validate(owner).model_dump(mode="json"), "meta": {}}


@router.delete("/{owner_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_owner(
    owner_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> Response:
    OwnerService(db).delete_owner(tenant.tenant_id, owner_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

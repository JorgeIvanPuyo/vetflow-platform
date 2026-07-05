import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, require_superadmin
from app.db.session import get_db
from app.schemas.admin_users import (
    AdminUserRead,
    InviteUserRequest,
    InviteUserResponse,
    TenantOptionRead,
)
from app.schemas.common import ListMeta
from app.services.admin_user import AdminUserService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def list_users(
    tenant_id: uuid.UUID | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: TenantContext = Depends(require_superadmin),
    db: Session = Depends(get_db),
) -> dict:
    users, total = AdminUserService(db).list_users(
        tenant_id=tenant_id,
        is_active=is_active,
        search=search,
        limit=limit,
        offset=offset,
    )
    return {
        "data": [
            AdminUserRead.model_validate(user).model_dump(mode="json")
            for user in users
        ],
        "meta": ListMeta(
            page=(offset // limit) + 1,
            page_size=len(users),
            total=total,
        ).model_dump(),
    }


@router.post("/users/invite", status_code=status.HTTP_201_CREATED)
def invite_user(
    payload: InviteUserRequest,
    _: TenantContext = Depends(require_superadmin),
    db: Session = Depends(get_db),
) -> dict:
    user, reset_link = AdminUserService(db).invite_user(payload)
    return {
        "data": InviteUserResponse(
            user=AdminUserRead.model_validate(user),
            password_reset_link=reset_link,
        ).model_dump(mode="json"),
        "meta": {},
    }


@router.get("/tenants")
def list_tenants(
    _: TenantContext = Depends(require_superadmin),
    db: Session = Depends(get_db),
) -> dict:
    tenants = AdminUserService(db).list_tenants()
    return {
        "data": [
            TenantOptionRead.model_validate(tenant).model_dump(mode="json")
            for tenant in tenants
        ],
        "meta": {},
    }

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.models.tenant import Tenant
from app.schemas.auth import CurrentUserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
def get_current_user(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    if tenant.user_id is None:
        raise AppError(
            status_code=403,
            code="user_not_registered",
            message="No tienes acceso a esta aplicación",
        )

    clinic = db.get(Tenant, tenant.tenant_id)
    tenant_name = clinic.display_name or clinic.name if clinic else ""

    return {
        "data": CurrentUserRead(
            id=tenant.user_id,
            email=tenant.user_email or "",
            full_name=tenant.user_full_name or "",
            role=tenant.role or "",
            is_active=True,
            tenant_id=tenant.tenant_id,
            tenant_name=tenant_name,
        ).model_dump(mode="json"),
        "meta": {},
    }

import uuid
from dataclasses import dataclass

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.firebase import FirebaseTokenVerificationError, verify_id_token
from app.db.session import get_db
from app.models.tenant import Tenant
from app.repositories.user import UserRepository


@dataclass(frozen=True)
class TenantContext:
    tenant_id: uuid.UUID
    user_id: uuid.UUID | None = None
    user_email: str | None = None
    user_full_name: str | None = None


def _resolve_development_tenant(x_tenant_id: str | None, db: Session) -> TenantContext:
    if not x_tenant_id:
        raise AppError(
            status_code=400,
            code="missing_tenant_header",
            message="X-Tenant-Id header is required in development fallback",
        )

    try:
        tenant_id = uuid.UUID(x_tenant_id)
    except ValueError as exc:
        raise AppError(
            status_code=400,
            code="invalid_tenant_header",
            message="X-Tenant-Id must be a valid UUID",
        ) from exc

    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise AppError(
            status_code=404,
            code="tenant_not_found",
            message="Tenant not found",
        )

    return TenantContext(tenant_id=tenant_id)


def get_tenant_context(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
) -> TenantContext:
    settings = get_settings()

    if not authorization:
        if settings.app_env == "development":
            return _resolve_development_tenant(x_tenant_id, db)

        raise AppError(
            status_code=401,
            code="missing_auth_token",
            message="Authorization bearer token is required",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AppError(
            status_code=401,
            code="missing_auth_token",
            message="Authorization bearer token is required",
        )

    try:
        decoded_token = verify_id_token(token)
    except FirebaseTokenVerificationError as exc:
        raise AppError(
            status_code=401,
            code="invalid_auth_token",
            message="Invalid authentication token",
        ) from exc

    email = decoded_token.get("email")
    if not isinstance(email, str) or not email.strip():
        raise AppError(
            status_code=401,
            code="auth_email_missing",
            message="Authenticated token does not include an email",
        )

    user = UserRepository(db).get_by_email(email.strip())
    if user is None:
        raise AppError(
            status_code=403,
            code="user_not_registered",
            message="No tienes acceso a esta aplicación",
        )

    if not user.is_active:
        raise AppError(
            status_code=403,
            code="inactive_user",
            message="User is inactive",
        )

    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise AppError(
            status_code=404,
            code="tenant_not_found",
            message="Tenant not found",
        )

    return TenantContext(
        tenant_id=user.tenant_id,
        user_id=user.id,
        user_email=user.email,
        user_full_name=user.full_name,
    )

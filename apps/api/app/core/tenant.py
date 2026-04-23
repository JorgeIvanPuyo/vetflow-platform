import uuid
from dataclasses import dataclass

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.models.tenant import Tenant


@dataclass(frozen=True)
class TenantContext:
    tenant_id: uuid.UUID


def get_tenant_context(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
) -> TenantContext:
    if not x_tenant_id:
        raise AppError(
            status_code=400,
            code="missing_tenant_header",
            message="X-Tenant-Id header is required",
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

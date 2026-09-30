"""Clinic operations are shared; professional responsibility is explicit."""
from fastapi import Depends, Request

from app.core.errors import AppError
from app.core.roles import Role
from app.core.tenant import TenantContext, get_tenant_context
from app.models.user import User


CLINIC_OPERATOR_ROLES = (
    Role.CLINIC_ADMIN.value,
    Role.MEDICO_VETERINARIO.value,
    Role.CONTADOR.value,
    Role.SECRETARIA.value,
)


def require_clinic_operator(
    tenant: TenantContext = Depends(get_tenant_context),
) -> TenantContext:
    if tenant.role not in CLINIC_OPERATOR_ROLES:
        raise AppError(403, "forbidden", "No tienes permiso para esta acción")
    return tenant


def require_supplier_manager(
    tenant: TenantContext = Depends(get_tenant_context),
) -> TenantContext:
    return require_clinic_operator(tenant)


def require_service_editor(
    tenant: TenantContext = Depends(get_tenant_context),
) -> TenantContext:
    return require_clinic_operator(tenant)


def require_veterinarian(
    tenant: TenantContext = Depends(get_tenant_context),
) -> TenantContext:
    if tenant.role != Role.MEDICO_VETERINARIO.value:
        raise AppError(403, "forbidden", "Esta acción requiere un médico veterinario")
    return tenant


def clinical_read_or_veterinarian(
    request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
) -> TenantContext:
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        require_veterinarian(tenant)
    return tenant


def ensure_veterinarian(user: User, *, fiscal: bool = False) -> None:
    """Validate an already tenant-scoped responsible user, never the operator."""
    if user.role != Role.MEDICO_VETERINARIO.value or not user.is_active:
        code = "invalid_fiscal_user" if fiscal else "invalid_responsible_user"
        raise AppError(422, code, "El responsable debe ser un médico veterinario activo")

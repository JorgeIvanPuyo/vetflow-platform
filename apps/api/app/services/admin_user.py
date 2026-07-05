import secrets
import uuid

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.firebase import (
    FirebaseUserProvisioningError,
    create_firebase_user,
    generate_password_reset_link,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.admin_user import AdminUserRepository
from app.repositories.user import UserRepository
from app.schemas.admin_users import InviteUserRequest


class AdminUserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = AdminUserRepository(db)
        self.user_repository = UserRepository(db)

    def list_users(
        self,
        *,
        tenant_id: uuid.UUID | None,
        is_active: bool | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        users, total = self.repository.list_users(
            tenant_id=tenant_id,
            is_active=is_active,
            search=search,
            limit=limit,
            offset=offset,
        )
        return [self._build_user_response(user) for user in users], total

    def list_tenants(self) -> list[Tenant]:
        return self.repository.list_tenants()

    def invite_user(self, payload: InviteUserRequest) -> tuple[dict, str | None]:
        tenant = self.db.get(Tenant, payload.tenant_id)
        if tenant is None:
            raise AppError(404, "tenant_not_found", "La clínica indicada no existe")

        existing = self.user_repository.get_by_email(payload.email)
        if existing is not None:
            raise AppError(409, "user_already_exists", "Ya existe un usuario con ese correo")

        temporary_password = secrets.token_urlsafe(16)
        try:
            create_firebase_user(
                email=payload.email,
                display_name=payload.full_name,
                password=temporary_password,
            )
        except FirebaseUserProvisioningError as exc:
            raise AppError(
                502,
                "firebase_user_create_failed",
                "No se pudo crear la cuenta de acceso",
            ) from exc

        user = self.repository.create_user(
            tenant_id=payload.tenant_id,
            email=payload.email,
            full_name=payload.full_name,
            role=payload.role,
        )
        self.db.commit()
        self.db.refresh(user)

        reset_link: str | None = None
        try:
            reset_link = generate_password_reset_link(payload.email)
        except FirebaseUserProvisioningError:
            reset_link = None

        return self._build_user_response(user), reset_link

    def _build_user_response(self, user: User) -> dict:
        tenant_name = ""
        if user.tenant is not None:
            tenant_name = user.tenant.display_name or user.tenant.name
        return {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "tenant_id": user.tenant_id,
            "tenant_name": tenant_name,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

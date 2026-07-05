import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.user import User


class AdminUserRepository:
    """Cross-tenant user access. ONLY for superadmin-gated endpoints."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_users(
        self,
        *,
        tenant_id: uuid.UUID | None = None,
        is_active: bool | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[User], int]:
        filters = []
        if tenant_id is not None:
            filters.append(User.tenant_id == tenant_id)
        if is_active is not None:
            filters.append(User.is_active.is_(is_active))
        if search and search.strip():
            pattern = f"%{search.strip().lower()}%"
            filters.append(
                or_(
                    func.lower(User.full_name).like(pattern),
                    func.lower(User.email).like(pattern),
                )
            )

        base = select(User).where(*filters)

        total = self.db.scalar(
            select(func.count()).select_from(base.subquery())
        )

        statement = (
            base.order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        users = list(self.db.scalars(statement).all())
        return users, int(total or 0)

    def create_user(
        self,
        *,
        tenant_id: uuid.UUID,
        email: str,
        full_name: str,
        role: str,
    ) -> User:
        user = User(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            email=email,
            full_name=full_name,
            role=role,
            is_active=True,
        )
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def list_tenants(self) -> list[Tenant]:
        statement = select(Tenant).order_by(func.lower(Tenant.name).asc())
        return list(self.db.scalars(statement).all())

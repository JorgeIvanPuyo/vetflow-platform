import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(func.lower(User.email) == email.lower())
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_id(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
        statement = select(User).where(
            User.id == user_id,
            User.tenant_id == tenant_id,
        )
        return self.db.scalar(statement)

    def list_active_by_tenant(self, tenant_id: uuid.UUID) -> list[User]:
        statement = (
            select(User)
            .where(
                User.tenant_id == tenant_id,
                User.is_active.is_(True),
            )
            .order_by(func.lower(User.full_name).asc())
        )
        return list(self.db.scalars(statement).all())

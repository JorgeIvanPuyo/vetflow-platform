import uuid

from sqlalchemy import select
from sqlalchemy.orm import object_session

from app.models.user import User


def headers_for_user(user: User) -> dict[str, str]:
    """Authenticate a persisted user through the development email resolver."""
    return {"X-User-Email": user.email}


def _headers_for_role(tenant, role: str, *, identity: str, full_name: str) -> dict[str, str]:
    db = object_session(tenant)
    email = f"test-{identity}-{tenant.id}@example.com"
    user = db.scalar(select(User).where(User.tenant_id == tenant.id, User.email == email))
    if user is None:
        user = User(
            id=uuid.uuid4(), tenant_id=tenant.id, email=email,
            full_name=full_name, role=role, is_active=True,
        )
        db.add(user)
        db.commit()
    assert user.role == role and user.is_active
    return headers_for_user(user)


def veterinarian_headers(tenant) -> dict[str, str]:
    return _headers_for_role(
        tenant, "medico_veterinario", identity="veterinarian", full_name="Test Veterinarian",
    )


def clinic_admin_headers(tenant) -> dict[str, str]:
    return _headers_for_role(
        tenant, "clinic_admin", identity="clinic-admin", full_name="Test Clinic Admin",
    )

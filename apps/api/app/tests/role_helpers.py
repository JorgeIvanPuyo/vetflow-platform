import uuid

from sqlalchemy import select
from sqlalchemy.orm import object_session

from app.models.user import User


def veterinarian_headers(tenant):
    db = object_session(tenant)
    email = f"test-veterinarian-{tenant.id}@example.com"
    user = db.scalar(select(User).where(User.tenant_id == tenant.id, User.email == email))
    if user is None:
        user = User(id=uuid.uuid4(), tenant_id=tenant.id, email=email,
                    full_name="Test Veterinarian", role="medico_veterinario", is_active=True)
        db.add(user)
        db.commit()
    return {"X-User-Email": email}

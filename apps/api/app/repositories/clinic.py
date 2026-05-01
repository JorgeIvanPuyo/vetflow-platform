import uuid

from sqlalchemy.orm import Session

from app.models.tenant import Tenant


class ClinicRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_profile(self, tenant_id: uuid.UUID) -> Tenant | None:
        return self.db.get(Tenant, tenant_id)

    def update_profile(self, tenant: Tenant, updates: dict) -> Tenant:
        for field, value in updates.items():
            setattr(tenant, field, value)

        self.db.add(tenant)
        self.db.flush()
        self.db.refresh(tenant)
        return tenant

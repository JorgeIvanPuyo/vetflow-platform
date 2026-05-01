import uuid

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.clinic import ClinicRepository
from app.repositories.user import UserRepository
from app.schemas.clinic import ClinicProfileUpdate


class ClinicService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.clinic_repository = ClinicRepository(db)
        self.user_repository = UserRepository(db)

    def get_profile(self, tenant_id: uuid.UUID) -> Tenant:
        tenant = self.clinic_repository.get_profile(tenant_id)
        if tenant is None:
            raise AppError(404, "clinic_not_found", "Clinic profile not found")
        return tenant

    def update_profile(
        self,
        tenant_id: uuid.UUID,
        payload: ClinicProfileUpdate,
    ) -> Tenant:
        tenant = self.get_profile(tenant_id)
        updates = payload.model_dump(exclude_unset=True)
        updated_tenant = self.clinic_repository.update_profile(tenant, updates)
        self.db.commit()
        return updated_tenant

    def list_team(self, tenant_id: uuid.UUID) -> list[User]:
        self.get_profile(tenant_id)
        return self.user_repository.list_active_by_tenant(tenant_id)

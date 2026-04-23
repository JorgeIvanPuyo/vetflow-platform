import uuid

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.owner import Owner
from app.repositories.owner import OwnerRepository
from app.repositories.patient import PatientRepository
from app.schemas.owner import OwnerCreate, OwnerUpdate


class OwnerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.owner_repository = OwnerRepository(db)
        self.patient_repository = PatientRepository(db)

    def create_owner(self, tenant_id: uuid.UUID, payload: OwnerCreate) -> Owner:
        owner = Owner(tenant_id=tenant_id, **payload.model_dump())
        self.owner_repository.create(owner)
        self.db.commit()
        return owner

    def list_owners(
        self,
        tenant_id: uuid.UUID,
        *,
        search: str | None = None,
        phone: str | None = None,
    ) -> tuple[list[Owner], int]:
        return self.owner_repository.list(tenant_id, search=search, phone=phone)

    def get_owner(self, tenant_id: uuid.UUID, owner_id: uuid.UUID) -> Owner:
        owner = self.owner_repository.get_by_id(tenant_id, owner_id)
        if owner is None:
            raise AppError(404, "owner_not_found", "Owner not found")
        return owner

    def update_owner(
        self, tenant_id: uuid.UUID, owner_id: uuid.UUID, payload: OwnerUpdate
    ) -> Owner:
        owner = self.get_owner(tenant_id, owner_id)
        updates = payload.model_dump(exclude_unset=True)
        if "full_name" in updates and updates["full_name"] is None:
            raise AppError(422, "validation_error", "full_name cannot be null")
        if "phone" in updates and updates["phone"] is None:
            raise AppError(422, "validation_error", "phone cannot be null")
        updated_owner = self.owner_repository.update(owner, updates)
        self.db.commit()
        return updated_owner

    def delete_owner(self, tenant_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        owner = self.get_owner(tenant_id, owner_id)
        if self.patient_repository.exists_for_owner(tenant_id, owner_id):
            raise AppError(
                409,
                "owner_has_patients",
                "Owner has patients and cannot be deleted",
            )

        self.owner_repository.delete(owner)
        self.db.commit()

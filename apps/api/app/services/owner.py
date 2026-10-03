import uuid

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.consultation import Consultation
from app.models.exam import Exam
from app.models.follow_up import FollowUp
from app.models.owner import Owner
from app.models.patient import Patient
from app.models.patient_file_reference import PatientFileReference
from app.models.patient_preventive_care import PatientPreventiveCare
from app.models.sale import Sale
from app.repositories.owner import OwnerRepository
from app.schemas.owner import OwnerCreate, OwnerSortBy, OwnerUpdate


class OwnerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.owner_repository = OwnerRepository(db)

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
        page: int = 1,
        page_size: int | None = None,
        sort_by: OwnerSortBy = "created_at",
    ) -> tuple[list[Owner], int]:
        return self.owner_repository.list(
            tenant_id,
            search=search,
            phone=phone,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
        )

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
        if "is_active" in updates and updates["is_active"] is None:
            raise AppError(422, "validation_error", "is_active cannot be null")
        updated_owner = self.owner_repository.update(owner, updates)
        self.db.commit()
        return updated_owner

    def delete_owner(
        self, tenant_id: uuid.UUID, owner_id: uuid.UUID, *, allow_patient_deletion: bool = True,
    ) -> None:
        try:
            owner = self.owner_repository.get_by_id(tenant_id, owner_id, for_update=True)
            if owner is None:
                raise AppError(404, "owner_not_found", "Owner not found")
            if self.db.scalar(select(Sale.id).where(
                Sale.tenant_id == tenant_id, Sale.owner_id == owner_id,
            ).limit(1)) is not None:
                raise self._commercial_history_error()
            patient_ids = list(
                self.db.scalars(
                    select(Patient.id).where(
                        Patient.tenant_id == tenant_id,
                        Patient.owner_id == owner_id,
                    )
                ).all()
            )

            if patient_ids and not allow_patient_deletion:
                raise AppError(403, "forbidden", "No puedes eliminar un propietario con pacientes e historia clínica")

            if patient_ids:
                self.db.execute(
                    delete(PatientFileReference).where(
                        PatientFileReference.tenant_id == tenant_id,
                        PatientFileReference.patient_id.in_(patient_ids),
                    )
                )
                self.db.execute(
                    delete(PatientPreventiveCare).where(
                        PatientPreventiveCare.tenant_id == tenant_id,
                        PatientPreventiveCare.patient_id.in_(patient_ids),
                    )
                )
                self.db.execute(
                    delete(FollowUp).where(
                        FollowUp.tenant_id == tenant_id,
                        FollowUp.patient_id.in_(patient_ids),
                    )
                )
                self.db.execute(
                    delete(Exam).where(
                        Exam.tenant_id == tenant_id,
                        Exam.patient_id.in_(patient_ids),
                    )
                )
                self.db.execute(
                    delete(Consultation).where(
                        Consultation.tenant_id == tenant_id,
                        Consultation.patient_id.in_(patient_ids),
                    )
                )
                self.db.execute(
                    delete(Patient).where(
                        Patient.tenant_id == tenant_id,
                        Patient.owner_id == owner_id,
                    )
                )

            self.owner_repository.delete(owner)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            # The FK also protects references outside the scoped history query.
            if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) == "fk_sales_owner_id_preserve_history":
                raise self._commercial_history_error() from exc
            raise
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _commercial_history_error() -> AppError:
        return AppError(
            409, "owner_has_commercial_history",
            "Este propietario tiene ventas y no se puede eliminar. Puedes archivarlo.",
        )

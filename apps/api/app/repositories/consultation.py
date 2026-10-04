import uuid

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session, contains_eager, selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.models.catalog_item import CatalogItem
from app.models.consultation import (
    Consultation,
    ConsultationMedication,
    ConsultationStudyRequest,
)
from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.owner import Owner
from app.models.patient import Patient
from app.models.user import User


class ConsultationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _patient_join(self, tenant_id: uuid.UUID) -> ColumnElement[bool]:
        return and_(Patient.id == Consultation.patient_id, Patient.tenant_id == tenant_id)

    def _owner_join(self, tenant_id: uuid.UUID) -> ColumnElement[bool]:
        return and_(Owner.id == Patient.owner_id, Owner.tenant_id == tenant_id)

    def _read_statement(self, tenant_id: uuid.UUID) -> Select[tuple[Consultation]]:
        """Scope both the required patient chain and every loaded child in SQL.

        Historical single-column FKs can link rows from different tenants.
        Refresh already loaded relationships so the session identity map cannot
        retain children loaded earlier through an unscoped ORM relationship.
        """
        return (
            select(Consultation)
            .join(Patient, self._patient_join(tenant_id))
            .join(Owner, self._owner_join(tenant_id))
            .where(Consultation.tenant_id == tenant_id)
            .options(
                contains_eager(Consultation.patient).contains_eager(Patient.owner),
                selectinload(
                    Consultation.parent_consultation.and_(Consultation.tenant_id == tenant_id)
                ),
                selectinload(
                    Consultation.created_by_user.and_(User.tenant_id == tenant_id)
                ),
                selectinload(
                    Consultation.attending_user.and_(User.tenant_id == tenant_id)
                ),
                selectinload(
                    Consultation.medications.and_(ConsultationMedication.tenant_id == tenant_id)
                ).options(
                    selectinload(
                        ConsultationMedication.inventory_item.and_(
                            InventoryItem.tenant_id == tenant_id
                        )
                    ),
                    selectinload(
                        ConsultationMedication.inventory_movement.and_(
                            InventoryMovement.tenant_id == tenant_id
                        )
                    ),
                ),
                selectinload(
                    Consultation.study_requests.and_(ConsultationStudyRequest.tenant_id == tenant_id)
                ).selectinload(
                    ConsultationStudyRequest.exam_catalog_item.and_(CatalogItem.tenant_id == tenant_id)
                ),
            )
            .execution_options(populate_existing=True)
        )

    def create(self, consultation: Consultation) -> Consultation:
        self.db.add(consultation)
        self.db.flush()
        self.db.refresh(consultation)
        return consultation

    def get_by_id(
        self, tenant_id: uuid.UUID, consultation_id: uuid.UUID
    ) -> Consultation | None:
        statement = self._read_statement(tenant_id).where(Consultation.id == consultation_id)
        return self.db.scalar(statement)

    def list_by_patient(
        self, tenant_id: uuid.UUID, patient_id: uuid.UUID
    ) -> tuple[list[Consultation], int]:
        statement = (
            self._read_statement(tenant_id)
            .where(Consultation.patient_id == patient_id)
            .order_by(Consultation.visit_date.desc())
        )
        consultations = list(self.db.scalars(statement).all())

        count_statement = (
            select(func.count())
            .select_from(Consultation)
            .join(Patient, self._patient_join(tenant_id))
            .join(Owner, self._owner_join(tenant_id))
            .where(Consultation.tenant_id == tenant_id, Consultation.patient_id == patient_id)
        )
        total = self.db.scalar(count_statement) or 0
        return consultations, total

    def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Consultation], int]:
        filters = [Consultation.tenant_id == tenant_id]
        if status:
            filters.append(Consultation.status == status)
        if search and search.strip():
            search_pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    Patient.name.ilike(search_pattern),
                    Owner.full_name.ilike(search_pattern),
                    Consultation.reason.ilike(search_pattern),
                )
            )

        tenant_patient_join = self._patient_join(tenant_id)
        tenant_owner_join = self._owner_join(tenant_id)
        statement = (
            select(Consultation)
            .join(Patient, tenant_patient_join)
            .join(Owner, tenant_owner_join)
            .where(*filters)
            .options(
                contains_eager(Consultation.patient).contains_eager(Patient.owner),
                selectinload(Consultation.created_by_user),
                selectinload(Consultation.attending_user),
            )
            .order_by(Consultation.visit_date.desc(), Consultation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        consultations = list(self.db.scalars(statement).unique().all())

        count_statement = (
            select(func.count())
            .select_from(Consultation)
            .join(Patient, tenant_patient_join)
            .join(Owner, tenant_owner_join)
            .where(*filters)
        )
        total = self.db.scalar(count_statement) or 0
        return consultations, total

    def update(self, consultation: Consultation, updates: dict) -> Consultation:
        for field, value in updates.items():
            setattr(consultation, field, value)

        self.db.add(consultation)
        self.db.flush()
        self.db.refresh(consultation)
        return consultation

    def delete(self, consultation: Consultation) -> None:
        self.db.delete(consultation)
        self.db.flush()

    def create_medication(
        self,
        medication: ConsultationMedication,
    ) -> ConsultationMedication:
        self.db.add(medication)
        self.db.flush()
        self.db.refresh(medication)
        return medication

    def get_medication_by_id(
        self,
        tenant_id: uuid.UUID,
        medication_id: uuid.UUID,
    ) -> ConsultationMedication | None:
        statement = select(ConsultationMedication).where(
            ConsultationMedication.id == medication_id,
            ConsultationMedication.tenant_id == tenant_id,
        ).options(
            selectinload(ConsultationMedication.inventory_item.and_(
                InventoryItem.tenant_id == tenant_id
            )),
            selectinload(ConsultationMedication.inventory_movement.and_(
                InventoryMovement.tenant_id == tenant_id
            )),
        ).execution_options(populate_existing=True)
        return self.db.scalar(statement)

    def delete_medication(self, medication: ConsultationMedication) -> None:
        self.db.delete(medication)
        self.db.flush()

    def delete_medications_by_consultation(
        self,
        tenant_id: uuid.UUID,
        consultation_id: uuid.UUID,
    ) -> None:
        medications = self.db.scalars(
            select(ConsultationMedication).where(
                ConsultationMedication.tenant_id == tenant_id,
                ConsultationMedication.consultation_id == consultation_id,
            )
        ).all()
        for medication in medications:
            self.db.delete(medication)
        self.db.flush()

    def create_study_request(
        self,
        study_request: ConsultationStudyRequest,
    ) -> ConsultationStudyRequest:
        self.db.add(study_request)
        self.db.flush()
        self.db.refresh(study_request)
        return study_request

    def get_study_request_by_id(
        self,
        tenant_id: uuid.UUID,
        study_request_id: uuid.UUID,
    ) -> ConsultationStudyRequest | None:
        statement = select(ConsultationStudyRequest).where(
            ConsultationStudyRequest.id == study_request_id,
            ConsultationStudyRequest.tenant_id == tenant_id,
        )
        return self.db.scalar(statement)

    def delete_study_request(
        self,
        study_request: ConsultationStudyRequest,
    ) -> None:
        self.db.delete(study_request)
        self.db.flush()

    def delete_study_requests_by_consultation(
        self,
        tenant_id: uuid.UUID,
        consultation_id: uuid.UUID,
    ) -> None:
        study_requests = self.db.scalars(
            select(ConsultationStudyRequest).where(
                ConsultationStudyRequest.tenant_id == tenant_id,
                ConsultationStudyRequest.consultation_id == consultation_id,
            )
        ).all()
        for study_request in study_requests:
            self.db.delete(study_request)
        self.db.flush()

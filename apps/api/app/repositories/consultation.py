import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.consultation import (
    Consultation,
    ConsultationMedication,
    ConsultationStudyRequest,
)


class ConsultationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, consultation: Consultation) -> Consultation:
        self.db.add(consultation)
        self.db.flush()
        self.db.refresh(consultation)
        return consultation

    def get_by_id(
        self, tenant_id: uuid.UUID, consultation_id: uuid.UUID
    ) -> Consultation | None:
        statement = select(Consultation).where(
            Consultation.id == consultation_id,
            Consultation.tenant_id == tenant_id,
        ).options(
            selectinload(Consultation.created_by_user),
            selectinload(Consultation.attending_user),
            selectinload(Consultation.medications).selectinload(
                ConsultationMedication.inventory_item,
            ),
            selectinload(Consultation.medications).selectinload(
                ConsultationMedication.inventory_movement,
            ),
            selectinload(Consultation.study_requests),
        )
        return self.db.scalar(statement)

    def list_by_patient(
        self, tenant_id: uuid.UUID, patient_id: uuid.UUID
    ) -> tuple[list[Consultation], int]:
        statement = (
            select(Consultation)
            .where(
                Consultation.tenant_id == tenant_id,
                Consultation.patient_id == patient_id,
            )
            .options(
                selectinload(Consultation.created_by_user),
                selectinload(Consultation.attending_user),
                selectinload(Consultation.medications).selectinload(
                    ConsultationMedication.inventory_item,
                ),
                selectinload(Consultation.medications).selectinload(
                    ConsultationMedication.inventory_movement,
                ),
                selectinload(Consultation.study_requests),
            )
            .order_by(Consultation.visit_date.desc())
        )
        consultations = list(self.db.scalars(statement).all())

        count_statement = select(func.count()).select_from(Consultation).where(
            Consultation.tenant_id == tenant_id,
            Consultation.patient_id == patient_id,
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
            selectinload(ConsultationMedication.inventory_item),
            selectinload(ConsultationMedication.inventory_movement),
        )
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

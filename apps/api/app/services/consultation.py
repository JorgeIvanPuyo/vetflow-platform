import uuid
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.consultation import (
    Consultation,
    ConsultationMedication,
    ConsultationStudyRequest,
)
from app.models.exam import Exam
from app.models.follow_up import FollowUp
from app.models.inventory_movement import InventoryMovement
from app.models.patient_file_reference import PatientFileReference
from app.models.patient_preventive_care import PatientPreventiveCare
from app.models.patient import Patient
from app.repositories.consultation import ConsultationRepository
from app.repositories.exam import ExamRepository
from app.repositories.file_reference import FileReferenceRepository
from app.repositories.follow_up import FollowUpRepository
from app.repositories.inventory import InventoryRepository
from app.repositories.patient import PatientRepository
from app.repositories.preventive_care import PreventiveCareRepository
from app.schemas.consultation import (
    ConsultationCreate,
    ConsultationMedicationCreate,
    ConsultationStudyRequestCreate,
    ConsultationUpdate,
)


class ConsultationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.consultation_repository = ConsultationRepository(db)
        self.exam_repository = ExamRepository(db)
        self.preventive_care_repository = PreventiveCareRepository(db)
        self.file_reference_repository = FileReferenceRepository(db)
        self.follow_up_repository = FollowUpRepository(db)
        self.inventory_repository = InventoryRepository(db)
        self.patient_repository = PatientRepository(db)

    def create_consultation(
        self,
        tenant_id: uuid.UUID,
        payload: ConsultationCreate,
        *,
        created_by_user_id: uuid.UUID | None = None,
        attending_user_id: uuid.UUID | None = None,
    ) -> Consultation:
        patient = self.patient_repository.get_by_id(tenant_id, payload.patient_id)
        if patient is None:
            patient_any_tenant = self.db.get(Patient, payload.patient_id)
            if patient_any_tenant is not None:
                raise AppError(
                    409,
                    "invalid_cross_tenant_access",
                    "Patient does not belong to the provided tenant",
                )
            raise AppError(
                404,
                "patient_not_found",
                "Patient not found for the provided tenant",
            )

        consultation = Consultation(
            tenant_id=tenant_id,
            created_by_user_id=created_by_user_id,
            attending_user_id=attending_user_id,
            **payload.model_dump(),
        )
        self.consultation_repository.create(consultation)
        self.db.commit()
        return consultation

    def get_consultation(
        self, tenant_id: uuid.UUID, consultation_id: uuid.UUID
    ) -> Consultation:
        consultation = self.consultation_repository.get_by_id(
            tenant_id,
            consultation_id,
        )
        if consultation is None:
            raise AppError(404, "consultation_not_found", "Consultation not found")
        return consultation

    def update_consultation(
        self,
        tenant_id: uuid.UUID,
        consultation_id: uuid.UUID,
        payload: ConsultationUpdate,
    ) -> Consultation:
        consultation = self.get_consultation(tenant_id, consultation_id)
        updates = payload.model_dump(exclude_unset=True)
        if "visit_date" in updates and updates["visit_date"] is None:
            raise AppError(422, "validation_error", "visit_date cannot be null")
        if "reason" in updates and updates["reason"] is None:
            raise AppError(422, "validation_error", "reason cannot be null")
        self._validate_update_numbers(updates)

        updated_consultation = self.consultation_repository.update(
            consultation,
            updates,
        )
        self.db.commit()
        return updated_consultation

    def delete_consultation(
        self,
        tenant_id: uuid.UUID,
        consultation_id: uuid.UUID,
    ) -> None:
        consultation = self.get_consultation(tenant_id, consultation_id)

        exams, _ = self.exam_repository.list_by_consultation(
            tenant_id,
            consultation_id,
        )
        for exam in exams:
            self.exam_repository.update(exam, {"consultation_id": None})

        self.consultation_repository.delete_medications_by_consultation(
            tenant_id,
            consultation_id,
        )
        self.consultation_repository.delete_study_requests_by_consultation(
            tenant_id,
            consultation_id,
        )
        self.consultation_repository.delete(consultation)
        self.db.commit()

    def create_medication(
        self,
        tenant_id: uuid.UUID,
        consultation_id: uuid.UUID,
        payload: ConsultationMedicationCreate,
    ) -> ConsultationMedication:
        consultation = self.get_consultation(tenant_id, consultation_id)
        medication_data = payload.model_dump()

        if payload.inventory_item_id is not None:
            item = self.inventory_repository.get_item_by_id(
                tenant_id,
                payload.inventory_item_id,
            )
            if item is None:
                raise AppError(
                    404,
                    "inventory_item_not_found",
                    "Inventory item not found",
                )
            if payload.quantity_used is None or payload.quantity_used <= Decimal("0"):
                raise AppError(
                    422,
                    "invalid_stock_quantity",
                    "quantity_used is required when inventory_item_id is provided",
                )
            if item.current_stock - payload.quantity_used < Decimal("0"):
                raise AppError(
                    409,
                    "insufficient_stock",
                    "Insufficient stock for this medication",
                )

            unit_sale_price = item.sale_price_ars
            total_sale_price = (
                self._quantize_money(unit_sale_price * payload.quantity_used)
                if unit_sale_price is not None
                else None
            )
            movement = InventoryMovement(
                tenant_id=tenant_id,
                inventory_item_id=item.id,
                movement_type="exit",
                reason="consultation_use",
                quantity=payload.quantity_used,
                unit_sale_price_ars=unit_sale_price,
                total_sale_price_ars=total_sale_price,
                related_patient_id=consultation.patient_id,
                related_consultation_id=consultation.id,
                notes=f"Uso en consulta: {consultation.reason}",
            )
            self.inventory_repository.create_movement(movement)
            self.inventory_repository.update_item(
                item,
                {"current_stock": item.current_stock - payload.quantity_used},
            )

            medication_data["medication_name"] = (
                payload.medication_name or item.name
            )
            medication_data["supplied_by_clinic"] = True
            medication_data["inventory_movement_id"] = movement.id
        else:
            medication_data["supplied_by_clinic"] = bool(payload.supplied_by_clinic)

        medication = ConsultationMedication(
            tenant_id=tenant_id,
            consultation_id=consultation_id,
            **medication_data,
        )
        self.consultation_repository.create_medication(medication)
        self.db.commit()
        return medication

    def delete_medication(
        self,
        tenant_id: uuid.UUID,
        medication_id: uuid.UUID,
    ) -> None:
        medication = self.consultation_repository.get_medication_by_id(
            tenant_id,
            medication_id,
        )
        if medication is None:
            raise AppError(
                404,
                "consultation_medication_not_found",
                "Consultation medication not found",
            )

        self.consultation_repository.delete_medication(medication)
        self.db.commit()

    def create_study_request(
        self,
        tenant_id: uuid.UUID,
        consultation_id: uuid.UUID,
        payload: ConsultationStudyRequestCreate,
    ) -> ConsultationStudyRequest:
        self.get_consultation(tenant_id, consultation_id)
        study_request = ConsultationStudyRequest(
            tenant_id=tenant_id,
            consultation_id=consultation_id,
            **payload.model_dump(),
        )
        self.consultation_repository.create_study_request(study_request)
        self.db.commit()
        return study_request

    def delete_study_request(
        self,
        tenant_id: uuid.UUID,
        study_request_id: uuid.UUID,
    ) -> None:
        study_request = self.consultation_repository.get_study_request_by_id(
            tenant_id,
            study_request_id,
        )
        if study_request is None:
            raise AppError(
                404,
                "consultation_study_request_not_found",
                "Consultation study request not found",
            )

        self.consultation_repository.delete_study_request(study_request)
        self.db.commit()

    def list_patient_consultations(
        self, tenant_id: uuid.UUID, patient_id: uuid.UUID
    ) -> tuple[list[Consultation], int]:
        self._get_patient_for_tenant(tenant_id, patient_id)
        return self.consultation_repository.list_by_patient(tenant_id, patient_id)

    def get_patient_clinical_history(
        self, tenant_id: uuid.UUID, patient_id: uuid.UUID
    ) -> tuple[
        Patient,
        list[Consultation],
        list[Exam],
        list[PatientPreventiveCare],
        list[PatientFileReference],
        list[FollowUp],
    ]:
        patient = self._get_patient_for_tenant(tenant_id, patient_id)
        consultations, _ = self.consultation_repository.list_by_patient(
            tenant_id,
            patient_id,
        )
        exams, _ = self.exam_repository.list_by_patient(tenant_id, patient_id)
        preventive_care, _ = self.preventive_care_repository.list_by_patient(
            tenant_id,
            patient_id,
        )
        file_references, _ = self.file_reference_repository.list_by_patient(
            tenant_id,
            patient_id,
        )
        follow_ups, _ = self.follow_up_repository.list_by_patient(tenant_id, patient_id)
        return patient, consultations, exams, preventive_care, file_references, follow_ups

    def _get_patient_for_tenant(
        self, tenant_id: uuid.UUID, patient_id: uuid.UUID
    ) -> Patient:
        patient = self.patient_repository.get_by_id(tenant_id, patient_id)
        if patient is None:
            raise AppError(404, "patient_not_found", "Patient not found")
        return patient

    def _validate_update_numbers(self, updates: dict) -> None:
        non_negative_fields = {
            "current_step",
            "temperature_c",
            "current_weight_kg",
            "heart_rate",
            "respiratory_rate",
        }
        for field in non_negative_fields:
            value = updates.get(field)
            if value is not None and value < 0:
                raise AppError(
                    422,
                    "validation_error",
                    f"{field} cannot be negative",
                )

    def _quantize_money(self, value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

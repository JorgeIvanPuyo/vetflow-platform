import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.appointment import Appointment
from app.models.owner import Owner
from app.models.patient import Patient
from app.models.user import User
from app.repositories.appointment import AppointmentRepository
from app.repositories.owner import OwnerRepository
from app.repositories.patient import PatientRepository
from app.repositories.user import UserRepository
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate


class AppointmentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.appointment_repository = AppointmentRepository(db)
        self.owner_repository = OwnerRepository(db)
        self.patient_repository = PatientRepository(db)
        self.user_repository = UserRepository(db)

    def create_appointment(
        self,
        tenant_id: uuid.UUID,
        payload: AppointmentCreate,
        *,
        created_by_user_id: uuid.UUID | None = None,
    ) -> Appointment:
        self._validate_time_range(payload.start_at, payload.end_at)
        self._validate_optional_patient(tenant_id, payload.patient_id)
        self._validate_optional_owner(tenant_id, payload.owner_id)
        self._validate_optional_user(tenant_id, payload.assigned_user_id)
        self._validate_optional_user(tenant_id, created_by_user_id)

        appointment = Appointment(
            tenant_id=tenant_id,
            created_by_user_id=created_by_user_id,
            **payload.model_dump(),
        )
        self.appointment_repository.create(appointment)
        self.db.commit()
        return self.get_appointment(tenant_id, appointment.id)

    def list_appointments(
        self,
        tenant_id: uuid.UUID,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        assigned_user_id: uuid.UUID | None = None,
        patient_id: uuid.UUID | None = None,
        owner_id: uuid.UUID | None = None,
        status: str | None = None,
        appointment_type: str | None = None,
    ) -> tuple[list[Appointment], int]:
        self._validate_time_range(date_from, date_to, allow_open_ended=True)
        if assigned_user_id is not None:
            self._validate_optional_user(tenant_id, assigned_user_id)
        if patient_id is not None:
            self._validate_optional_patient(tenant_id, patient_id)
        if owner_id is not None:
            self._validate_optional_owner(tenant_id, owner_id)
        return self.appointment_repository.list(
            tenant_id,
            date_from=date_from,
            date_to=date_to,
            assigned_user_id=assigned_user_id,
            patient_id=patient_id,
            owner_id=owner_id,
            status=status,
            appointment_type=appointment_type,
        )

    def get_appointment(
        self,
        tenant_id: uuid.UUID,
        appointment_id: uuid.UUID,
    ) -> Appointment:
        appointment = self.appointment_repository.get_by_id(tenant_id, appointment_id)
        if appointment is None:
            raise AppError(404, "appointment_not_found", "Appointment not found")
        return appointment

    def update_appointment(
        self,
        tenant_id: uuid.UUID,
        appointment_id: uuid.UUID,
        payload: AppointmentUpdate,
    ) -> Appointment:
        appointment = self.get_appointment(tenant_id, appointment_id)
        updates = payload.model_dump(exclude_unset=True)

        for field in ("title", "appointment_type", "status", "start_at", "end_at"):
            if field in updates and updates[field] is None:
                raise AppError(422, "validation_error", f"{field} cannot be null")

        start_at = updates.get("start_at", appointment.start_at)
        end_at = updates.get("end_at", appointment.end_at)
        self._validate_time_range(start_at, end_at)

        if "patient_id" in updates and updates["patient_id"] is not None:
            self._validate_optional_patient(tenant_id, updates["patient_id"])
        if "owner_id" in updates and updates["owner_id"] is not None:
            self._validate_optional_owner(tenant_id, updates["owner_id"])
        if "assigned_user_id" in updates and updates["assigned_user_id"] is not None:
            self._validate_optional_user(tenant_id, updates["assigned_user_id"])

        updated_appointment = self.appointment_repository.update(appointment, updates)
        self.db.commit()
        return self.get_appointment(tenant_id, updated_appointment.id)

    def delete_appointment(self, tenant_id: uuid.UUID, appointment_id: uuid.UUID) -> None:
        appointment = self.get_appointment(tenant_id, appointment_id)
        self.appointment_repository.delete(appointment)
        self.db.commit()

    def _validate_time_range(
        self,
        start_at: datetime | None,
        end_at: datetime | None,
        *,
        allow_open_ended: bool = False,
    ) -> None:
        if allow_open_ended and (start_at is None or end_at is None):
            return
        if (
            start_at is not None
            and end_at is not None
            and self._comparable_datetime(end_at)
            <= self._comparable_datetime(start_at)
        ):
            raise AppError(
                422,
                "invalid_appointment_time",
                "Appointment end_at must be after start_at",
            )

    def _comparable_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    def _validate_optional_patient(
        self,
        tenant_id: uuid.UUID,
        patient_id: uuid.UUID | None,
    ) -> None:
        if patient_id is None:
            return
        patient = self.patient_repository.get_by_id(tenant_id, patient_id)
        if patient is not None:
            return
        patient_any_tenant = self.db.get(Patient, patient_id)
        if patient_any_tenant is not None:
            raise AppError(
                409,
                "invalid_cross_tenant_access",
                "Patient does not belong to the provided tenant",
            )
        raise AppError(404, "patient_not_found", "Patient not found")

    def _validate_optional_owner(
        self,
        tenant_id: uuid.UUID,
        owner_id: uuid.UUID | None,
    ) -> None:
        if owner_id is None:
            return
        owner = self.owner_repository.get_by_id(tenant_id, owner_id)
        if owner is not None:
            return
        owner_any_tenant = self.db.get(Owner, owner_id)
        if owner_any_tenant is not None:
            raise AppError(
                409,
                "invalid_cross_tenant_access",
                "Owner does not belong to the provided tenant",
            )
        raise AppError(404, "owner_not_found", "Owner not found")

    def _validate_optional_user(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> None:
        if user_id is None:
            return
        user = self.user_repository.get_by_id(tenant_id, user_id)
        if user is not None:
            return
        user_any_tenant = self.db.get(User, user_id)
        if user_any_tenant is not None:
            raise AppError(
                409,
                "invalid_cross_tenant_access",
                "User does not belong to the provided tenant",
            )
        raise AppError(404, "user_not_found", "User not found")

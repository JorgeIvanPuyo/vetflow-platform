import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.appointment import Appointment
from app.models.follow_up import FollowUp
from app.models.owner import Owner
from app.models.patient import Patient
from app.models.user import User
from app.repositories.appointment import AppointmentRepository
from app.repositories.follow_up import FollowUpRepository
from app.repositories.owner import OwnerRepository
from app.repositories.patient import PatientRepository
from app.repositories.user import UserRepository
from app.schemas.appointment import AppointmentCreate
from app.schemas.follow_up import FollowUpCancel, FollowUpCreate, FollowUpUpdate
from app.services.appointment import AppointmentService


FOLLOW_UP_TO_APPOINTMENT_TYPE = {
    "consultation_control": "follow_up",
    "vaccine": "vaccine",
    "deworming": "deworming",
    "exam_review": "exam",
    "other": "other",
}


class FollowUpService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.follow_up_repository = FollowUpRepository(db)
        self.appointment_repository = AppointmentRepository(db)
        self.owner_repository = OwnerRepository(db)
        self.patient_repository = PatientRepository(db)
        self.user_repository = UserRepository(db)

    def create_follow_up(
        self,
        tenant_id: uuid.UUID,
        payload: FollowUpCreate,
        *,
        created_by_user_id: uuid.UUID | None = None,
    ) -> FollowUp:
        self._validate_patient(tenant_id, payload.patient_id)
        self._validate_owner(tenant_id, payload.owner_id)
        self._validate_user(tenant_id, payload.assigned_user_id)
        self._validate_user(tenant_id, created_by_user_id)

        follow_up = FollowUp(
            tenant_id=tenant_id,
            patient_id=payload.patient_id,
            owner_id=payload.owner_id,
            assigned_user_id=payload.assigned_user_id,
            created_by_user_id=created_by_user_id,
            source_type=payload.source_type,
            source_id=payload.source_id,
            title=payload.title,
            description=payload.description,
            follow_up_type=payload.follow_up_type,
            status="pending",
            due_at=payload.due_at,
            notes=payload.notes,
        )
        self.follow_up_repository.create(follow_up)

        if payload.create_appointment:
            appointment = AppointmentService(self.db).create_appointment(
                tenant_id,
                AppointmentCreate(
                    patient_id=payload.patient_id,
                    owner_id=payload.owner_id,
                    assigned_user_id=payload.assigned_user_id,
                    title=payload.title,
                    reason=payload.description,
                    appointment_type=FOLLOW_UP_TO_APPOINTMENT_TYPE[payload.follow_up_type],
                    status="scheduled",
                    start_at=payload.due_at,
                    end_at=payload.due_at
                    + timedelta(minutes=payload.appointment_duration_minutes),
                    notes=payload.notes,
                ),
                created_by_user_id=created_by_user_id,
            )
            follow_up = self.follow_up_repository.update(
                follow_up,
                {
                    "appointment_id": appointment.id,
                    "status": "scheduled",
                },
            )
            self.db.commit()
            return self.get_follow_up(tenant_id, follow_up.id)

        self.db.commit()
        return self.get_follow_up(tenant_id, follow_up.id)

    def list_follow_ups(
        self,
        tenant_id: uuid.UUID,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        patient_id: uuid.UUID | None = None,
        owner_id: uuid.UUID | None = None,
        assigned_user_id: uuid.UUID | None = None,
        status: str | None = None,
        follow_up_type: str | None = None,
    ) -> tuple[list[FollowUp], int]:
        self._validate_time_range(date_from, date_to, allow_open_ended=True)
        if patient_id is not None:
            self._validate_patient(tenant_id, patient_id)
        if owner_id is not None:
            self._validate_owner(tenant_id, owner_id)
        if assigned_user_id is not None:
            self._validate_user(tenant_id, assigned_user_id)
        return self.follow_up_repository.list(
            tenant_id,
            date_from=date_from,
            date_to=date_to,
            patient_id=patient_id,
            owner_id=owner_id,
            assigned_user_id=assigned_user_id,
            status=status,
            follow_up_type=follow_up_type,
        )

    def get_follow_up(self, tenant_id: uuid.UUID, follow_up_id: uuid.UUID) -> FollowUp:
        follow_up = self.follow_up_repository.get_by_id(tenant_id, follow_up_id)
        if follow_up is None:
            raise AppError(404, "follow_up_not_found", "Follow-up not found")
        return follow_up

    def update_follow_up(
        self,
        tenant_id: uuid.UUID,
        follow_up_id: uuid.UUID,
        payload: FollowUpUpdate,
    ) -> FollowUp:
        follow_up = self.get_follow_up(tenant_id, follow_up_id)
        updates = payload.model_dump(exclude_unset=True)

        for field in ("title", "follow_up_type", "status", "due_at"):
            if field in updates and updates[field] is None:
                raise AppError(422, "validation_error", f"{field} cannot be null")

        if "assigned_user_id" in updates and updates["assigned_user_id"] is not None:
            self._validate_user(tenant_id, updates["assigned_user_id"])
        if "appointment_id" in updates and updates["appointment_id"] is not None:
            self._validate_appointment(tenant_id, updates["appointment_id"])

        self._apply_status_timestamps(updates, follow_up)

        updated_follow_up = self.follow_up_repository.update(follow_up, updates)
        self.db.commit()
        return self.get_follow_up(tenant_id, updated_follow_up.id)

    def complete_follow_up(
        self,
        tenant_id: uuid.UUID,
        follow_up_id: uuid.UUID,
    ) -> FollowUp:
        follow_up = self.get_follow_up(tenant_id, follow_up_id)
        self.follow_up_repository.update(
            follow_up,
            {
                "status": "completed",
                "completed_at": datetime.now(UTC),
                "cancelled_at": None,
            },
        )
        self.db.commit()
        return self.get_follow_up(tenant_id, follow_up_id)

    def cancel_follow_up(
        self,
        tenant_id: uuid.UUID,
        follow_up_id: uuid.UUID,
        payload: FollowUpCancel,
    ) -> FollowUp:
        follow_up = self.get_follow_up(tenant_id, follow_up_id)
        notes = follow_up.notes
        if payload.notes:
            notes = f"{notes}\n\n{payload.notes}" if notes else payload.notes

        self.follow_up_repository.update(
            follow_up,
            {
                "status": "cancelled",
                "cancelled_at": datetime.now(UTC),
                "completed_at": None,
                "notes": notes,
            },
        )
        self.db.commit()
        return self.get_follow_up(tenant_id, follow_up_id)

    def delete_follow_up(self, tenant_id: uuid.UUID, follow_up_id: uuid.UUID) -> None:
        follow_up = self.get_follow_up(tenant_id, follow_up_id)
        self.follow_up_repository.delete(follow_up)
        self.db.commit()

    def _apply_status_timestamps(self, updates: dict, follow_up: FollowUp) -> None:
        if "status" not in updates:
            return

        status = updates["status"]
        if status == "completed":
            updates["completed_at"] = follow_up.completed_at or datetime.now(UTC)
            updates["cancelled_at"] = None
        elif status == "cancelled":
            updates["cancelled_at"] = follow_up.cancelled_at or datetime.now(UTC)
            updates["completed_at"] = None
        elif status in {"pending", "scheduled", "overdue"}:
            updates["completed_at"] = None
            updates["cancelled_at"] = None

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
            and self._comparable_datetime(end_at) < self._comparable_datetime(start_at)
        ):
            raise AppError(
                422,
                "invalid_follow_up_date_range",
                "Follow-up date_to must be after or equal to date_from",
            )

    def _comparable_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    def _validate_patient(self, tenant_id: uuid.UUID, patient_id: uuid.UUID) -> None:
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

    def _validate_owner(self, tenant_id: uuid.UUID, owner_id: uuid.UUID | None) -> None:
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

    def _validate_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID | None) -> None:
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

    def _validate_appointment(
        self,
        tenant_id: uuid.UUID,
        appointment_id: uuid.UUID,
    ) -> None:
        appointment = self.appointment_repository.get_by_id(tenant_id, appointment_id)
        if appointment is not None:
            return
        appointment_any_tenant = self.db.get(Appointment, appointment_id)
        if appointment_any_tenant is not None:
            raise AppError(
                409,
                "invalid_cross_tenant_access",
                "Appointment does not belong to the provided tenant",
            )
        raise AppError(404, "appointment_not_found", "Appointment not found")

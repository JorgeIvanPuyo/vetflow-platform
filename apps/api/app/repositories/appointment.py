import uuid
from datetime import datetime, timezone

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.appointment import Appointment


class AppointmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, appointment: Appointment) -> Appointment:
        self.db.add(appointment)
        self.db.flush()
        self.db.refresh(appointment)
        return appointment

    def get_by_id(
        self,
        tenant_id: uuid.UUID,
        appointment_id: uuid.UUID,
    ) -> Appointment | None:
        statement = (
            select(Appointment)
            .where(
                Appointment.id == appointment_id,
                Appointment.tenant_id == tenant_id,
            )
            .options(
                selectinload(Appointment.patient),
                selectinload(Appointment.owner),
                selectinload(Appointment.assigned_user),
                selectinload(Appointment.created_by_user),
            )
        )
        return self.db.scalar(statement)

    def list(
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
        if date_from is None and date_to is None:
            date_from = datetime.now(timezone.utc)

        statement: Select[tuple[Appointment]] = (
            select(Appointment)
            .where(Appointment.tenant_id == tenant_id)
            .options(
                selectinload(Appointment.patient),
                selectinload(Appointment.owner),
                selectinload(Appointment.assigned_user),
                selectinload(Appointment.created_by_user),
            )
        )
        count_statement = select(func.count()).select_from(Appointment).where(
            Appointment.tenant_id == tenant_id
        )

        statement = self._apply_filters(
            statement,
            date_from=date_from,
            date_to=date_to,
            assigned_user_id=assigned_user_id,
            patient_id=patient_id,
            owner_id=owner_id,
            status=status,
            appointment_type=appointment_type,
        )
        count_statement = self._apply_filters(
            count_statement,
            date_from=date_from,
            date_to=date_to,
            assigned_user_id=assigned_user_id,
            patient_id=patient_id,
            owner_id=owner_id,
            status=status,
            appointment_type=appointment_type,
        )

        appointments = list(
            self.db.scalars(statement.order_by(Appointment.start_at.asc())).all()
        )
        total = self.db.scalar(count_statement) or 0
        return appointments, total

    def update(self, appointment: Appointment, updates: dict) -> Appointment:
        for field, value in updates.items():
            setattr(appointment, field, value)

        self.db.add(appointment)
        self.db.flush()
        self.db.refresh(appointment)
        return appointment

    def delete(self, appointment: Appointment) -> None:
        self.db.delete(appointment)
        self.db.flush()

    def _apply_filters(
        self,
        statement,
        *,
        date_from: datetime | None,
        date_to: datetime | None,
        assigned_user_id: uuid.UUID | None,
        patient_id: uuid.UUID | None,
        owner_id: uuid.UUID | None,
        status: str | None,
        appointment_type: str | None,
    ):
        if date_from is not None:
            statement = statement.where(Appointment.start_at >= date_from)
        if date_to is not None:
            statement = statement.where(Appointment.start_at <= date_to)
        if assigned_user_id is not None:
            statement = statement.where(Appointment.assigned_user_id == assigned_user_id)
        if patient_id is not None:
            statement = statement.where(Appointment.patient_id == patient_id)
        if owner_id is not None:
            statement = statement.where(Appointment.owner_id == owner_id)
        if status is not None:
            statement = statement.where(Appointment.status == status)
        if appointment_type is not None:
            statement = statement.where(Appointment.appointment_type == appointment_type)
        return statement

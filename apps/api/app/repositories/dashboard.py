from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.appointment import Appointment
from app.models.consultation import Consultation
from app.models.follow_up import FollowUp
from app.models.patient_file_reference import PatientFileReference
from app.models.patient_preventive_care import PatientPreventiveCare


class DashboardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_appointments(
        self,
        tenant_id: uuid.UUID,
        *,
        range_start: datetime,
        range_end: datetime,
        assigned_user_id: uuid.UUID | None = None,
        include_completed: bool = False,
    ) -> list[Appointment]:
        statement = (
            select(Appointment)
            .where(
                Appointment.tenant_id == tenant_id,
                Appointment.start_at >= range_start,
                Appointment.start_at <= range_end,
            )
            .options(
                selectinload(Appointment.patient),
                selectinload(Appointment.owner),
                selectinload(Appointment.assigned_user),
            )
            .order_by(Appointment.start_at.asc())
        )
        if assigned_user_id is not None:
            statement = statement.where(Appointment.assigned_user_id == assigned_user_id)
        if not include_completed:
            statement = statement.where(Appointment.status == "scheduled")
        return list(self.db.scalars(statement).all())

    def list_follow_ups(
        self,
        tenant_id: uuid.UUID,
        *,
        range_start: datetime | None = None,
        range_end: datetime | None = None,
        before: datetime | None = None,
        assigned_user_id: uuid.UUID | None = None,
        statuses: tuple[str, ...] = ("pending", "scheduled"),
    ) -> list[FollowUp]:
        statement = (
            select(FollowUp)
            .where(
                FollowUp.tenant_id == tenant_id,
                FollowUp.status.in_(statuses),
            )
            .options(
                selectinload(FollowUp.patient),
                selectinload(FollowUp.owner),
                selectinload(FollowUp.assigned_user),
            )
            .order_by(FollowUp.due_at.asc())
        )
        if range_start is not None:
            statement = statement.where(FollowUp.due_at >= range_start)
        if range_end is not None:
            statement = statement.where(FollowUp.due_at <= range_end)
        if before is not None:
            statement = statement.where(FollowUp.due_at < before)
        if assigned_user_id is not None:
            statement = statement.where(FollowUp.assigned_user_id == assigned_user_id)
        return list(self.db.scalars(statement).all())

    def list_consultations(
        self,
        tenant_id: uuid.UUID,
        *,
        range_start: datetime,
        range_end: datetime,
        assigned_user_id: uuid.UUID | None = None,
    ) -> list[Consultation]:
        statement = (
            select(Consultation)
            .where(
                Consultation.tenant_id == tenant_id,
                Consultation.visit_date >= range_start,
                Consultation.visit_date <= range_end,
            )
            .options(
                selectinload(Consultation.patient),
                selectinload(Consultation.attending_user),
                selectinload(Consultation.created_by_user),
            )
            .order_by(Consultation.visit_date.desc())
        )
        if assigned_user_id is not None:
            statement = statement.where(
                or_(
                    Consultation.attending_user_id == assigned_user_id,
                    Consultation.created_by_user_id == assigned_user_id,
                )
            )
        return list(self.db.scalars(statement).all())

    def list_upcoming_preventive_care(
        self,
        tenant_id: uuid.UUID,
        *,
        range_start: datetime,
        range_end: datetime,
    ) -> list[PatientPreventiveCare]:
        statement = (
            select(PatientPreventiveCare)
            .where(
                PatientPreventiveCare.tenant_id == tenant_id,
                PatientPreventiveCare.next_due_at.is_not(None),
                PatientPreventiveCare.next_due_at >= range_start,
                PatientPreventiveCare.next_due_at <= range_end,
            )
            .options(
                selectinload(PatientPreventiveCare.patient),
                selectinload(PatientPreventiveCare.created_by_user),
            )
            .order_by(PatientPreventiveCare.next_due_at.asc())
        )
        return list(self.db.scalars(statement).all())

    def list_recent_files(
        self,
        tenant_id: uuid.UUID,
        *,
        range_start: datetime,
        range_end: datetime,
    ) -> list[PatientFileReference]:
        event_timestamp = func.coalesce(
            PatientFileReference.uploaded_at,
            PatientFileReference.created_at,
        )
        statement = (
            select(PatientFileReference)
            .where(
                PatientFileReference.tenant_id == tenant_id,
                event_timestamp >= range_start,
                event_timestamp <= range_end,
            )
            .options(
                selectinload(PatientFileReference.patient),
                selectinload(PatientFileReference.created_by_user),
            )
            .order_by(event_timestamp.desc())
        )
        return list(self.db.scalars(statement).all())

    def count_appointments_for_user(
        self,
        tenant_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        range_start: datetime,
        range_end: datetime,
        include_completed: bool = False,
    ) -> int:
        statement = select(func.count()).select_from(Appointment).where(
            Appointment.tenant_id == tenant_id,
            Appointment.assigned_user_id == user_id,
            Appointment.start_at >= range_start,
            Appointment.start_at <= range_end,
        )
        if not include_completed:
            statement = statement.where(Appointment.status == "scheduled")
        return int(self.db.scalar(statement) or 0)

    def count_consultations_for_user(
        self,
        tenant_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        range_start: datetime,
        range_end: datetime,
    ) -> int:
        statement = select(func.count()).select_from(Consultation).where(
            Consultation.tenant_id == tenant_id,
            Consultation.visit_date >= range_start,
            Consultation.visit_date <= range_end,
            or_(
                Consultation.attending_user_id == user_id,
                Consultation.created_by_user_id == user_id,
            ),
        )
        return int(self.db.scalar(statement) or 0)

    def count_follow_ups_for_user(
        self,
        tenant_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        statuses: tuple[str, ...] = ("pending", "scheduled", "overdue"),
    ) -> int:
        statement = select(func.count()).select_from(FollowUp).where(
            FollowUp.tenant_id == tenant_id,
            FollowUp.assigned_user_id == user_id,
            FollowUp.status.in_(statuses),
        )
        return int(self.db.scalar(statement) or 0)

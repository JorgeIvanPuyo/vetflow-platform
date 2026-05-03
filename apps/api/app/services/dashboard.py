from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.user import User
from app.repositories.dashboard import DashboardRepository
from app.repositories.user import UserRepository
from app.schemas.dashboard import DashboardSummaryRead


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DashboardTimeWindows:
    requested_start: datetime
    requested_end: datetime
    appointments_start: datetime
    appointments_end: datetime
    follow_ups_start: datetime
    follow_ups_end: datetime
    overdue_before: datetime
    consultations_start: datetime
    consultations_end: datetime
    preventive_care_start: datetime
    preventive_care_end: datetime
    files_start: datetime
    files_end: datetime


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.dashboard_repository = DashboardRepository(db)
        self.user_repository = UserRepository(db)

    def get_summary(
        self,
        tenant_id: uuid.UUID,
        *,
        date_from_raw: str | None = None,
        date_to_raw: str | None = None,
        assigned_user_id: uuid.UUID | None = None,
        include_completed: bool = False,
    ) -> DashboardSummaryRead:
        self._validate_user_scope(tenant_id, assigned_user_id)
        windows = self._build_time_windows(date_from_raw, date_to_raw)

        try:
            appointments = self.dashboard_repository.list_appointments(
                tenant_id,
                range_start=windows.appointments_start,
                range_end=windows.appointments_end,
                assigned_user_id=assigned_user_id,
                include_completed=include_completed,
            )
            upcoming_follow_ups = self.dashboard_repository.list_follow_ups(
                tenant_id,
                range_start=windows.follow_ups_start,
                range_end=windows.follow_ups_end,
                assigned_user_id=assigned_user_id,
                statuses=("pending", "scheduled"),
            )
            overdue_follow_ups = self.dashboard_repository.list_follow_ups(
                tenant_id,
                before=windows.overdue_before,
                assigned_user_id=assigned_user_id,
                statuses=("pending", "scheduled"),
            )
            recent_consultations = self.dashboard_repository.list_consultations(
                tenant_id,
                range_start=windows.consultations_start,
                range_end=windows.consultations_end,
                assigned_user_id=assigned_user_id,
            )
            upcoming_preventive_care = self.dashboard_repository.list_upcoming_preventive_care(
                tenant_id,
                range_start=windows.preventive_care_start,
                range_end=windows.preventive_care_end,
            )
            recent_files = self.dashboard_repository.list_recent_files(
                tenant_id,
                range_start=windows.files_start,
                range_end=windows.files_end,
            )
            activity_by_veterinarian = self._build_activity_by_veterinarian(
                tenant_id,
                windows=windows,
                assigned_user_id=assigned_user_id,
                include_completed=include_completed,
            )

            return DashboardSummaryRead(
                period={
                    "date_from": windows.requested_start,
                    "date_to": windows.requested_end,
                },
                cards={
                    "appointments_today": len(appointments),
                    "follow_ups_upcoming": len(upcoming_follow_ups),
                    "follow_ups_overdue": len(overdue_follow_ups),
                    "consultations_recent": len(recent_consultations),
                    "preventive_care_upcoming": len(upcoming_preventive_care),
                    "files_recent": len(recent_files),
                },
                appointments_today=[
                    {
                        "id": appointment.id,
                        "title": appointment.title,
                        "appointment_type": appointment.appointment_type,
                        "status": appointment.status,
                        "start_at": appointment.start_at,
                        "end_at": appointment.end_at,
                        "patient_name": appointment.patient_name,
                        "owner_name": appointment.owner_name,
                        "assigned_user_name": appointment.assigned_user_name,
                    }
                    for appointment in appointments
                ],
                upcoming_follow_ups=[
                    {
                        "id": follow_up.id,
                        "title": follow_up.title,
                        "follow_up_type": follow_up.follow_up_type,
                        "status": follow_up.status,
                        "due_at": follow_up.due_at,
                        "patient_name": follow_up.patient_name,
                        "owner_name": follow_up.owner_name,
                        "assigned_user_name": follow_up.assigned_user_name,
                    }
                    for follow_up in upcoming_follow_ups
                ],
                overdue_follow_ups=[
                    {
                        "id": follow_up.id,
                        "title": follow_up.title,
                        "follow_up_type": follow_up.follow_up_type,
                        "status": follow_up.status,
                        "due_at": follow_up.due_at,
                        "patient_name": follow_up.patient_name,
                        "owner_name": follow_up.owner_name,
                        "assigned_user_name": follow_up.assigned_user_name,
                    }
                    for follow_up in overdue_follow_ups
                ],
                recent_consultations=[
                    {
                        "id": consultation.id,
                        "patient_id": consultation.patient_id,
                        "patient_name": consultation.patient.name,
                        "reason": consultation.reason,
                        "status": consultation.status,
                        "visit_date": consultation.visit_date,
                        "attending_user_name": consultation.attending_user_name,
                        "created_by_user_name": consultation.created_by_user_name,
                    }
                    for consultation in recent_consultations
                ],
                upcoming_preventive_care=[
                    {
                        "id": record.id,
                        "patient_id": record.patient_id,
                        "patient_name": record.patient.name,
                        "name": record.name,
                        "care_type": record.care_type,
                        "next_due_at": record.next_due_at,
                        "created_by_user_name": record.created_by_user_name,
                    }
                    for record in upcoming_preventive_care
                    if record.next_due_at is not None
                ],
                recent_files=[
                    {
                        "id": file_reference.id,
                        "patient_id": file_reference.patient_id,
                        "patient_name": file_reference.patient.name,
                        "name": file_reference.name,
                        "file_type": file_reference.file_type,
                        "uploaded_at": file_reference.uploaded_at
                        or file_reference.created_at,
                        "created_by_user_name": file_reference.created_by_user_name,
                    }
                    for file_reference in recent_files
                ],
                activity_by_veterinarian=activity_by_veterinarian,
            )
        except AppError:
            raise
        except Exception as exc:
            logger.exception(
                "Dashboard summary generation failed. tenant_id=%s assigned_user_id=%s",
                tenant_id,
                assigned_user_id,
            )
            raise AppError(
                500,
                "dashboard_summary_failed",
                "Dashboard summary generation failed",
            ) from exc

    def _build_activity_by_veterinarian(
        self,
        tenant_id: uuid.UUID,
        *,
        windows: DashboardTimeWindows,
        assigned_user_id: uuid.UUID | None,
        include_completed: bool,
    ) -> list[dict]:
        users = self.user_repository.list_active_by_tenant(tenant_id)
        if assigned_user_id is not None:
            users = [user for user in users if user.id == assigned_user_id]

        return [
            {
                "user_id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "appointments_today_count": self.dashboard_repository.count_appointments_for_user(
                    tenant_id,
                    user_id=user.id,
                    range_start=windows.appointments_start,
                    range_end=windows.appointments_end,
                    include_completed=include_completed,
                ),
                "consultations_recent_count": self.dashboard_repository.count_consultations_for_user(
                    tenant_id,
                    user_id=user.id,
                    range_start=windows.consultations_start,
                    range_end=windows.consultations_end,
                ),
                "follow_ups_pending_count": self.dashboard_repository.count_follow_ups_for_user(
                    tenant_id,
                    user_id=user.id,
                ),
            }
            for user in users
        ]

    def _validate_user_scope(
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

    def _build_time_windows(
        self,
        date_from_raw: str | None,
        date_to_raw: str | None,
    ) -> DashboardTimeWindows:
        now = datetime.now(UTC)
        today_start = datetime.combine(now.date(), time.min, tzinfo=UTC)
        today_end = datetime.combine(now.date(), time.max, tzinfo=UTC)

        if date_from_raw is None and date_to_raw is None:
            return DashboardTimeWindows(
            requested_start=today_start,
            requested_end=today_end,
            appointments_start=now,
            appointments_end=now + timedelta(days=1),
            follow_ups_start=now,
            follow_ups_end=now + timedelta(days=7),
            overdue_before=now,
            consultations_start=now - timedelta(days=7),
            consultations_end=now,
            preventive_care_start=now,
            preventive_care_end=now + timedelta(days=30),
            files_start=now - timedelta(days=7),
            files_end=now,
        )

        requested_start = self._parse_datetime_boundary(date_from_raw, is_end=False) or today_start
        requested_end = self._parse_datetime_boundary(date_to_raw, is_end=True) or today_end
        if requested_end < requested_start:
            raise AppError(
                422,
                "invalid_date_range",
                "date_to must be greater than or equal to date_from",
            )

        return DashboardTimeWindows(
            requested_start=requested_start,
            requested_end=requested_end,
            appointments_start=requested_start,
            appointments_end=requested_end,
            follow_ups_start=requested_start,
            follow_ups_end=requested_end,
            overdue_before=now,
            consultations_start=requested_start,
            consultations_end=requested_end,
            preventive_care_start=requested_start,
            preventive_care_end=requested_end,
            files_start=requested_start,
            files_end=requested_end,
        )

    def _parse_datetime_boundary(
        self,
        value: str | None,
        *,
        is_end: bool,
    ) -> datetime | None:
        if value is None:
            return None

        raw = value.strip()
        if not raw:
            return None

        try:
            if len(raw) <= 10:
                parsed_date = date.fromisoformat(raw)
                boundary_time = time.max if is_end else time.min
                return datetime.combine(parsed_date, boundary_time, tzinfo=UTC)

            normalized = raw.replace("Z", "+00:00")
            parsed_datetime = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise AppError(
                422,
                "invalid_date_range",
                "Invalid date range",
            ) from exc

        if parsed_datetime.tzinfo is None:
            return parsed_datetime.replace(tzinfo=UTC)
        return parsed_datetime.astimezone(UTC)

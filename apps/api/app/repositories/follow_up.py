from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.follow_up import FollowUp


class FollowUpRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, follow_up: FollowUp) -> FollowUp:
        self.db.add(follow_up)
        self.db.flush()
        self.db.refresh(follow_up)
        return follow_up

    def get_by_id(self, tenant_id: uuid.UUID, follow_up_id: uuid.UUID) -> FollowUp | None:
        statement = (
            select(FollowUp)
            .where(
                FollowUp.id == follow_up_id,
                FollowUp.tenant_id == tenant_id,
            )
            .options(
                selectinload(FollowUp.patient),
                selectinload(FollowUp.owner),
                selectinload(FollowUp.assigned_user),
                selectinload(FollowUp.created_by_user),
                selectinload(FollowUp.appointment),
            )
        )
        return self.db.scalar(statement)

    def list(
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
        statement: Select[tuple[FollowUp]] = (
            select(FollowUp)
            .where(FollowUp.tenant_id == tenant_id)
            .options(
                selectinload(FollowUp.patient),
                selectinload(FollowUp.owner),
                selectinload(FollowUp.assigned_user),
                selectinload(FollowUp.created_by_user),
                selectinload(FollowUp.appointment),
            )
        )
        count_statement = select(func.count()).select_from(FollowUp).where(
            FollowUp.tenant_id == tenant_id
        )

        statement = self._apply_filters(
            statement,
            date_from=date_from,
            date_to=date_to,
            patient_id=patient_id,
            owner_id=owner_id,
            assigned_user_id=assigned_user_id,
            status=status,
            follow_up_type=follow_up_type,
        )
        count_statement = self._apply_filters(
            count_statement,
            date_from=date_from,
            date_to=date_to,
            patient_id=patient_id,
            owner_id=owner_id,
            assigned_user_id=assigned_user_id,
            status=status,
            follow_up_type=follow_up_type,
        )

        if date_from is None and date_to is None and status is None:
            statement = statement.where(FollowUp.status.in_(("pending", "scheduled", "overdue")))
            count_statement = count_statement.where(
                FollowUp.status.in_(("pending", "scheduled", "overdue"))
            )

        follow_ups = list(self.db.scalars(statement.order_by(FollowUp.due_at.asc())).all())
        total = self.db.scalar(count_statement) or 0
        return follow_ups, total

    def list_by_patient(
        self,
        tenant_id: uuid.UUID,
        patient_id: uuid.UUID,
    ) -> tuple[list[FollowUp], int]:
        statement = (
            select(FollowUp)
            .where(
                FollowUp.tenant_id == tenant_id,
                FollowUp.patient_id == patient_id,
            )
            .options(
                selectinload(FollowUp.patient),
                selectinload(FollowUp.owner),
                selectinload(FollowUp.assigned_user),
                selectinload(FollowUp.created_by_user),
                selectinload(FollowUp.appointment),
            )
            .order_by(FollowUp.due_at.desc())
        )
        count_statement = select(func.count()).select_from(FollowUp).where(
            FollowUp.tenant_id == tenant_id,
            FollowUp.patient_id == patient_id,
        )
        follow_ups = list(self.db.scalars(statement).all())
        total = self.db.scalar(count_statement) or 0
        return follow_ups, total

    def update(self, follow_up: FollowUp, updates: dict) -> FollowUp:
        for field, value in updates.items():
            setattr(follow_up, field, value)

        self.db.add(follow_up)
        self.db.flush()
        self.db.refresh(follow_up)
        return follow_up

    def delete(self, follow_up: FollowUp) -> None:
        self.db.delete(follow_up)
        self.db.flush()

    def _apply_filters(
        self,
        statement,
        *,
        date_from: datetime | None,
        date_to: datetime | None,
        patient_id: uuid.UUID | None,
        owner_id: uuid.UUID | None,
        assigned_user_id: uuid.UUID | None,
        status: str | None,
        follow_up_type: str | None,
    ):
        if date_from is not None:
            statement = statement.where(FollowUp.due_at >= date_from)
        if date_to is not None:
            statement = statement.where(FollowUp.due_at <= date_to)
        if patient_id is not None:
            statement = statement.where(FollowUp.patient_id == patient_id)
        if owner_id is not None:
            statement = statement.where(FollowUp.owner_id == owner_id)
        if assigned_user_id is not None:
            statement = statement.where(FollowUp.assigned_user_id == assigned_user_id)
        if status is not None:
            statement = statement.where(FollowUp.status == status)
        if follow_up_type is not None:
            statement = statement.where(FollowUp.follow_up_type == follow_up_type)
        return statement

import uuid
from datetime import date
from decimal import Decimal
from math import ceil

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.sale import calculate_payment_status
from app.repositories.clinic import ClinicRepository
from app.repositories.receivables import ReceivablesRepository
from app.schemas.receivables import OwnerReceivablesActivityRead, OwnerReceivablesRead
from app.services.owner import OwnerService


class OwnerReceivablesService:
    def __init__(self, db: Session) -> None:
        self.owners = OwnerService(db)
        self.clinic = ClinicRepository(db)
        self.repository = ReceivablesRepository(db)

    def get(self, tenant_id: uuid.UUID, owner_id: uuid.UUID, *, page: int, page_size: int,
            date_from: date | None = None, date_to: date | None = None, patient_id: uuid.UUID | None = None) -> tuple[OwnerReceivablesRead, dict]:
        # Validate Owner first, including archived owners. An unknown/foreign ID
        # must never receive a summary, even when tracking is not configured.
        self.owners.get_owner(tenant_id, owner_id)
        if date_from and date_to and date_from > date_to:
            raise AppError(422, "validation_error", "date_from must be before date_to")
        preferences = self.clinic.get_preferences(tenant_id)
        cutoff = preferences.receivables_tracking_started_at if preferences else None
        total, count, sales, filtered_count = Decimal("0.00"), 0, [], 0
        if cutoff is not None:
            total, count, sales, filtered_count = self.repository.get(tenant_id, owner_id, page=page, page_size=page_size,
                date_from=date_from, date_to=date_to, patient_id=patient_id)
            for sale in sales:
                sale["payment_status"] = calculate_payment_status("confirmed", sale["total_ars"], sale["paid_total_ars"])
        data = OwnerReceivablesRead(
            owner_id=owner_id, tracking_configured=cutoff is not None,
            tracking_started_at=cutoff, currency=preferences.currency_code if preferences else None,
            locale=preferences.locale if preferences else None,
            total_outstanding_ars=total, open_sales_count=count, sales=sales,
        )
        return data, self._meta(page, page_size, filtered_count)

    def activity(self, tenant_id: uuid.UUID, owner_id: uuid.UUID, *, page: int, page_size: int) -> tuple[OwnerReceivablesActivityRead, dict]:
        self.owners.get_owner(tenant_id, owner_id)
        preferences = self.clinic.get_preferences(tenant_id)
        cutoff = preferences.receivables_tracking_started_at if preferences else None
        events, count = [], 0
        if cutoff is not None:
            events, count = self.repository.activity(tenant_id, owner_id, page=page, page_size=page_size)
            for event in events:
                event["event_id"] = f"{event['type']}:{event.pop('source_id')}"
        data = OwnerReceivablesActivityRead(owner_id=owner_id, tracking_configured=cutoff is not None,
            tracking_started_at=cutoff, currency=preferences.currency_code if preferences else None,
            locale=preferences.locale if preferences else None, events=events)
        return data, self._meta(page, page_size, count)

    @staticmethod
    def _meta(page: int, page_size: int, count: int) -> dict:
        return {"page": page, "page_size": page_size, "total": count, "total_pages": ceil(count / page_size) if count else 0}

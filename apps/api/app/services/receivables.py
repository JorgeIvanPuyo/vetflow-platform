import uuid
from decimal import Decimal
from math import ceil

from sqlalchemy.orm import Session

from app.models.sale import calculate_payment_status
from app.repositories.clinic import ClinicRepository
from app.repositories.receivables import ReceivablesRepository
from app.schemas.receivables import OwnerReceivablesRead
from app.services.owner import OwnerService


class OwnerReceivablesService:
    def __init__(self, db: Session) -> None:
        self.owners = OwnerService(db)
        self.clinic = ClinicRepository(db)
        self.repository = ReceivablesRepository(db)

    def get(self, tenant_id: uuid.UUID, owner_id: uuid.UUID, *, page: int, page_size: int) -> tuple[OwnerReceivablesRead, dict]:
        # Validate Owner first, including archived owners. An unknown/foreign ID
        # must never receive a summary, even when tracking is not configured.
        self.owners.get_owner(tenant_id, owner_id)
        preferences = self.clinic.get_preferences(tenant_id)
        cutoff = preferences.receivables_tracking_started_at if preferences else None
        total, count, sales = Decimal("0.00"), 0, []
        if cutoff is not None:
            total, count, sales = self.repository.get(tenant_id, owner_id, page=page, page_size=page_size)
            for sale in sales:
                sale["payment_status"] = calculate_payment_status("confirmed", sale["total_ars"], sale["paid_total_ars"])
        data = OwnerReceivablesRead(
            owner_id=owner_id, tracking_configured=cutoff is not None,
            tracking_started_at=cutoff, currency=preferences.currency_code if preferences else None,
            locale=preferences.locale if preferences else None,
            total_outstanding_ars=total, open_sales_count=count, sales=sales,
        )
        return data, {"page": page, "page_size": page_size, "total": count, "total_pages": ceil(count / page_size) if count else 0}

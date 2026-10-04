import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.services.payment_report import PaymentReportService

router = APIRouter(prefix="/reports", tags=["payment-reports"])


@router.get("/payments")
def payment_report(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    payment_method_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    report, meta = PaymentReportService(db).read(tenant.tenant_id, date_from=date_from, date_to=date_to,
        payment_method_id=payment_method_id, page=page, page_size=page_size)
    return {"data": report.model_dump(mode="json"), "meta": meta}

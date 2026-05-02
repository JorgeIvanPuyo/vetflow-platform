import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.services.dashboard import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_dashboard_summary(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    assigned_user_id: uuid.UUID | None = Query(default=None),
    include_completed: bool = Query(default=False),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    summary = DashboardService(db).get_summary(
        tenant.tenant_id,
        date_from_raw=date_from,
        date_to_raw=date_to,
        assigned_user_id=assigned_user_id,
        include_completed=include_completed,
    )
    return {
        "data": summary.model_dump(mode="json"),
        "meta": {},
    }

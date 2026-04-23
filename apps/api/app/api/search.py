from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.search import SearchMeta
from app.services.search import SearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def search(
    q: str = Query(...),
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    results, trimmed_query = SearchService(db).search(tenant.tenant_id, q)
    return {
        "data": [result.model_dump(mode="json") for result in results],
        "meta": SearchMeta(query=trimmed_query).model_dump(),
    }

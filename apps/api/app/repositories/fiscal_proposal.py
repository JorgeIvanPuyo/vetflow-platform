import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.fiscal_proposal import FiscalPaymentAllocation, FiscalProposal


class FiscalProposalRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, sale_id: uuid.UUID, proposal_id: uuid.UUID, *, lock=False):
        query = select(FiscalProposal).where(FiscalProposal.tenant_id == tenant_id, FiscalProposal.sale_id == sale_id, FiscalProposal.id == proposal_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return self.db.scalar(query)

    def list(self, tenant_id, sale_id):
        return list(self.db.scalars(select(FiscalProposal).where(FiscalProposal.tenant_id == tenant_id, FiscalProposal.sale_id == sale_id).order_by(FiscalProposal.created_at, FiscalProposal.id)))

    def by_key(self, tenant_id, key):
        return self.db.scalar(select(FiscalProposal).where(FiscalProposal.tenant_id == tenant_id, FiscalProposal.idempotency_key == key))

    def allocations(self, tenant_id, sale_id, *, active_only=False):
        query = select(FiscalPaymentAllocation).where(FiscalPaymentAllocation.tenant_id == tenant_id, FiscalPaymentAllocation.sale_id == sale_id)
        if active_only:
            query = query.where(FiscalPaymentAllocation.is_active.is_(True))
        return list(self.db.scalars(query.order_by(FiscalPaymentAllocation.id)))

    def add(self, proposal):
        self.db.add(proposal)
        self.db.flush()
        return proposal

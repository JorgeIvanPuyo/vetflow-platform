from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.arca_emission import ArcaDocumentFile, ArcaEmissionAttempt, ArcaEmissionIntent, ArcaSeriesOwnership
from app.models.fiscal_configuration import FiscalPolicy, FiscalSeries
from app.models.fiscal_proposal import FiscalPaymentAllocation, FiscalProposal
from app.models.payment import SalePayment
from app.models.sale import Sale
from app.models.sale_fiscal import FiscalIssuer, SaleFiscalDocument


def _locked(query, lock):
    return query.with_for_update().execution_options(populate_existing=True) if lock else query


class ArcaEmissionRepository:
    def __init__(self, db: Session):
        self.db = db

    def sale(self, tenant_id, sale_id, *, lock=False):
        return self.db.scalar(_locked(select(Sale).where(Sale.tenant_id == tenant_id, Sale.id == sale_id), lock))

    def proposal(self, tenant_id, sale_id, proposal_id, *, lock=False):
        return self.db.scalar(_locked(select(FiscalProposal).where(FiscalProposal.tenant_id == tenant_id, FiscalProposal.sale_id == sale_id, FiscalProposal.id == proposal_id), lock))

    def series(self, tenant_id, series_id, *, lock=False):
        return self.db.scalar(_locked(select(FiscalSeries).where(FiscalSeries.tenant_id == tenant_id, FiscalSeries.id == series_id), lock))

    def issuer(self, tenant_id, issuer_id, *, lock=False):
        return self.db.scalar(_locked(select(FiscalIssuer).where(FiscalIssuer.tenant_id == tenant_id, FiscalIssuer.id == issuer_id), lock))

    def policy(self, tenant_id, *, lock=False):
        return self.db.scalar(_locked(select(FiscalPolicy).where(FiscalPolicy.tenant_id == tenant_id), lock))

    def intent(self, tenant_id, sale_id, intent_id, *, lock=False):
        return self.db.scalar(_locked(select(ArcaEmissionIntent).where(ArcaEmissionIntent.tenant_id == tenant_id, ArcaEmissionIntent.sale_id == sale_id, ArcaEmissionIntent.id == intent_id), lock))

    def by_key(self, tenant_id, key):
        return self.db.scalar(select(ArcaEmissionIntent).where(ArcaEmissionIntent.tenant_id == tenant_id, ArcaEmissionIntent.idempotency_key == key))

    def current_for_proposal(self, tenant_id, proposal_id, *, lock=False):
        return self.db.scalar(_locked(select(ArcaEmissionIntent).where(ArcaEmissionIntent.tenant_id == tenant_id, ArcaEmissionIntent.proposal_id == proposal_id, ArcaEmissionIntent.is_current.is_(True)), lock))

    def intents(self, tenant_id, sale_id=None, *, pending_only=False):
        query = select(ArcaEmissionIntent).where(ArcaEmissionIntent.tenant_id == tenant_id)
        if sale_id is not None:
            query = query.where(ArcaEmissionIntent.sale_id == sale_id)
        if pending_only:
            query = query.where(ArcaEmissionIntent.state.in_(["processing", "unknown", "conflict"]))
        return list(self.db.scalars(query.order_by(ArcaEmissionIntent.created_at, ArcaEmissionIntent.id)))

    def allocations(self, tenant_id, sale_id, proposal_id, *, lock=False):
        query = select(FiscalPaymentAllocation).where(FiscalPaymentAllocation.tenant_id == tenant_id, FiscalPaymentAllocation.sale_id == sale_id, FiscalPaymentAllocation.proposal_id == proposal_id, FiscalPaymentAllocation.is_active.is_(True)).order_by(FiscalPaymentAllocation.payment_id)
        return list(self.db.scalars(_locked(query, lock)))

    def payments(self, tenant_id, sale_id, ids, *, lock=False):
        return list(self.db.scalars(_locked(select(SalePayment).where(SalePayment.tenant_id == tenant_id, SalePayment.sale_id == sale_id, SalePayment.id.in_(ids)).order_by(SalePayment.id), lock)))

    def owner(self, tenant_id, owner_id, *, lock=False):
        return self.db.scalar(_locked(select(ArcaSeriesOwnership).where(ArcaSeriesOwnership.tenant_id == tenant_id, ArcaSeriesOwnership.id == owner_id), lock))

    def claim_series_ownership(self, tenant_id, key, payload):
        # This is the sole internal global lookup. Never return another owner's
        # identity or tenant. Registry/global uniqueness prevents split numbering.
        query = select(ArcaSeriesOwnership).where(ArcaSeriesOwnership.series_key == key).with_for_update()
        owner = self.db.scalar(query)
        if owner is None:
            try:
                with self.db.begin_nested():
                    owner = ArcaSeriesOwnership(tenant_id=tenant_id, series_key=key, environment=payload.environment, cuit=payload.issuer.cuit, point_of_sale=payload.point_of_sale, document_type=payload.document_type, fence=0)
                    self.db.add(owner)
                    self.db.flush()
            except IntegrityError:
                owner = self.db.scalar(query.execution_options(populate_existing=True))
        if owner is None or owner.tenant_id != tenant_id:
            raise AppError(409, "arca_series_unavailable", "Esta serie remota no está disponible para esta clínica; solicita revisión de su configuración")
        return owner

    def attempts(self, tenant_id, emission_id):
        return list(self.db.scalars(select(ArcaEmissionAttempt).where(ArcaEmissionAttempt.tenant_id == tenant_id, ArcaEmissionAttempt.emission_id == emission_id).order_by(ArcaEmissionAttempt.created_at, ArcaEmissionAttempt.id)))

    def files(self, tenant_id, emission_id):
        return list(self.db.scalars(select(ArcaDocumentFile).where(ArcaDocumentFile.tenant_id == tenant_id, ArcaDocumentFile.emission_id == emission_id).order_by(ArcaDocumentFile.created_at.desc(), ArcaDocumentFile.id)))

    def file(self, tenant_id, emission_id, file_id):
        return self.db.scalar(select(ArcaDocumentFile).where(ArcaDocumentFile.tenant_id == tenant_id, ArcaDocumentFile.emission_id == emission_id, ArcaDocumentFile.id == file_id))

    def document(self, tenant_id, sale_id, document_id, *, lock=False):
        return self.db.scalar(_locked(select(SaleFiscalDocument).where(SaleFiscalDocument.tenant_id == tenant_id, SaleFiscalDocument.sale_id == sale_id, SaleFiscalDocument.id == document_id), lock))

    def add(self, row):
        self.db.add(row)
        self.db.flush()
        return row

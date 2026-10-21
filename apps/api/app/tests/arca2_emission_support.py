"""Synthetic business fixtures and runtime injection for orchestration tests."""
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
import uuid

from sqlalchemy import select

from app.core.errors import AppError
from app.models.payment import PaymentMethod, SalePayment
from app.models.sale import Sale, SaleItem
from app.models.sale_fiscal import FiscalIssuer
from app.schemas.fiscal_emission import FiscalEmissionCreate
from app.schemas.fiscal_proposal import FiscalProposalApprove, FiscalProposalGenerate
from app.services.arca_wsfe import ArcaWsfeClient
from app.services.fiscal_proposal import FiscalProposalService
from app.tests.arca2_support import ControlledArcaTransport, synthetic_payload, synthetic_ticket
from app.tests.fiscal_test_support import seed_fiscal_case


NOW = datetime(2026, 10, 20, 12, tzinfo=UTC)


class SyntheticEmissionRuntime:
    """Only tests import this runtime; no application flag can select it."""
    def __init__(self, *, transport=None, clock=None, external_enabled=True):
        self.transport = transport or ControlledArcaTransport()
        self.clock = clock or (lambda: NOW)
        self.external_enabled = external_enabled
        self.ensure_calls = []
        self.ticket_calls = []
        self.status_calls = []
        self.wsfe = ArcaWsfeClient("homologation", transport=self.transport, clock=self.clock)

    def ensure_available(self, tenant_id, reference, environment, represented_cuit):
        # These are guards, never secret resolution or outbound authentication.
        if environment == "production":
            raise AppError(403, "arca_production_blocked", "Production is blocked in this synthetic runtime")
        if not self.external_enabled:
            raise AppError(409, "arca_external_disabled", "External emission is explicitly disabled")
        self.ensure_calls.append((tenant_id, reference, environment, represented_cuit))

    def get_ticket(self, tenant_id, reference, environment, represented_cuit):
        self.ensure_available(tenant_id, reference, environment, represented_cuit)
        self.ticket_calls.append((tenant_id, reference, environment, represented_cuit))
        return synthetic_ticket(now=self.clock(), represented_cuit=represented_cuit,
                                auth_scope="synthetic-tenant-" + str(tenant_id))

    def credential_status(self, tenant_id, reference, environment, represented_cuit):
        self.status_calls.append((tenant_id, reference, environment, represented_cuit))
        return {"status": "ready", "state": "ready", "reference": reference,
                "environment": environment, "fingerprint": "f" * 64,
                "expires_at": "2026-10-21T12:00:00+00:00", "represented_cuit": represented_cuit,
                "remote_validation": "pending"}

    def close(self):
        self.wsfe.close()


class SyntheticEmissionStorage:
    bucket_name = "arca2-synthetic-storage"

    def __init__(self, *, fail_upload=False):
        self.fail_upload = fail_upload
        self.objects = {}
        self.uploads = []
        self.deletes = []

    def upload_clinical_file(self, *, object_path, content, content_type):
        assert content_type == "application/pdf"
        self.uploads.append(object_path)
        if self.fail_upload:
            raise RuntimeError("Synthetic storage failure")
        self.objects[object_path] = bytes(content)

    def download_object_bytes(self, *, bucket_name, object_path):
        assert bucket_name == self.bucket_name
        return self.objects[object_path]

    def delete_clinical_file(self, *, bucket_name, object_path):
        assert bucket_name == self.bucket_name
        self.deletes.append(object_path)
        self.objects.pop(object_path, None)


def seed_emission_case(db, *, point_of_sale=1, reuse_case=None):
    if reuse_case is None:
        case = seed_fiscal_case(db, point_of_sale=point_of_sale)
    else:
        method = db.scalar(select(PaymentMethod).where(
            PaymentMethod.tenant_id == reuse_case.tenant_id, PaymentMethod.id == reuse_case.method_id))
        sale = Sale(tenant_id=reuse_case.tenant_id, sale_date=date(2026, 10, 20), currency="ARS",
            subtotal_ars=Decimal("100.00"), discount_total_ars=Decimal("0.00"), total_ars=Decimal("100.00"),
            status="confirmed", confirmed_at=NOW, confirmed_by_user_id=reuse_case.context.user_id)
        sale.items.append(SaleItem(tenant_id=reuse_case.tenant_id, line_type="service",
            description_snapshot="Another synthetic veterinary service", unit_snapshot="unit", quantity=Decimal("1"),
            unit_price_ars=Decimal("100.00"), discount_percentage=Decimal("0"), line_subtotal_ars=Decimal("100.00"),
            line_discount_ars=Decimal("0"), line_total_ars=Decimal("100.00"), line_order=1))
        db.add(sale)
        db.flush()
        payment = SalePayment(tenant_id=reuse_case.tenant_id, sale_id=sale.id, payment_method_id=method.id,
            payment_method_label_snapshot=method.label, payment_method_type_snapshot=method.type,
            amount_ars=Decimal("100.00"), received_at=NOW, is_active=True, created_by_user_id=reuse_case.context.user_id)
        db.add(payment)
        db.commit()
        case = SimpleNamespace(**{**vars(reuse_case), "sale_id": sale.id, "payment_id": payment.id})
    issuer = db.scalar(select(FiscalIssuer).where(FiscalIssuer.tenant_id == case.tenant_id, FiscalIssuer.id == case.issuer_id))
    proposals = FiscalProposalService(db).generate(case.context, case.sale_id,
        FiscalProposalGenerate(payment_ids=[case.payment_id], fiscal_series_id=case.series_id,
                               fiscal_description="Explicitly reviewed synthetic veterinary service"))
    assert len(proposals) == 1
    proposal = FiscalProposalService(db).approve(case.context, case.sale_id, proposals[0].id,
        FiscalProposalApprove(content_hash=proposals[0].content_hash, confirm_fiscal_identity=True),
        idempotency_key="arca2-synthetic-approval-" + uuid.uuid4().hex)
    case.proposal = proposal
    case.payload = synthetic_payload(number=None, document_type=15,
        point_of_sale=point_of_sale if reuse_case is None else reuse_case.payload.point_of_sale,
        issuer={"cuit": issuer.cuit, "legal_name": issuer.legal_name, "tax_condition": issuer.tax_condition,
                "fiscal_address": "Explicit synthetic fiscal address", "gross_income_registration": "Synthetic IIBB",
                "activity_start_date": "2020-01-01"})
    case.create = FiscalEmissionCreate(proposal_id=proposal.id, fiscal_data=case.payload, confirm_fiscal_identity=True)
    return case

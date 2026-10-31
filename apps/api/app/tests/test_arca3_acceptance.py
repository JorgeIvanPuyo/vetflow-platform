"""Cross-feature acceptance with synthetic clinics and the real fiscal services.

ARCA.1 already covers individual policy/blocker/permission combinations;
ARCA.2 covers protocol, recovery, encryption and PDF failures independently.
These cases connect checkout, attribution, durable emission, recovery and file
history. The ledger is an injected HTTP transport: SOAP serialization/parsing
and the business orchestrator run unchanged. No external service is contacted.
"""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
import hashlib
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import func, select

from app.core.errors import AppError
from app.models.arca_emission import ArcaEmissionIntent, ArcaSeriesOwnership
from app.models.fiscal_configuration import FiscalSeries
from app.models.fiscal_proposal import FiscalPaymentAllocation, FiscalProposal
from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.payment import PaymentMethod, SalePayment
from app.models.sale import Sale, SaleItem
from app.models.sale_fiscal import FiscalIssuer, SaleFiscalDocument, SaleFiscalDocumentFileVersion
from app.schemas.fiscal_configuration import FiscalPolicyUpdate, FiscalSeriesCreate
from app.schemas.fiscal_emission import FiscalEmissionCreate
from app.schemas.fiscal_proposal import FiscalManualAllocation, FiscalProposalApprove, FiscalProposalGenerate
from app.schemas.sale import SaleConfirm
from app.services.arca_emission import ArcaEmissionService
from app.services.fiscal_configuration import FiscalConfigurationService
from app.services.fiscal_proposal import FiscalProposalService
from app.services.payment import SalePaymentService
from app.services.sale import SaleService
from app.services.sale_confirmation import SaleConfirmationService
from app.services.sale_fiscal_document import SaleFiscalDocumentService
from app.tests.arca2_emission_support import NOW, SyntheticEmissionRuntime, SyntheticEmissionStorage, seed_emission_case
from app.tests.arca2_support import ControlledArcaTransport, synthetic_payload
from app.tests.fiscal_test_support import context_for, seed_fiscal_case
from app.tests.test_arca1_proposals import _extra_method, _extra_payment, _inventory, _manual_document, _second_issuer


class TransactionCheckingLedger(ControlledArcaTransport):
    def __init__(self, db, **options):
        super().__init__(**options)
        self.db = db

    def handle_request(self, request):
        assert not self.db.in_transaction(), "Fiscal HTTP started with an open business transaction"
        return super().handle_request(request)


class TransactionCheckingStorage(SyntheticEmissionStorage):
    def __init__(self, db):
        super().__init__()
        self.db = db

    def upload_clinical_file(self, **options):
        assert not self.db.in_transaction(), "Fiscal PDF upload started with an open business transaction"
        super().upload_clinical_file(**options)


@pytest.fixture()
def laboratory(db_session):
    time = SimpleNamespace(now=NOW)
    ledger = {}
    runtimes = []

    def restart():
        transport = TransactionCheckingLedger(db_session, records=ledger, points_of_sale=(1, 2))
        runtime = SyntheticEmissionRuntime(transport=transport, clock=lambda: time.now)
        runtimes.append(runtime)
        return runtime

    lab = SimpleNamespace(time=time, ledger=ledger, runtimes=runtimes,
                          storage=TransactionCheckingStorage(db_session), restart=restart)
    lab.runtime = restart()
    try:
        yield lab
    finally:
        for runtime in runtimes:
            runtime.close()


def _service(db, lab, *, runtime=None):
    return ArcaEmissionService(db, runtime=runtime or lab.runtime, storage=lab.storage,
                               clock=lambda: lab.time.now, owner_id=uuid.uuid4().hex)


def _record(db, model, case, record_id):
    return db.scalar(select(model).where(model.tenant_id == case.tenant_id, model.id == record_id))


def _payments(db, case):
    return list(db.scalars(select(SalePayment).where(
        SalePayment.tenant_id == case.tenant_id, SalePayment.sale_id == case.sale_id).order_by(SalePayment.id)))


def _book(db, case):
    return [(row.id, row.payment_method_id, row.amount_ars, row.is_active,
             row.payment_method_label_snapshot, row.payment_method_type_snapshot,
             row.reference, row.received_at) for row in _payments(db, case)]


def _allocations(db, case):
    return list(db.scalars(select(FiscalPaymentAllocation).where(
        FiscalPaymentAllocation.tenant_id == case.tenant_id,
        FiscalPaymentAllocation.sale_id == case.sale_id,
        FiscalPaymentAllocation.is_active.is_(True))))


def _approve(db, case, proposal):
    return FiscalProposalService(db).approve(case.context, case.sale_id, proposal.id,
        FiscalProposalApprove(content_hash=proposal.content_hash, confirm_fiscal_identity=True),
        "acceptance-approval-" + uuid.uuid4().hex)


def _create(db, case, proposal):
    issuer = _record(db, FiscalIssuer, case, proposal.fiscal_issuer_id)
    series = _record(db, FiscalSeries, case, proposal.fiscal_series_id)
    money = format(proposal.total_ars, ".2f")
    payload = synthetic_payload(number=None, concept=proposal.concept,
        point_of_sale=series.point_of_sale, document_type=11 if series.document_type == "invoice_c" else 15,
        issuer={"cuit": issuer.cuit, "legal_name": issuer.legal_name, "tax_condition": issuer.tax_condition,
                "fiscal_address": "Explicit synthetic address", "gross_income_registration": "Synthetic IIBB",
                "activity_start_date": "2020-01-01"},
        total=money, net_amount=money,
        service_from=None if proposal.concept == 1 else "2026-10-01",
        service_to=None if proposal.concept == 1 else "2026-10-20",
        payment_due=None if proposal.concept == 1 else "2026-10-20",
        lines=[{"description": proposal.fiscal_description, "quantity": "1", "unit_price": money, "total": money}])
    return FiscalEmissionCreate(proposal_id=proposal.id, fiscal_data=payload, confirm_fiscal_identity=True)


def _checkout(db, base, entries, *, product=None):
    """Use actual confirmation/payment services; configuration comes from base."""
    sale = Sale(tenant_id=base.tenant_id, sale_date=date(2026, 10, 20), currency="ARS",
        subtotal_ars=Decimal("100.00"), discount_total_ars=Decimal("0.00"),
        total_ars=Decimal("100.00"), status="draft")
    sale.items.append(SaleItem(tenant_id=base.tenant_id, line_type="product" if product else "service",
        inventory_item_id=product.id if product else None, description_snapshot="Synthetic checkout line",
        unit_snapshot="unit", quantity=Decimal("1.00"), unit_price_ars=Decimal("100.00"),
        discount_percentage=Decimal("0"), line_subtotal_ars=Decimal("100.00"),
        line_discount_ars=Decimal("0.00"), line_total_ars=Decimal("100.00"), line_order=1))
    db.add(sale)
    db.commit()
    payload = SaleConfirm(confirm=True, initial_payments=[{
        "payment_method_id": method.id, "amount_ars": amount,
        "received_at": NOW, "reference": "Synthetic checkout " + str(index),
    } for index, (method, amount) in enumerate(entries)])
    key = "acceptance-checkout-" + uuid.uuid4().hex
    confirmed = SaleConfirmationService(db).confirm(base.tenant_id, sale.id, payload,
        user_id=base.context.user_id, idempotency_key=key)
    assert confirmed.status == "confirmed" and confirmed.paid_total_ars == Decimal("100.00")
    return SimpleNamespace(**{**vars(base), "sale_id": sale.id, "checkout": payload, "checkout_key": key})


@pytest.mark.parametrize("scope,first_total,committed,excluded", [
    ("electronic_only", Decimal("33.33"), Decimal("66.67"), Decimal("33.33")),
    ("all_payments", Decimal("66.66"), Decimal("100.00"), Decimal("0.00")),
])
def test_mixed_checkout_three_issuers_two_clinics_recover_independently_without_changing_the_book(
        db_session, laboratory, scope, first_total, committed, excluded):
    db, lab = db_session, laboratory
    base = seed_fiscal_case(db)
    second, second_series = _second_issuer(db, base)
    original_method = _record(db, PaymentMethod, base, base.method_id)
    second_method = _extra_method(db, base, issuer_id=second.id)
    cash_method = _extra_method(db, base, kind="cash", issuer_id=base.issuer_id)
    db.commit()
    FiscalConfigurationService(db).update_policy(base.context, FiscalPolicyUpdate(payment_scope=scope))
    case = _checkout(db, base, [(original_method, "10.01"), (original_method, "23.32"),
                               (second_method, "33.34"), (cash_method, "33.33")])
    foreign = seed_fiscal_case(db)
    third = _record(db, FiscalIssuer, foreign, foreign.issuer_id)
    third.cuit, third.tax_id, third.legal_name = "27123456780", "27123456780", "Third synthetic fiscal identity"
    _record(db, FiscalSeries, foreign, foreign.series_id).cuit_snapshot = third.cuit
    db.commit()
    original_book, foreign_book = _book(db, case), _book(db, foreign)
    assert db.scalar(select(func.count()).select_from(ArcaEmissionIntent)) == 0
    assert db.scalar(select(func.count()).select_from(SaleFiscalDocument)) == 0
    assert db.scalar(select(func.count()).select_from(FiscalPaymentAllocation)) == 0
    assert lab.runtime.ticket_calls == [] and lab.runtime.transport.calls == []

    proposals = FiscalProposalService(db).generate(case.context, case.sale_id, FiscalProposalGenerate())
    assert {row.fiscal_series_id: row.total_ars for row in proposals} == {
        case.series_id: first_total, second_series.id: Decimal("33.34")}
    review = FiscalProposalService(db).review(case.context, case.sale_id)
    assert review.totals.active_payments_ars == Decimal("100.00")
    assert review.totals.proposed_ars == committed and review.totals.excluded_ars == excluded
    assert _allocations(db, case) == []
    proposals = [_approve(db, case, row) for row in proposals]
    third_proposal = _approve(db, foreign, FiscalProposalService(db).generate(
        foreign.context, foreign.sale_id, FiscalProposalGenerate())[0])
    approval_snapshots = {row.id: (row.content_hash, deepcopy(row.snapshot)) for row in [*proposals, third_proposal]}
    payment_amounts = {row.id: row.amount_ars for row in _payments(db, case)}
    allocations = _allocations(db, case)
    assert len({row.payment_id for row in allocations}) == len(allocations)
    assert all(row.amount_ars == payment_amounts[row.payment_id] for row in allocations)
    assert sum((row.amount_ars for row in allocations), Decimal("0.00")) == committed
    expected_payment_ids = {row.id for row in _payments(db, case)
                            if scope == "all_payments" or row.payment_method_type_snapshot != "cash"}
    assert {row.payment_id for row in allocations} == expected_payment_ids

    first = next(row for row in proposals if row.fiscal_issuer_id == case.issuer_id)
    second_proposal = next(row for row in proposals if row.fiscal_issuer_id == second.id)
    operations = [(case, row, _service(db, lab).prepare(case.context, case.sale_id, _create(db, case, row),
        "acceptance-emission-" + str(row.id))) for row in (first, second_proposal)]
    third_operation = _service(db, lab).prepare(foreign.context, foreign.sale_id, _create(db, foreign, third_proposal),
        "acceptance-emission-" + str(third_proposal.id))
    lab.runtime.transport.timeout_after_authorization = True
    uncertain = _service(db, lab).issue(case.context, case.sale_id, operations[0][2].id)
    assert uncertain.status == "unknown" and uncertain.number == 1
    frozen_request = deepcopy(uncertain.business_snapshot)
    request_hash = uncertain.request_hash
    # An uncertain remote series cannot consume or block another issuer's series.
    for owner_case, operation in ((case, operations[1][2]), (foreign, third_operation)):
        result = _service(db, lab).issue(owner_case.context, owner_case.sale_id, operation.id)
        assert result.status == "authorized" and result.number == 1
    assert lab.runtime.transport.authorization_calls == 3

    # A failed exact query is not evidence of nonexistence, even with explicit retry requested.
    lab.time.now += timedelta(seconds=121)
    restarted = lab.restart()
    restarted.transport.mode = "fault"
    still_unknown = _service(db, lab, runtime=restarted).reconcile(case.context, case.sale_id,
        uncertain.id, retry_same_request=True)
    assert still_unknown.status == "unknown" and still_unknown.number == 1
    assert restarted.transport.authorization_calls == 0
    restarted.transport.mode = "authorized"
    recovered = _service(db, lab, runtime=restarted).reconcile(case.context, case.sale_id, uncertain.id)
    assert recovered.status == "authorized" and recovered.business_snapshot == frozen_request
    assert recovered.request_hash == request_hash and recovered.number == 1
    assert restarted.transport.calls.count("FECompConsultar") == 2
    assert restarted.transport.authorization_calls == 0
    assert set(lab.ledger) == {("20123456786", 1, 15, 1), ("30712345671", 1, 15, 1), ("27123456780", 1, 15, 1)}

    # Checkout replay remains commercial-only after fiscal approval and recovery.
    replay = SaleConfirmationService(db)
    replay.confirm(case.tenant_id, case.sale_id, case.checkout,
        user_id=case.context.user_id, idempotency_key=case.checkout_key)
    assert replay.idempotency_replayed
    assert _book(db, case) == original_book and _book(db, foreign) == foreign_book
    assert len(_allocations(db, case)) == len(expected_payment_ids)
    assert sum((row.amount_ars for row in _allocations(db, case)), Decimal("0.00")) == committed
    for owner_case, rows in ((case, proposals), (foreign, [third_proposal])):
        sale = SaleService(db).get(owner_case.tenant_id, owner_case.sale_id)
        assert sale.status == "confirmed" and sale.fiscal_status == "pending" and sale.fiscal_document is None
        assert len(sale.fiscal_documents) == len(rows)
        for proposal in rows:
            frozen = _record(db, FiscalProposal, owner_case, proposal.id)
            assert frozen.status == "authorized"
            assert (frozen.content_hash, frozen.snapshot) == approval_snapshots[proposal.id]
    assert len(_service(db, lab).list(context_for(case.actors["secretaria"]), case.sale_id)["operations"]) == 2
    own_vet_operations = _service(db, lab).list(context_for(case.actors["medico_veterinario"]), case.sale_id)["operations"]
    assert [row["id"] for row in own_vet_operations] == [str(recovered.id)]
    with pytest.raises(AppError) as cross_tenant:
        _service(db, lab).list(case.context, foreign.sale_id)
    assert cross_tenant.value.status_code == 404


def test_one_cuit_keeps_pos_and_document_type_independent_while_another_series_is_uncertain(db_session, laboratory):
    db, lab = db_session, laboratory
    base = seed_fiscal_case(db)
    issuer = _record(db, FiscalIssuer, base, base.issuer_id)
    issuer.can_issue_product_invoice_c = True
    issuer.product_document_type, issuer.product_document_code = "invoice_c", "011"
    db.commit()
    configuration = FiscalConfigurationService(db)
    pos_two = configuration.create_series(base.context, FiscalSeriesCreate(fiscal_issuer_id=issuer.id,
        point_of_sale=2, document_type="receipt_c", concept=2, credential_reference="opaque://test/credential"))
    invoice = configuration.create_series(base.context, FiscalSeriesCreate(fiscal_issuer_id=issuer.id,
        point_of_sale=1, document_type="invoice_c", concept=1, credential_reference="opaque://test/credential"))
    method = _record(db, PaymentMethod, base, base.method_id)
    product = _inventory(db, base)
    db.commit()
    cases = [_checkout(db, base, [(method, "50.00"), (method, "50.00")], product=product if index == 2 else None)
             for index in range(3)]
    assert _record(db, InventoryItem, base, product.id).current_stock == Decimal("16.00")
    operations = []
    for case, series_id in zip(cases, (base.series_id, pos_two.id, invoice.id), strict=True):
        # Automatic grouping is ambiguous; the user must choose the actual series.
        assert FiscalProposalService(db).generate(case.context, case.sale_id, FiscalProposalGenerate()) == []
        proposal = _approve(db, case, FiscalProposalService(db).generate(case.context, case.sale_id,
            FiscalProposalGenerate(fiscal_series_id=series_id))[0])
        operation = _service(db, lab).prepare(case.context, case.sale_id, _create(db, case, proposal),
            "acceptance-series-" + str(proposal.id))
        operations.append(operation)
    lab.runtime.transport.timeout_after_authorization = True
    assert _service(db, lab).issue(cases[0].context, cases[0].sale_id, operations[0].id).status == "unknown"
    for case, operation in zip(cases[1:], operations[1:], strict=True):
        result = _service(db, lab).issue(case.context, case.sale_id, operation.id)
        assert result.status == "authorized" and result.number == 1
    lab.time.now += timedelta(seconds=121)
    recovered = _service(db, lab, runtime=lab.restart()).reconcile(cases[0].context, cases[0].sale_id, operations[0].id)
    assert recovered.status == "authorized" and recovered.number == 1
    assert set(lab.ledger) == {("20123456786", 1, 15, 1), ("20123456786", 2, 15, 1), ("20123456786", 1, 11, 1)}
    assert db.scalar(select(func.count()).select_from(ArcaSeriesOwnership).where(
        ArcaSeriesOwnership.tenant_id == base.tenant_id)) == 3
    assert _record(db, InventoryItem, base, product.id).current_stock == Decimal("16.00")
    assert db.scalar(select(func.count()).select_from(InventoryMovement).where(
        InventoryMovement.tenant_id == base.tenant_id)) == 1
    assert sum(runtime.transport.authorization_calls for runtime in lab.runtimes) == 3


def test_regularized_manual_history_and_remote_remainder_keep_distinct_allocations_and_file_versions(db_session, laboratory):
    db, lab = db_session, laboratory
    case = seed_fiscal_case(db, payment_amount="33.33")
    method = _record(db, PaymentMethod, case, case.method_id)
    remainder = _extra_payment(db, case, method, "66.67")
    document, historical_version = _manual_document(db, case, amount="33.33")
    content = b"%PDF-1.4 synthetic preserved historical document"
    document.bucket_name = lab.storage.bucket_name
    document.storage_key = f"tenants/{case.tenant_id}/sales/{case.sale_id}/fiscal-documents/{document.id}/original.pdf"
    document.sha256, document.size_bytes = hashlib.sha256(content).hexdigest(), len(content)
    db.commit()
    lab.storage.objects[document.storage_key] = content
    original_manual = (document.issuer_name_snapshot, document.issuer_tax_id_snapshot,
        document.document_number, document.storage_key, document.sha256)
    original_history = (historical_version.id, historical_version.storage_key, historical_version.sha256)
    original_book = _book(db, case)
    service = FiscalProposalService(db)
    draft = service.generate(case.context, case.sale_id, FiscalProposalGenerate(payment_ids=[remainder.id],
        fiscal_series_id=case.series_id, fiscal_description="Explicit whole-payment remainder"))[0]
    with pytest.raises(AppError) as unknown_manual:
        _approve(db, case, draft)
    assert unknown_manual.value.code == "fiscal_manual_allocation_unknown"
    assert _allocations(db, case) == []
    with pytest.raises(AppError) as partial_allocation:
        service.regularize_manual(case.context, case.sale_id, document.id,
            FiscalManualAllocation(payment_ids=[remainder.id], confirm_fiscal_identity=True), "wrong-whole-payment")
    assert partial_allocation.value.code == "fiscal_manual_total_mismatch"
    payload = FiscalManualAllocation(payment_ids=[case.payment_id], confirm_fiscal_identity=True)
    for _ in range(2):
        service.regularize_manual(case.context, case.sale_id, document.id, payload, "acceptance-manual-allocation")
    manual = _record(db, SaleFiscalDocument, case, document.id)
    assert manual.allocation_reviewed_by_user_id == case.context.user_id and manual.allocation_reviewed_at
    assert len(_allocations(db, case)) == 1
    approved = _approve(db, case, draft)
    operation = _service(db, lab).prepare(case.context, case.sale_id, _create(db, case, approved), "acceptance-manual-remainder")
    authorized = _service(db, lab).issue(case.context, case.sale_id, operation.id)
    assert authorized.status == "authorized" and authorized.file_status == "ready"
    first_version = authorized.file_versions[0]
    first_descriptor, first_bytes = _service(db, lab).download(case.context, case.sale_id, authorized.id,
        version_id=first_version.id)
    regenerated = _service(db, lab).regenerate(case.context, case.sale_id, authorized.id)
    assert len(regenerated.file_versions) == 2
    old_descriptor, old_bytes = _service(db, lab).download(case.context, case.sale_id, authorized.id,
        version_id=first_version.id)
    assert old_descriptor.id == first_descriptor.id and old_bytes == first_bytes
    lab.storage.fail_upload = True
    failed_regeneration = _service(db, lab).regenerate(case.context, case.sale_id, authorized.id)
    assert failed_regeneration.status == "authorized" and failed_regeneration.file_status == "ready"
    assert failed_regeneration.allowed_actions.download and len(failed_regeneration.file_versions) == 2
    assert any(attempt.outcome == "regeneration_failed_previous_version_retained"
               for attempt in failed_regeneration.attempts)
    _, retained_bytes = _service(db, lab).download(case.context, case.sale_id, authorized.id,
        version_id=first_version.id)
    assert retained_bytes == first_bytes
    lab.storage.fail_upload = False
    assert (regenerated.document_id, regenerated.cae, regenerated.number) == (
        authorized.document_id, authorized.cae, authorized.number)
    assert lab.runtime.transport.authorization_calls == 1 and len(lab.ledger) == 1
    allocations = _allocations(db, case)
    assert {(row.payment_id, row.amount_ars, row.fiscal_document_id, row.proposal_id) for row in allocations} == {
        (case.payment_id, Decimal("33.33"), document.id, None),
        (remainder.id, Decimal("66.67"), None, approved.id)}
    uploads = len(lab.storage.uploads)
    with pytest.raises(AppError) as frozen_file:
        SaleFiscalDocumentService(db, lab.storage).update(case.tenant_id, case.sale_id,
            issuer_id=None, document_type=None, document_code=None, document_number="Forbidden rewrite",
            issue_date=None, filename="changed.pdf", declared_content_type="application/pdf",
            content=b"%PDF-1.4 forbidden replacement", updated_by_user_id=case.context.user_id)
    assert frozen_file.value.code == "fiscal_document_allocated" and len(lab.storage.uploads) == uploads
    db.rollback()
    manual, downloaded = SaleFiscalDocumentService(db, lab.storage).download(case.tenant_id, case.sale_id)
    assert downloaded == content
    assert (manual.issuer_name_snapshot, manual.issuer_tax_id_snapshot, manual.document_number,
            manual.storage_key, manual.sha256) == original_manual
    history = _record(db, SaleFiscalDocumentFileVersion, case, historical_version.id)
    assert (history.id, history.storage_key, history.sha256) == original_history
    sale = SaleService(db).get(case.tenant_id, case.sale_id)
    assert sale.fiscal_document.id == document.id
    assert {(row.source, row.total_ars_snapshot) for row in sale.fiscal_documents} == {
        ("manual", Decimal("33.33")), ("arca", Decimal("66.67"))}
    assert _book(db, case) == original_book


def test_cancelled_approval_cannot_send_its_prepared_intent_after_the_payment_is_reserved_again(db_session, laboratory):
    db, lab = db_session, laboratory
    case = seed_emission_case(db)
    original_book = _book(db, case)
    old = _service(db, lab).prepare(case.context, case.sale_id, case.create, "acceptance-cancelled-intent")
    FiscalProposalService(db).cancel(case.context, case.sale_id, case.proposal.id, reason="Reviewed before sending")
    assert _allocations(db, case) == []
    replacement = _approve(db, case, FiscalProposalService(db).generate(case.context, case.sale_id, FiscalProposalGenerate())[0])
    current = _service(db, lab).prepare(case.context, case.sale_id, _create(db, case, replacement), "acceptance-replacement-intent")
    with pytest.raises(AppError) as obsolete:
        _service(db, lab).issue(case.context, case.sale_id, old.id)
    assert obsolete.value.code == "arca_approval_required"
    assert lab.runtime.ticket_calls == [] and lab.runtime.transport.calls == []
    authorized = _service(db, lab).issue(case.context, case.sale_id, current.id)
    assert authorized.status == "authorized" and lab.runtime.transport.authorization_calls == 1
    assert [row.proposal_id for row in _allocations(db, case)] == [replacement.id]
    for action, expected_code in (("void", "fiscal_payment_reserved"), ("reverse", "fiscal_sale_reserved")):
        with pytest.raises(AppError) as reserved:
            if action == "void":
                SalePaymentService(db).void(case.tenant_id, case.payment_id, reason="Blocked correction", user_id=case.context.user_id)
            else:
                SaleService(db).reverse(case.tenant_id, case.sale_id, reason="Blocked correction", reversed_by_user_id=case.context.user_id)
        assert reserved.value.code == expected_code
    uploads = len(lab.storage.uploads)
    with pytest.raises(AppError) as manual_duplicate:
        SaleFiscalDocumentService(db, lab.storage).create(case.tenant_id, case.sale_id,
            issuer_id=case.issuer_id, document_type="receipt_c", document_code="015", document_number="NO-SECOND-DOCUMENT",
            issue_date=date(2026, 10, 20), filename="duplicate.pdf", declared_content_type="application/pdf",
            content=b"%PDF-1.4 synthetic duplicate", uploaded_by_user_id=case.context.user_id)
    assert manual_duplicate.value.code == "fiscal_sale_reserved" and len(lab.storage.uploads) == uploads
    assert _book(db, case) == original_book
    assert db.scalar(select(func.count()).select_from(SaleFiscalDocument).where(
        SaleFiscalDocument.tenant_id == case.tenant_id, SaleFiscalDocument.sale_id == case.sale_id)) == 1

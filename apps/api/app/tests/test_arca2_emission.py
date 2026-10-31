"""Durable orchestration through the real SOAP codec and a remote test ledger."""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.models.arca_emission import ArcaEmissionIntent
from app.models.fiscal_configuration import FiscalPolicy, FiscalSeries
from app.models.fiscal_proposal import FiscalPaymentAllocation, FiscalProposal
from app.models.payment import SalePayment
from app.models.sale import Sale
from app.models.sale_fiscal import FiscalIssuer, SaleFiscalDocument
from app.schemas.fiscal_emission import FiscalEmissionCreate
from app.services.arca_emission import ArcaEmissionService
from app.services.fiscal_proposal import FiscalProposalService
from app.services.payment import SalePaymentService
from app.services.sale import SaleService
from app.tests.arca2_emission_support import (
    NOW, SyntheticEmissionRuntime, SyntheticEmissionStorage, seed_emission_case,
)


@pytest.fixture()
def emission_case(db_session):
    return seed_emission_case(db_session)


@pytest.fixture()
def laboratory():
    time = SimpleNamespace(now=NOW)
    runtime = SyntheticEmissionRuntime(clock=lambda: time.now)
    storage = SyntheticEmissionStorage()
    try:
        yield SimpleNamespace(time=time, runtime=runtime, storage=storage)
    finally:
        runtime.close()


def _service(db, lab, *, owner="synthetic-worker"):
    return ArcaEmissionService(db, runtime=lab.runtime, storage=lab.storage,
                               clock=lambda: lab.time.now, owner_id=owner)


def _prepare(db, lab, case, *, key="synthetic-emission-intent"):
    return _service(db, lab).prepare(case.context, case.sale_id, case.create, key)


def _row(db, case, operation):
    db.expire_all()
    return db.scalar(select(ArcaEmissionIntent).where(
        ArcaEmissionIntent.tenant_id == case.tenant_id, ArcaEmissionIntent.id == operation.id))


def _active_count(db, case):
    return db.scalar(select(func.count()).select_from(FiscalPaymentAllocation).where(
        FiscalPaymentAllocation.tenant_id == case.tenant_id,
        FiscalPaymentAllocation.payment_id == case.payment_id,
        FiscalPaymentAllocation.is_active.is_(True)))


def _document_count(db, case):
    return db.scalar(select(func.count()).select_from(SaleFiscalDocument).where(
        SaleFiscalDocument.tenant_id == case.tenant_id, SaleFiscalDocument.sale_id == case.sale_id,
        SaleFiscalDocument.source == "arca"))


def test_prepare_is_normalized_idempotent_and_a_different_key_cannot_duplicate_proposal(db_session, emission_case, laboratory):
    case, lab = emission_case, laboratory
    operation = _prepare(db_session, lab, case)
    replay = _prepare(db_session, lab, case)
    assert operation.id == replay.id and operation.status == "prepared"
    assert operation.number is None and lab.runtime.transport.authorization_calls == 0
    changed = case.create.model_copy(update={"fiscal_data": case.payload.model_copy(update={
        "receiver": case.payload.receiver.model_copy(update={"name": "Changed reviewed recipient"})})})
    with pytest.raises(AppError) as error:
        _service(db_session, lab).prepare(case.context, case.sale_id, changed, "synthetic-emission-intent")
    assert error.value.status_code == 409
    try:
        same = _prepare(db_session, lab, case, key="second-key-same-proposal")
    except AppError as conflict:
        assert conflict.status_code == 409
    else:
        assert same.id == operation.id
    assert db_session.scalar(select(func.count()).select_from(ArcaEmissionIntent)) == 1


def test_issue_preserves_sale_payments_approval_and_homologation_is_not_productive_coverage(db_session, emission_case, laboratory):
    case, lab = emission_case, laboratory
    approval = db_session.scalar(select(FiscalProposal).where(FiscalProposal.tenant_id == case.tenant_id, FiscalProposal.id == case.proposal.id))
    frozen = (approval.content_hash, approval.snapshot, approval.payment_ids, approval.total_ars)
    operation = _prepare(db_session, lab, case)
    authorized = _service(db_session, lab).issue(case.context, case.sale_id, operation.id)
    assert authorized.status == "authorized" and authorized.environment == "homologation"
    assert authorized.cae and authorized.number == 1 and authorized.document_id
    again = _service(db_session, lab).issue(case.context, case.sale_id, operation.id)
    assert again.id == authorized.id and again.cae == authorized.cae
    assert lab.runtime.transport.authorization_calls == 1 and _document_count(db_session, case) == 1
    assert _active_count(db_session, case) == 1
    sale = SaleService(db_session).get(case.tenant_id, case.sale_id)
    assert sale.status == "confirmed" and sale.fiscal_status == "pending"
    assert sale.fiscal_document is None
    assert sale.fiscal_document_totals == [{"source": "arca", "authorization_status": "authorized", "environment": "homologation", "count": 1, "total_ars": 100}]
    assert sale.total_ars == 100 and sale.paid_total_ars == 100
    payment = db_session.scalar(select(SalePayment).where(SalePayment.tenant_id == case.tenant_id, SalePayment.id == case.payment_id))
    assert payment.is_active and payment.amount_ars == 100
    db_session.refresh(approval)
    assert (approval.content_hash, approval.snapshot, approval.payment_ids, approval.total_ars) == frozen


def test_response_lost_after_authorization_recovers_after_service_restart_without_new_send(db_session, emission_case, laboratory):
    case, lab = emission_case, laboratory
    lab.runtime.transport.timeout_after_authorization = True
    operation = _prepare(db_session, lab, case)
    unknown = _service(db_session, lab, owner="sender-before-restart").issue(case.context, case.sale_id, operation.id)
    assert unknown.status in {"unknown", "processing"}
    saved = _row(db_session, case, operation)
    number, request_hash, request_payload = saved.number, saved.request_hash, saved.request_payload
    assert number == 1 and request_hash and request_payload["number"] == 1
    assert _active_count(db_session, case) == 1 and _document_count(db_session, case) == 0
    assert len(lab.runtime.transport.records) == 1
    lab.time.now += timedelta(seconds=121)
    recovered = _service(db_session, lab, owner="restarted-process").reconcile(case.context, case.sale_id, operation.id)
    assert recovered.status == "authorized" and recovered.number == number
    saved = _row(db_session, case, operation)
    assert saved.request_hash == request_hash and saved.request_payload == request_payload
    assert _document_count(db_session, case) == 1 and _active_count(db_session, case) == 1
    assert lab.runtime.transport.authorization_calls == 1


def test_crash_after_number_persistence_requires_consult_then_explicit_identical_retry(db_session, emission_case, laboratory, monkeypatch):
    case, lab = emission_case, laboratory
    operation = _prepare(db_session, lab, case)
    sender = _service(db_session, lab, owner="crashed-worker")
    def crash(*_args, **_kwargs):
        raise SystemExit("Synthetic process crash before FECAESolicitar")
    monkeypatch.setattr(sender, "_after_number_persisted", crash)
    with pytest.raises(SystemExit):
        sender.issue(case.context, case.sale_id, operation.id)
    saved = _row(db_session, case, operation)
    number, request_hash, request_payload = saved.number, saved.request_hash, saved.request_payload
    assert number == 1 and request_payload["number"] == 1
    assert lab.runtime.transport.authorization_calls == 0
    lab.time.now += timedelta(seconds=121)
    restarted = _service(db_session, lab, owner="recovered-worker")
    not_found = restarted.reconcile(case.context, case.sale_id, operation.id)
    assert not_found.status in {"unknown", "processing"}
    assert lab.runtime.transport.authorization_calls == 0
    retried = restarted.reconcile(case.context, case.sale_id, operation.id, retry_same_request=True)
    assert retried.status == "authorized" and retried.number == number
    saved = _row(db_session, case, operation)
    assert saved.request_hash == request_hash and saved.request_payload == request_payload
    assert lab.runtime.transport.authorization_calls == 1 and len(lab.runtime.transport.records) == 1


def test_database_failure_after_cae_is_reconciled_without_reissuing(db_session, emission_case, laboratory, monkeypatch):
    case, lab = emission_case, laboratory
    operation = _prepare(db_session, lab, case)
    sender = _service(db_session, lab, owner="failed-persistence-worker")
    def fail_result(*_args, **_kwargs):
        raise RuntimeError("Synthetic database persistence failure after remote CAE")
    monkeypatch.setattr(sender, "_before_result_commit", fail_result)
    try:
        result = sender.issue(case.context, case.sale_id, operation.id)
    except (AppError, RuntimeError):
        db_session.rollback()
    else:
        assert result.status in {"unknown", "processing"}
    saved = _row(db_session, case, operation)
    assert saved.number == 1 and saved.request_payload and saved.request_hash
    assert len(lab.runtime.transport.records) == 1 and lab.runtime.transport.authorization_calls == 1
    lab.time.now += timedelta(seconds=121)
    recovered = _service(db_session, lab, owner="new-persistence-worker").reconcile(case.context, case.sale_id, operation.id)
    assert recovered.status == "authorized"
    assert _document_count(db_session, case) == 1 and _active_count(db_session, case) == 1
    assert lab.runtime.transport.authorization_calls == 1


@pytest.mark.parametrize("action", ["cancel_proposal", "void_payment", "reverse_sale"])
def test_uncertain_result_retains_reservations_and_blocks_incompatible_cancellation(db_session, emission_case, laboratory, action):
    case, lab = emission_case, laboratory
    lab.runtime.transport.timeout_after_authorization = True
    operation = _prepare(db_session, lab, case)
    assert _service(db_session, lab).issue(case.context, case.sale_id, operation.id).status in {"unknown", "processing"}
    with pytest.raises(AppError) as error:
        if action == "cancel_proposal":
            FiscalProposalService(db_session).cancel(case.context, case.sale_id, case.proposal.id, reason="Incompatible synthetic cancellation")
        elif action == "void_payment":
            SalePaymentService(db_session).void(case.tenant_id, case.payment_id, reason="Synthetic void", user_id=case.context.user_id)
        else:
            SaleService(db_session).reverse(case.tenant_id, case.sale_id, reason="Synthetic reversal", reversed_by_user_id=case.context.user_id)
    assert error.value.status_code == 409
    assert _active_count(db_session, case) == 1
    assert lab.runtime.transport.authorization_calls == 1


def test_remote_conflict_blocks_series_without_adopting_cae_or_advancing_number(db_session, emission_case, laboratory):
    case, lab = emission_case, laboratory
    lab.runtime.transport.timeout_after_authorization = True
    operation = _prepare(db_session, lab, case)
    _service(db_session, lab).issue(case.context, case.sale_id, operation.id)
    key = (case.payload.issuer.cuit, 1, 15, 1)
    lab.runtime.transport.records[key]["ImpTotal"] = "100.01"
    lab.time.now += timedelta(seconds=121)
    conflicted = _service(db_session, lab, owner="conflict-reconciler").reconcile(case.context, case.sale_id, operation.id)
    assert conflicted.status == "conflict" and conflicted.cae is None
    assert _document_count(db_session, case) == 0 and _active_count(db_session, case) == 1
    second = seed_emission_case(db_session, reuse_case=case)
    second_intent = _prepare(db_session, lab, second, key="second-proposal-pending-series")
    try:
        blocked = _service(db_session, lab).issue(second.context, second.sale_id, second_intent.id)
    except AppError as error:
        assert error.status_code == 409
    else:
        assert blocked.status in {"prepared", "processing", "unknown", "conflict"}
    assert _row(db_session, second, second_intent).number is None
    assert lab.runtime.transport.authorization_calls == 1


def test_definitive_rejection_requires_new_audited_intent_and_reuses_unconsumed_number(db_session, emission_case, laboratory):
    case, lab = emission_case, laboratory
    lab.runtime.transport.mode = "rejected"
    operation = _prepare(db_session, lab, case)
    rejected = _service(db_session, lab).issue(case.context, case.sale_id, operation.id)
    assert rejected.status == "rejected" and rejected.number == 1
    assert _document_count(db_session, case) == 0 and _active_count(db_session, case) == 1
    original = _row(db_session, case, operation)
    original_payload, original_hash = original.request_payload, original.request_hash
    line = case.payload.lines[0].model_copy(update={"description": "Explicit corrected fiscal description"})
    corrected_payload = case.payload.model_copy(update={"lines": (line,)})
    correction = FiscalEmissionCreate(proposal_id=case.proposal.id, fiscal_data=corrected_payload,
                                     confirm_fiscal_identity=True, supersedes_id=operation.id)
    corrected = _service(db_session, lab).prepare(case.context, case.sale_id, correction, "explicit-rejected-correction")
    assert corrected.id != operation.id
    lab.runtime.transport.mode = "authorized"
    authorized = _service(db_session, lab).issue(case.context, case.sale_id, corrected.id)
    assert authorized.status == "authorized" and authorized.number == 1
    original = _row(db_session, case, operation)
    assert original.state == "rejected" and original.request_payload == original_payload and original.request_hash == original_hash
    assert _document_count(db_session, case) == 1 and _active_count(db_session, case) == 1


def test_disabled_external_runtime_does_not_authorize_or_resolve_tickets(db_session, emission_case, laboratory):
    case, lab = emission_case, laboratory
    operation = _prepare(db_session, lab, case)
    before_tickets = list(lab.runtime.ticket_calls)
    before_calls = list(lab.runtime.transport.calls)
    lab.runtime.external_enabled = False
    with pytest.raises(AppError):
        _service(db_session, lab).issue(case.context, case.sale_id, operation.id)
    assert lab.runtime.ticket_calls == before_tickets and lab.runtime.transport.calls == before_calls
    assert _document_count(db_session, case) == 0


@pytest.mark.parametrize("change,expected_code", [
    ("policy_disabled", "fiscal_module_disabled"),
    ("issuer_inactive", "arca_issuer_changed"),
    ("issuer_cuit", "arca_issuer_changed"),
    ("issuer_legal_name", "arca_issuer_changed"),
    ("issuer_tax_condition", "arca_issuer_changed"),
    ("issuer_capability", "arca_configuration_pending"),
    ("issuer_responsible", "arca_configuration_pending"),
    ("series_inactive", "arca_series_changed"),
    ("series_concept", "arca_series_changed"),
    ("series_authorization_mode", "arca_series_changed"),
    ("series_reference", "arca_credentials_changed"),
])
def test_configuration_changes_before_first_send_block_without_ticket_resolution(db_session, emission_case, laboratory, change, expected_code):
    case, lab = emission_case, laboratory
    operation = _prepare(db_session, lab, case)
    policy = db_session.scalar(select(FiscalPolicy).where(FiscalPolicy.tenant_id == case.tenant_id))
    issuer = db_session.scalar(select(FiscalIssuer).where(FiscalIssuer.tenant_id == case.tenant_id, FiscalIssuer.id == case.issuer_id))
    series = db_session.scalar(select(FiscalSeries).where(FiscalSeries.tenant_id == case.tenant_id, FiscalSeries.id == case.series_id))
    if change == "policy_disabled":
        policy.enabled = False
    elif change == "issuer_inactive":
        issuer.is_active = False
    elif change == "issuer_cuit":
        issuer.cuit = "20329642330"
    elif change == "issuer_legal_name":
        issuer.legal_name = "Changed synthetic fiscal identity"
    elif change == "issuer_tax_condition":
        issuer.tax_condition = "Changed reviewed tax condition"
    elif change == "issuer_capability":
        # Keep a valid product capability while revoking this service circuit.
        issuer.can_issue_service_receipt_c = False
        issuer.service_document_type = issuer.service_document_code = None
        issuer.can_issue_product_invoice_c = True
        issuer.product_document_type = "invoice_c"
        issuer.product_document_code = "011"
    elif change == "issuer_responsible":
        issuer.user.is_active = False
    elif change == "series_inactive":
        series.is_active = False
    elif change == "series_concept":
        series.concept = 1
    elif change == "series_authorization_mode":
        series.authorization_mode = "CAEA"
    else:
        series.credential_reference = "opaque://test/reconfigured-credential"
    db_session.commit()
    with pytest.raises(AppError) as error:
        _service(db_session, lab).issue(case.context, case.sale_id, operation.id)
    assert error.value.status_code == 409 and error.value.code == expected_code
    assert lab.runtime.ticket_calls == [] and lab.runtime.transport.calls == []
    saved = _row(db_session, case, operation)
    assert saved.number is None and saved.request_payload is None and saved.state == "prepared"
    assert _active_count(db_session, case) == 1


def test_numbered_unknown_reconciles_frozen_request_when_current_configuration_is_disabled(db_session, emission_case, laboratory):
    case, lab = emission_case, laboratory
    lab.runtime.transport.timeout_after_authorization = True
    operation = _prepare(db_session, lab, case)
    assert _service(db_session, lab).issue(case.context, case.sale_id, operation.id).status == "unknown"
    saved = _row(db_session, case, operation)
    frozen_request, frozen_hash, frozen_reference = saved.request_payload, saved.request_hash, saved.credential_reference
    policy = db_session.scalar(select(FiscalPolicy).where(FiscalPolicy.tenant_id == case.tenant_id))
    issuer = db_session.scalar(select(FiscalIssuer).where(FiscalIssuer.tenant_id == case.tenant_id, FiscalIssuer.id == case.issuer_id))
    series = db_session.scalar(select(FiscalSeries).where(FiscalSeries.tenant_id == case.tenant_id, FiscalSeries.id == case.series_id))
    policy.enabled = False
    issuer.is_active = False
    series.is_active = False
    series.credential_reference = None
    db_session.commit()
    lab.time.now += timedelta(seconds=121)
    recovered = _service(db_session, lab, owner="disabled-config-reconciler").reconcile(case.context, case.sale_id, operation.id)
    assert recovered.status == "authorized" and recovered.number == 1
    saved = _row(db_session, case, operation)
    assert saved.request_payload == frozen_request and saved.request_hash == frozen_hash
    assert lab.runtime.ticket_calls[-1][1] == frozen_reference
    assert lab.runtime.transport.authorization_calls == 1 and _document_count(db_session, case) == 1
    assert _active_count(db_session, case) == 1


def test_expired_number_attribute_cannot_bypass_request_identity_immutability(db_session, emission_case, laboratory):
    case, lab = emission_case, laboratory
    lab.runtime.transport.timeout_after_authorization = True
    operation = _prepare(db_session, lab, case)
    assert _service(db_session, lab).issue(case.context, case.sale_id, operation.id).status == "unknown"
    saved = _row(db_session, case, operation)
    number, request_hash = saved.number, saved.request_hash
    db_session.expire(saved, ["number", "request_payload", "request_hash"])
    saved.number = number + 1
    with pytest.raises(AppError) as error:
        db_session.flush()
    assert error.value.code == "arca_request_immutable"
    db_session.rollback()
    saved = _row(db_session, case, operation)
    assert saved.number == number and saved.request_hash == request_hash
    assert lab.runtime.transport.authorization_calls == 1


def test_sql_constraint_rejects_numbered_request_with_null_hash_inside_savepoint(db_session, emission_case, laboratory):
    case, lab = emission_case, laboratory
    operation = _prepare(db_session, lab, case)
    # An outer transaction must exist before SAVEPOINT on SQLite. Only this
    # synthetic database is used; no migration or application schema is touched.
    if not db_session.in_transaction():
        db_session.begin()
    connection = db_session.connection()
    if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
        # sqlite3 legacy mode does not BEGIN for SELECT; a Session transaction
        # alone would otherwise let SAVEPOINT become the physical outer one.
        connection.exec_driver_sql("BEGIN")
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.execute(update(ArcaEmissionIntent).where(
                ArcaEmissionIntent.tenant_id == case.tenant_id,
                ArcaEmissionIntent.id == operation.id,
            ).values(number=1, request_payload={"number": 1}, request_hash=None)
              .execution_options(synchronize_session=False))
    saved = _row(db_session, case, operation)
    assert saved.number is None and saved.request_payload is None and saved.request_hash is None
    assert saved.state == "prepared" and lab.runtime.transport.authorization_calls == 0

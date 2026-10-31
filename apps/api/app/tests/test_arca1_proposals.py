"""Fiscal intents reserve complete payments without changing commercial facts.

All fixtures are synthetic SQLite data. PostgreSQL lock races live separately
in test_arca1_postgresql.py; these tests do not claim concurrency coverage.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.errors import AppError
from app.models.fiscal_configuration import FiscalSeries
from app.models.fiscal_proposal import FiscalPaymentAllocation, FiscalProposal
from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.payment import PaymentMethod, SalePayment
from app.models.sale import Sale, SaleItem
from app.models.sale_fiscal import FiscalIssuer, SaleFiscalDocument, SaleFiscalDocumentFileVersion
from app.models.user import User
from app.schemas.fiscal_configuration import FiscalPolicyUpdate, FiscalSeriesCreate, FiscalSeriesUpdate
from app.schemas.fiscal_proposal import FiscalManualAllocation, FiscalProposalApprove, FiscalProposalGenerate, FiscalProposalUpdate
from app.schemas.payment import PaymentMethodUpdate
from app.services.fiscal_configuration import FiscalConfigurationService
from app.services.fiscal_proposal import FiscalProposalService
from app.services.payment import PaymentMethodService, SalePaymentService
from app.services.sale import SaleService
from app.tests.fiscal_test_support import seed_fiscal_case


def _record(db, model, case, record_id):
    return db.scalar(select(model).where(model.tenant_id == case.tenant_id, model.id == record_id))


def _allocations(db, case, *, active=False):
    query = select(FiscalPaymentAllocation).where(FiscalPaymentAllocation.tenant_id == case.tenant_id, FiscalPaymentAllocation.sale_id == case.sale_id)
    if active:
        query = query.where(FiscalPaymentAllocation.is_active.is_(True))
    return list(db.scalars(query))


def _draft(db, case, **changes):
    generated = FiscalProposalService(db).generate(case.context, case.sale_id, FiscalProposalGenerate(**changes))
    assert len(generated) == 1
    return generated[0]


def _approve(db, case, proposal, *, key=None, service=None):
    service = service or FiscalProposalService(db)
    return service.approve(case.context, case.sale_id, proposal.id, FiscalProposalApprove(content_hash=proposal.content_hash, confirm_fiscal_identity=True), key or f"approval-{uuid.uuid4()}")


def _extra_method(db, case, *, kind="bank_transfer", issuer_id=None):
    suffix = uuid.uuid4().hex
    method = PaymentMethod(tenant_id=case.tenant_id, label=f"Synthetic {kind} {suffix}", normalized_label=suffix, type=kind, suggested_fiscal_issuer_id=issuer_id, is_active=True)
    db.add(method)
    db.flush()
    return method


def _extra_payment(db, case, method, amount):
    payment = SalePayment(tenant_id=case.tenant_id, sale_id=case.sale_id, payment_method_id=method.id, payment_method_label_snapshot=method.label, payment_method_type_snapshot=method.type, amount_ars=Decimal(amount), received_at=datetime.now(UTC), is_active=True, created_by_user_id=case.context.user_id)
    db.add(payment)
    db.flush()
    return payment


def _second_issuer(db, case):
    suffix = uuid.uuid4().hex
    user = User(tenant_id=case.tenant_id, email=f"second-{suffix}@example.com", full_name="Second synthetic veterinarian", role="medico_veterinario", is_active=True)
    db.add(user)
    db.flush()
    issuer = FiscalIssuer(tenant_id=case.tenant_id, user_id=user.id, display_name="Second synthetic issuer", tax_id="30712345671", cuit="30712345671", legal_name="Second synthetic fiscal identity", tax_condition="monotributo", can_issue_service_receipt_c=True, service_document_type="receipt_c", service_document_code="015", is_active=True)
    db.add(issuer)
    db.flush()
    series = FiscalSeries(tenant_id=case.tenant_id, fiscal_issuer_id=issuer.id, cuit_snapshot=issuer.cuit, environment="homologation", point_of_sale=1, document_type="receipt_c", concept=2, authorization_mode="CAE", credential_reference="opaque://synthetic-second/credential", created_by_user_id=case.context.user_id, updated_by_user_id=case.context.user_id, is_active=True)
    db.add(series)
    db.flush()
    return issuer, series


def _inventory(db, case, *, category="food"):
    item = InventoryItem(tenant_id=case.tenant_id, internal_code=uuid.uuid4().hex[:12], name="Synthetic inventory", category=category, unit="unit", current_stock=Decimal("17.00"), minimum_stock=Decimal("0"), purchase_tax_rate_percentage=Decimal("0"), profit_margin_percentage=Decimal("0"), sale_tax_rate_percentage=Decimal("0"), is_active=True)
    db.add(item)
    db.flush()
    return item


def _manual_document(db, case, *, amount="100.00"):
    issuer = _record(db, FiscalIssuer, case, case.issuer_id)
    document = SaleFiscalDocument(tenant_id=case.tenant_id, sale_id=case.sale_id, fiscal_issuer_id=issuer.id, issuer_user_id_snapshot=issuer.user_id, issuer_name_snapshot="Preserved historical issuer", issuer_tax_id_snapshot="Preserved historical tax id", source="manual", authorization_status="manual", document_type="receipt_c", document_code="015", document_number=f"HIST-{uuid.uuid4()}", issue_date=date(2026, 10, 1), total_ars_snapshot=Decimal(amount), original_filename="synthetic-history.pdf", bucket_name="synthetic-local", storage_key="synthetic/manual.pdf", content_type="application/pdf", size_bytes=12, sha256="a" * 64, uploaded_by_user_id=case.context.user_id, uploaded_at=datetime.now(UTC), is_active=True)
    db.add(document)
    db.flush()
    version = SaleFiscalDocumentFileVersion(tenant_id=case.tenant_id, fiscal_document_id=document.id, original_filename="synthetic-earlier.pdf", bucket_name="synthetic-local", storage_key="synthetic/earlier.pdf", content_type="application/pdf", size_bytes=8, sha256="b" * 64, uploaded_at=datetime.now(UTC), replaced_at=datetime.now(UTC), replaced_by_user_id=case.context.user_id)
    db.add(version)
    db.commit()
    return document, version


def test_decimal_groups_two_real_issuers_and_cash_separately_without_commercial_side_effects(db_session):
    case = seed_fiscal_case(db_session, payment_amount="10.01")
    original_method = _record(db_session, PaymentMethod, case, case.method_id)
    additional = _extra_payment(db_session, case, original_method, "23.32")
    second_issuer, second_series = _second_issuer(db_session, case)
    second_method = _extra_method(db_session, case, issuer_id=second_issuer.id)
    second_payment = _extra_payment(db_session, case, second_method, "33.34")
    cash = _extra_payment(db_session, case, _extra_method(db_session, case, kind="cash", issuer_id=case.issuer_id), "33.33")
    stock = _inventory(db_session, case)
    db_session.commit()
    payments_before = [(row.id, row.amount_ars, row.is_active, row.payment_method_type_snapshot) for row in db_session.scalars(select(SalePayment).where(SalePayment.tenant_id == case.tenant_id, SalePayment.sale_id == case.sale_id).order_by(SalePayment.id))]
    service = FiscalProposalService(db_session)
    drafts = service.generate(case.context, case.sale_id, FiscalProposalGenerate())
    assert {row.fiscal_issuer_id: row.total_ars for row in drafts} == {case.issuer_id: Decimal("33.33"), second_issuer.id: Decimal("33.34")}
    assert {row.fiscal_series_id for row in drafts} == {case.series_id, second_series.id}
    assert {value for row in drafts for value in row.payment_ids} == {str(case.payment_id), str(additional.id), str(second_payment.id)}
    assert _allocations(db_session, case) == []
    review = service.review(case.context, case.sale_id)
    assert review.totals.active_payments_ars == Decimal("100.00")
    assert review.totals.proposed_ars == Decimal("66.67")
    assert review.totals.excluded_ars == Decimal("33.33")
    assert next(row for row in review.payments if row.payment_id == cash.id).status == "excluded"
    assert "exención" in next(row for row in review.payments if row.payment_id == cash.id).reason
    for proposal in drafts:
        approved = _approve(db_session, case, proposal)
        assert approved.total_ars == sum((row.amount_ars for row in approved.allocations), Decimal("0.00"))
    assert len(_allocations(db_session, case, active=True)) == 3
    assert sum((row.amount_ars for row in _allocations(db_session, case, active=True)), Decimal("0.00")) == Decimal("66.67")
    frozen_hashes = {proposal.id: proposal.content_hash for proposal in drafts}
    FiscalConfigurationService(db_session).update_policy(case.context, FiscalPolicyUpdate(payment_scope="all_payments", accounting_review_note="Incluir también efectivo tras revisión sintética"))
    cash_proposal = _draft(db_session, case)
    assert cash_proposal.payment_ids == [str(cash.id)]
    assert _approve(db_session, case, cash_proposal).total_ars == Decimal("33.33")
    assert sum((row.amount_ars for row in _allocations(db_session, case, active=True)), Decimal("0.00")) == Decimal("100.00")
    for proposal_id, original_hash in frozen_hashes.items():
        frozen = _record(db_session, FiscalProposal, case, proposal_id)
        assert frozen.content_hash == original_hash
        assert frozen.snapshot["policy"]["payment_scope"] == "electronic_only"
    sale = _record(db_session, Sale, case, case.sale_id)
    assert sale.status == "confirmed" and sale.total_ars == Decimal("100.00")
    assert sale.fiscal_status == "pending"
    assert _record(db_session, InventoryItem, case, stock.id).current_stock == Decimal("17.00")
    assert db_session.scalar(select(func.count(InventoryMovement.id)).where(InventoryMovement.tenant_id == case.tenant_id)) == 0
    assert db_session.scalar(select(func.count(SaleFiscalDocument.id)).where(SaleFiscalDocument.tenant_id == case.tenant_id)) == 0
    payments_after = [(row.id, row.amount_ars, row.is_active, row.payment_method_type_snapshot) for row in db_session.scalars(select(SalePayment).where(SalePayment.tenant_id == case.tenant_id, SalePayment.sale_id == case.sale_id).order_by(SalePayment.id))]
    assert payments_after == payments_before


def test_approval_api_replay_has_one_reservation_and_changed_content_conflicts(client, db_session):
    case = seed_fiscal_case(db_session)
    proposal = _draft(db_session, case)
    path = f"/api/v1/sales/{case.sale_id}/fiscal-proposals/{proposal.id}/approve"
    headers = {"X-User-Email": case.context.user_email, "Idempotency-Key": "exact-approval-intent"}
    payload = {"content_hash": proposal.content_hash, "confirm_fiscal_identity": True}
    first = client.post(path, headers=headers, json=payload)
    assert first.status_code == 200, first.text
    assert first.headers["Idempotency-Replayed"] == "false"
    retry = client.post(path, headers=headers, json=payload)
    assert retry.status_code == 200, retry.text
    assert retry.headers["Idempotency-Replayed"] == "true"
    assert retry.json()["data"]["id"] == first.json()["data"]["id"]
    assert len(_allocations(db_session, case, active=True)) == 1
    changed = client.post(path, headers=headers, json={**payload, "content_hash": "0" * 64})
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "fiscal_approval_idempotency_conflict"
    assert len(_allocations(db_session, case, active=True)) == 1


def test_two_overlapping_drafts_do_not_consume_until_approval_and_cannot_double_reserve(db_session):
    case = seed_fiscal_case(db_session)
    first = _draft(db_session, case, fiscal_description="Primera intención")
    second = _draft(db_session, case, fiscal_description="Segunda intención")
    assert first.id != second.id
    assert _allocations(db_session, case) == []
    assert _approve(db_session, case, first).status == "approved"
    with pytest.raises(AppError) as error:
        _approve(db_session, case, second)
    assert error.value.status_code == 409
    assert error.value.code == "fiscal_payment_reserved"
    assert len(_allocations(db_session, case, active=True)) == 1


def test_approved_content_is_frozen_through_dto_and_orm_and_cannot_return_to_draft(client, db_session):
    case = seed_fiscal_case(db_session)
    approved = _approve(db_session, case, _draft(db_session, case))
    path = f"/api/v1/sales/{case.sale_id}/fiscal-proposals/{approved.id}"
    response = client.patch(path, headers={"X-User-Email": case.context.user_email}, json={"payment_ids": [str(case.payment_id)], "fiscal_series_id": str(case.series_id), "fiscal_description": "Sustitución prohibida"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "fiscal_proposal_frozen"
    for changes in ({"fiscal_description": "Mutación directa"}, {"status": "draft"}):
        record = _record(db_session, FiscalProposal, case, approved.id)
        for name, value in changes.items():
            setattr(record, name, value)
        with pytest.raises(AppError) as error:
            db_session.flush()
        assert error.value.code == "fiscal_proposal_frozen"
        db_session.rollback()
    assert _record(db_session, FiscalProposal, case, approved.id).content_hash == approved.content_hash


def test_cancellation_releases_with_audit_and_requires_a_new_approval_intention(db_session):
    case = seed_fiscal_case(db_session)
    first = _approve(db_session, case, _draft(db_session, case), key="first-intent")
    service = FiscalProposalService(db_session)
    cancelled = service.cancel(case.context, case.sale_id, first.id, reason="Corregir atribución revisada")
    assert cancelled.status == "cancelled"
    released = _allocations(db_session, case)[0]
    assert released.is_active is False
    assert released.released_at and released.released_by_user_id == case.context.user_id
    assert released.release_reason == "Corregir atribución revisada"
    record = _record(db_session, FiscalProposal, case, first.id)
    assert [entry["action"] for entry in record.audit_log] == ["created", "approved", "cancelled"]
    assert record.approved_at and record.cancelled_at and record.idempotency_key == "first-intent"
    next_draft = _draft(db_session, case)
    assert next_draft.id != first.id
    with pytest.raises(AppError) as error:
        _approve(db_session, case, next_draft, key="first-intent")
    assert error.value.code == "fiscal_approval_idempotency_conflict"
    second = _approve(db_session, case, next_draft, key="second-intent")
    assert second.status == "approved"
    assert len(_allocations(db_session, case)) == 2
    assert len(_allocations(db_session, case, active=True)) == 1


def test_reserved_payment_and_sale_operations_fail_recoverably_until_cancelled(db_session):
    case = seed_fiscal_case(db_session)
    proposal = _approve(db_session, case, _draft(db_session, case))
    with pytest.raises(AppError) as payment_error:
        SalePaymentService(db_session).void(case.tenant_id, case.payment_id, reason="Corrección", user_id=case.context.user_id)
    assert payment_error.value.code == "fiscal_payment_reserved"
    assert "Cancela" in payment_error.value.message
    with pytest.raises(AppError) as sale_error:
        SaleService(db_session).reverse(case.tenant_id, case.sale_id, reason="Corrección", reversed_by_user_id=case.context.user_id)
    assert sale_error.value.code == "fiscal_sale_reserved"
    assert _record(db_session, SalePayment, case, case.payment_id).is_active is True
    assert _record(db_session, Sale, case, case.sale_id).status == "confirmed"
    FiscalProposalService(db_session).cancel(case.context, case.sale_id, proposal.id, reason="Liberación para corregir venta")
    voided = SalePaymentService(db_session).void(case.tenant_id, case.payment_id, reason="Corrección autorizada", user_id=case.context.user_id)
    assert voided.is_active is False
    assert SaleService(db_session).reverse(case.tenant_id, case.sale_id, reason="Corrección autorizada", reversed_by_user_id=case.context.user_id).status == "reversed"
    assert _allocations(db_session, case, active=True) == []


@pytest.mark.parametrize("changed_source", ["payment_voided", "sale_reversed", "series_changed", "mapping_changed", "policy_changed"])
def test_approval_rejects_stale_sources_before_reserving_any_payment(db_session, changed_source):
    case = seed_fiscal_case(db_session)
    proposal = _draft(db_session, case)
    if changed_source == "payment_voided":
        SalePaymentService(db_session).void(case.tenant_id, case.payment_id, reason="Cambio sintético", user_id=case.context.user_id)
    elif changed_source == "sale_reversed":
        SaleService(db_session).reverse(case.tenant_id, case.sale_id, reason="Cambio sintético", reversed_by_user_id=case.context.user_id)
    elif changed_source == "series_changed":
        FiscalConfigurationService(db_session).update_series(case.context, case.series_id, FiscalSeriesUpdate(point_of_sale=2))
    elif changed_source == "mapping_changed":
        PaymentMethodService(db_session).update(case.tenant_id, case.method_id, PaymentMethodUpdate(suggested_fiscal_issuer_id=None), user_id=case.context.user_id)
    else:
        FiscalConfigurationService(db_session).update_policy(case.context, FiscalPolicyUpdate(payment_scope="all_payments"))
    review = FiscalProposalService(db_session).review(case.context, case.sale_id)
    assert review.proposals[0].is_stale is True
    with pytest.raises(AppError) as error:
        _approve(db_session, case, proposal)
    assert error.value.status_code == 409
    assert error.value.code == "fiscal_proposal_stale"
    assert _allocations(db_session, case, active=True) == []


def test_manual_history_blocks_new_approval_until_explicit_idempotent_allocation(db_session):
    case = seed_fiscal_case(db_session)
    document, version = _manual_document(db_session, case)
    proposal = _draft(db_session, case)
    assert any(block.code == "fiscal_manual_allocation_unknown" for block in proposal.blockers)
    with pytest.raises(AppError) as error:
        _approve(db_session, case, proposal)
    assert error.value.code == "fiscal_manual_allocation_unknown"
    service = FiscalProposalService(db_session)
    payload = FiscalManualAllocation(payment_ids=[case.payment_id], confirm_fiscal_identity=True)
    first = service.regularize_manual(case.context, case.sale_id, document.id, payload, "manual-intent")
    retry = service.regularize_manual(case.context, case.sale_id, document.id, payload, "manual-intent")
    assert first.totals.committed_ars == retry.totals.committed_ars == Decimal("100.00")
    with pytest.raises(AppError) as conflict:
        service.regularize_manual(case.context, case.sale_id, document.id, FiscalManualAllocation(payment_ids=[uuid.uuid4()], confirm_fiscal_identity=True), "manual-intent")
    assert conflict.value.code == "fiscal_allocation_idempotency_conflict"
    assert not any(block.code == "fiscal_manual_allocation_unknown" for block in retry.eligibility.blockers)
    rows = _allocations(db_session, case, active=True)
    assert len(rows) == 1 and rows[0].fiscal_document_id == document.id and rows[0].proposal_id is None
    assert rows[0].amount_ars == Decimal("100.00")
    preserved = _record(db_session, SaleFiscalDocument, case, document.id)
    assert preserved.issuer_name_snapshot == "Preserved historical issuer"
    assert preserved.issuer_tax_id_snapshot == "Preserved historical tax id"
    assert preserved.storage_key == "synthetic/manual.pdf"
    assert preserved.allocation_reviewed_by_user_id == case.context.user_id
    assert preserved.allocation_reviewed_at and preserved.allocation_idempotency_key == "manual-intent"
    assert _record(db_session, SaleFiscalDocumentFileVersion, case, version.id).storage_key == "synthetic/earlier.pdf"
    # Regularization consumes the payment: it does not pretend the new proposal
    # is approved or that the same payment became free for another document.
    with pytest.raises(AppError) as error:
        _approve(db_session, case, proposal)
    assert error.value.code == "fiscal_payment_reserved"


def test_manual_allocation_requires_an_exact_sum_of_whole_payments(db_session):
    case = seed_fiscal_case(db_session, payment_amount="60.00")
    document, _version = _manual_document(db_session, case)
    payload = FiscalManualAllocation(payment_ids=[case.payment_id], confirm_fiscal_identity=True)
    with pytest.raises(AppError) as error:
        FiscalProposalService(db_session).regularize_manual(case.context, case.sale_id, document.id, payload, "incomplete-manual-selection")
    assert error.value.status_code == 409
    assert error.value.code == "fiscal_manual_total_mismatch"
    assert _allocations(db_session, case) == []
    assert _record(db_session, SaleFiscalDocument, case, document.id).allocation_reviewed_at is None


def test_incompatible_series_are_never_picked_arbitrarily_and_explicit_selection_is_preserved(db_session):
    case = seed_fiscal_case(db_session)
    other_series = FiscalConfigurationService(db_session).create_series(case.context, FiscalSeriesCreate(fiscal_issuer_id=case.issuer_id, environment="homologation", point_of_sale=2, document_type="receipt_c", concept=2, credential_reference="opaque://second-pos"))
    service = FiscalProposalService(db_session)
    assert service.generate(case.context, case.sale_id, FiscalProposalGenerate()) == []
    assert service.review(case.context, case.sale_id).payments[0].status == "pending"
    proposal = _draft(db_session, case, payment_ids=[case.payment_id], fiscal_series_id=other_series.id)
    assert proposal.fiscal_series_id == other_series.id
    assert proposal.snapshot["series"]["point_of_sale"] == 2


def test_partial_mixed_composition_is_blocked_without_automatic_proration(db_session):
    case = seed_fiscal_case(db_session, payment_amount="50.00")
    sale = _record(db_session, Sale, case, case.sale_id)
    sale.items[0].unit_price_ars = sale.items[0].line_subtotal_ars = sale.items[0].line_total_ars = Decimal("60.00")
    inventory = _inventory(db_session, case)
    sale.items.append(SaleItem(tenant_id=case.tenant_id, line_type="product", inventory_item_id=inventory.id, description_snapshot="Synthetic food", unit_snapshot="unit", quantity=Decimal("1"), unit_price_ars=Decimal("40.00"), discount_percentage=Decimal("0"), line_subtotal_ars=Decimal("40.00"), line_discount_ars=Decimal("0"), line_total_ars=Decimal("40.00"), line_order=2))
    issuer = _record(db_session, FiscalIssuer, case, case.issuer_id)
    issuer.can_issue_product_invoice_c = True
    issuer.product_document_type = "receipt_c"
    issuer.product_document_code = "015"
    _record(db_session, FiscalSeries, case, case.series_id).concept = 3
    db_session.commit()
    proposal = _draft(db_session, case)
    assert proposal.total_ars == Decimal("50.00")
    assert any(block.code == "fiscal_attribution_requires_split" for block in proposal.blockers)
    with pytest.raises(AppError) as error:
        _approve(db_session, case, proposal)
    assert error.value.code == "fiscal_attribution_requires_split"
    assert _allocations(db_session, case) == []
    assert _record(db_session, SalePayment, case, case.payment_id).amount_ars == Decimal("50.00")


def test_multiple_service_lines_require_explicit_partial_description_review(db_session):
    case = seed_fiscal_case(db_session, payment_amount="40.00")
    sale = _record(db_session, Sale, case, case.sale_id)
    sale.items[0].unit_price_ars = sale.items[0].line_subtotal_ars = sale.items[0].line_total_ars = Decimal("40.00")
    sale.items.append(SaleItem(tenant_id=case.tenant_id, line_type="service", description_snapshot="Second synthetic service", unit_snapshot="service", quantity=Decimal("1"), unit_price_ars=Decimal("60.00"), discount_percentage=Decimal("0"), line_subtotal_ars=Decimal("60.00"), line_discount_ars=Decimal("0"), line_total_ars=Decimal("60.00"), line_order=2))
    db_session.commit()
    proposal = _draft(db_session, case)
    assert any(block.code == "fiscal_attribution_review_required" for block in proposal.blockers)
    with pytest.raises(AppError) as error:
        _approve(db_session, case, proposal)
    assert error.value.code == "fiscal_attribution_review_required"
    reviewed = FiscalProposalService(db_session).update(case.context, case.sale_id, proposal.id, FiscalProposalUpdate(payment_ids=[case.payment_id], fiscal_series_id=case.series_id, fiscal_description="Atribución revisada: primer servicio sintético por ARS40"))
    assert not any(block.code == "fiscal_attribution_review_required" for block in reviewed.blockers)
    assert _approve(db_session, case, reviewed).total_ars == Decimal("40.00")


def test_medication_keeps_service_fiscal_classification_and_stock_is_untouched(db_session):
    case = seed_fiscal_case(db_session)
    medication = _inventory(db_session, case, category="medication")
    sale = _record(db_session, Sale, case, case.sale_id)
    sale.items[0].line_type = "product"
    sale.items[0].inventory_item_id = medication.id
    db_session.commit()
    proposal = _draft(db_session, case)
    assert proposal.concept == 2
    assert proposal.snapshot["sale"]["lines"][0]["fiscal_line_type"] == "service"
    assert _approve(db_session, case, proposal).status == "approved"
    assert _record(db_session, InventoryItem, case, medication.id).current_stock == Decimal("17.00")
    assert db_session.scalar(select(func.count(InventoryMovement.id)).where(InventoryMovement.tenant_id == case.tenant_id)) == 0


def test_other_is_pending_without_electronic_inference_and_all_payments_can_include_it(db_session):
    case = seed_fiscal_case(db_session, payment_type="other")
    service = FiscalProposalService(db_session)
    review = service.review(case.context, case.sale_id)
    assert review.payments[0].status == "pending"
    assert "other" in review.payments[0].reason
    assert service.generate(case.context, case.sale_id, FiscalProposalGenerate()) == []
    FiscalConfigurationService(db_session).update_policy(case.context, FiscalPolicyUpdate(payment_scope="all_payments"))
    proposal = _draft(db_session, case)
    assert _approve(db_session, case, proposal).total_ars == Decimal("100.00")


def test_usd_sale_has_a_clear_incompatibility_without_conversion_or_reservation(db_session):
    case = seed_fiscal_case(db_session, currency="USD")
    review = FiscalProposalService(db_session).review(case.context, case.sale_id)
    assert review.eligibility.eligible is False
    assert any(block.code == "fiscal_currency_incompatible" and "USD" in block.message for block in review.eligibility.blockers)
    with pytest.raises(AppError) as error:
        _draft(db_session, case)
    assert error.value.code == "fiscal_currency_incompatible"
    assert _allocations(db_session, case) == []
    assert _record(db_session, Sale, case, case.sale_id).currency == "USD"
    assert _record(db_session, SalePayment, case, case.payment_id).amount_ars == Decimal("100.00")

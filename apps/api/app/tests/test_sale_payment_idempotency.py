import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from decimal import Decimal
from threading import Barrier, local

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.models.payment import PaymentMethod, SalePayment
from app.models.sale import Sale
from app.models.tenant import Tenant
from app.repositories.payment import SalePaymentRepository
from app.schemas.payment import SalePaymentCreate
from app.services.payment import SalePaymentService, payment_request_hash
from app.tests.test_sale_payments import _headers, _method, _sale


def _payload(method, **overrides):
    return {
        "payment_method_id": method["id"], "amount_ars": "40.00",
        "received_at": "2026-10-01T12:00:00Z", "reference": "REF-1", "notes": "Cobro",
        **overrides,
    }


def _post(client, tenant, sale, payload, key="intent-A"):
    headers = _headers(tenant)
    if key is not None:
        headers["Idempotency-Key"] = key
    return client.post(f"/api/v1/sales/{sale['id']}/payments", headers=headers, json=payload)


def _count(db, tenant):
    return db.scalar(select(func.count(SalePayment.id)).where(SalePayment.tenant_id == tenant.id))


def test_identical_replay_recovers_committed_payment_and_current_summary(client, db_session, tenant):
    sale, method = _sale(client, tenant), _method(client, tenant)
    payload = _payload(method)
    first = _post(client, tenant, sale, payload)
    assert first.status_code == 201, first.text
    assert first.headers["Idempotency-Replayed"] == "false"
    # Simulate losing the first response and constructing another service/request.
    replay = _post(client, tenant, sale, payload)
    assert replay.status_code == 200, replay.text
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json()["data"] == first.json()["data"]
    assert replay.json()["meta"] == {
        "paid_total_ars": "40.00", "balance_due_ars": "60.00",
        "payment_status": "partial", "payment_requires_attention": False,
    }
    assert _count(db_session, tenant) == 1
    stored = db_session.scalar(select(SalePayment).where(SalePayment.tenant_id == tenant.id))
    assert stored.idempotency_key == "intent-A" and len(stored.idempotency_request_hash) == 64
    assert "idempotency_key" not in first.json()["data"]
    assert "idempotency_request_hash" not in first.json()["data"]


@pytest.mark.parametrize("mutation", [
    {"amount_ars": "41.00"}, {"reference": "REF-2"}, {"notes": "Otro cobro"},
    {"received_at": "2026-10-01T12:00:01Z"},
])
def test_key_reuse_with_changed_payload_conflicts_without_mutation(client, db_session, tenant, mutation):
    sale, method = _sale(client, tenant), _method(client, tenant)
    payload = _payload(method)
    first = _post(client, tenant, sale, payload)
    assert first.status_code == 201
    conflict = _post(client, tenant, sale, {**payload, **mutation})
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "sale_payment_idempotency_conflict"
    assert _count(db_session, tenant) == 1
    assert _post(client, tenant, sale, payload).json()["data"] == first.json()["data"]


def test_key_reuse_with_other_method_or_sale_conflicts(client, db_session, tenant):
    sale, other_sale = _sale(client, tenant), _sale(client, tenant)
    method, other_method = _method(client, tenant), _method(client, tenant, label="Transferencia", type="bank_transfer")
    payload = _payload(method)
    assert _post(client, tenant, sale, payload).status_code == 201
    for target, changed in ((sale, {**payload, "payment_method_id": other_method["id"]}), (other_sale, payload)):
        response = _post(client, tenant, target, changed)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "sale_payment_idempotency_conflict"
    assert _count(db_session, tenant) == 1


def test_same_key_is_independent_between_tenants_and_does_not_reveal_foreign_payment(client, db_session, tenant, other_tenant):
    foreign_sale, foreign_method = _sale(client, other_tenant), _method(client, other_tenant)
    foreign = _post(client, other_tenant, foreign_sale, _payload(foreign_method))
    assert foreign.status_code == 201
    # Matching key is not a global lookup: the local tenant cannot retrieve it.
    assert _post(client, tenant, foreign_sale, _payload(foreign_method)).status_code == 404
    local_sale, local_method = _sale(client, tenant), _method(client, tenant)
    local_payment = _post(client, tenant, local_sale, _payload(local_method))
    assert local_payment.status_code == 201
    assert local_payment.json()["data"]["id"] != foreign.json()["data"]["id"]
    assert _count(db_session, tenant) == _count(db_session, other_tenant) == 1
    replay = _post(client, tenant, local_sale, _payload(local_method))
    assert replay.json()["data"]["id"] == local_payment.json()["data"]["id"]


def test_requests_without_key_preserve_legacy_contract_and_behavior(client, db_session, tenant):
    sale, method = _sale(client, tenant), _method(client, tenant)
    payload = _payload(method, amount_ars="20.00")
    first, second = (_post(client, tenant, sale, payload, key=None) for _ in range(2))
    assert first.status_code == second.status_code == 201
    assert first.json()["meta"] == second.json()["meta"] == {}
    assert first.json()["data"]["id"] != second.json()["data"]["id"]
    assert "Idempotency-Replayed" not in first.headers
    assert _count(db_session, tenant) == 2
    assert all(payment.idempotency_key is None and payment.idempotency_request_hash is None for payment in db_session.scalars(select(SalePayment).where(SalePayment.tenant_id == tenant.id)))


@pytest.mark.parametrize("key", ["", " ", "\t", "a" * 129, "two words"])
def test_invalid_key_is_rejected_before_writing(client, db_session, tenant, key):
    sale, method = _sale(client, tenant), _method(client, tenant)
    response = _post(client, tenant, sale, _payload(method), key=key)
    assert response.status_code == 422, response.text
    assert _count(db_session, tenant) == 0


def test_key_trims_outer_whitespace_but_is_case_sensitive(client, db_session, tenant):
    sale, method = _sale(client, tenant), _method(client, tenant)
    payload = _payload(method, amount_ars="20.00")
    first = _post(client, tenant, sale, payload, key=" intent-A ")
    replay = _post(client, tenant, sale, payload, key="intent-A")
    different = _post(client, tenant, sale, payload, key="intent-a")
    assert first.status_code == different.status_code == 201
    assert replay.status_code == 200 and replay.json()["data"]["id"] == first.json()["data"]["id"]
    assert _count(db_session, tenant) == 2


def test_semantically_identical_decimal_time_and_optional_text_replay(client, tenant):
    sale, method = _sale(client, tenant), _method(client, tenant)
    payload = _payload(method, amount_ars="40", reference="  REF-1  ", notes=" ")
    first = _post(client, tenant, sale, payload)
    changed_spelling = {**payload, "amount_ars": "4e1", "received_at": "2026-10-01T09:00:00-03:00", "reference": "REF-1"}
    del changed_spelling["notes"]
    replay = _post(client, tenant, sale, changed_spelling)
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"] == first.json()["data"]


@pytest.mark.parametrize("received_at", ["omitted", None])
def test_received_at_remains_required_and_no_default_is_generated(client, tenant, received_at):
    sale, method = _sale(client, tenant), _method(client, tenant)
    payload = _payload(method, received_at=received_at)
    if received_at == "omitted":
        del payload["received_at"]
    assert _post(client, tenant, sale, payload).status_code == 422


def test_replay_after_other_payments_and_inactive_method_does_not_revalidate_balance(client, db_session, tenant):
    sale, method = _sale(client, tenant), _method(client, tenant)
    payload = _payload(method, amount_ars="70.00")
    first = _post(client, tenant, sale, payload)
    assert first.status_code == 201
    assert _post(client, tenant, sale, _payload(method, amount_ars="30.00"), key="intent-B").status_code == 201
    assert client.patch(f"/api/v1/payment-methods/{method['id']}", headers=_headers(tenant), json={"label": "Renombrado", "is_active": False}).status_code == 200
    replay = _post(client, tenant, sale, payload)
    assert replay.status_code == 200
    assert replay.json()["data"] == first.json()["data"]
    assert replay.json()["meta"]["paid_total_ars"] == "100.00"
    assert replay.json()["meta"]["balance_due_ars"] == "0.00"
    assert replay.json()["meta"]["payment_status"] == "paid"
    assert _count(db_session, tenant) == 2


def test_voided_payment_replay_never_reactivates_and_new_key_can_pay(client, db_session, tenant):
    sale, method = _sale(client, tenant), _method(client, tenant)
    payload = _payload(method)
    first = _post(client, tenant, sale, payload).json()["data"]
    voided = client.post(f"/api/v1/sale-payments/{first['id']}/void", headers=_headers(tenant), json={"reason": "Corrección"})
    assert voided.status_code == 200
    replay = _post(client, tenant, sale, payload)
    assert replay.status_code == 200
    assert replay.json()["data"] == voided.json()["data"]
    assert replay.json()["data"]["is_active"] is False
    assert replay.json()["meta"]["paid_total_ars"] == "0.00"
    assert _count(db_session, tenant) == 1
    assert _post(client, tenant, sale, payload, key="intent-B").status_code == 201


def test_reversed_sale_replay_preserves_original_payment_and_attention_summary(client, db_session, tenant):
    sale, method = _sale(client, tenant), _method(client, tenant)
    payload = _payload(method)
    first = _post(client, tenant, sale, payload).json()["data"]
    assert client.post(f"/api/v1/sales/{sale['id']}/reverse", headers=_headers(tenant), json={"reason": "Corrección"}).status_code == 200
    replay = _post(client, tenant, sale, payload)
    assert replay.status_code == 200 and replay.json()["data"] == first
    assert replay.json()["meta"]["payment_status"] == "requires_attention"
    assert _post(client, tenant, sale, payload, key="new-intent").json()["error"]["code"] == "sale_payment_not_allowed"
    assert _count(db_session, tenant) == 1


def test_failed_business_validation_does_not_reserve_key(client, db_session, tenant, other_tenant):
    sale = _sale(client, tenant)
    method, foreign = _method(client, tenant), _method(client, other_tenant)
    assert _post(client, tenant, sale, _payload(method, amount_ars="101.00")).json()["error"]["code"] == "sale_payment_exceeds_balance"
    assert _post(client, tenant, sale, _payload(foreign)).status_code == 404
    assert _count(db_session, tenant) == 0
    assert _post(client, tenant, sale, _payload(method)).status_code == 201


def test_unrelated_integrity_error_is_not_mistaken_for_replay(client, db_session, tenant, monkeypatch):
    sale, method = _sale(client, tenant), _method(client, tenant)
    def fail_insert(*args):
        raise IntegrityError("insert", {}, RuntimeError("unrelated failure"))
    monkeypatch.setattr(SalePaymentRepository, "create", fail_insert)
    with pytest.raises(IntegrityError):
        _post(client, tenant, sale, _payload(method))
    assert _count(db_session, tenant) == 0


def test_fingerprint_is_sha256_and_distinguishes_naive_time():
    sale_id, method_id = uuid.uuid4(), uuid.uuid4()
    first = SalePaymentCreate.model_validate(_payload({"id": str(method_id)}))
    same = first.model_copy(update={"amount_ars": Decimal("40.0")})
    assert payment_request_hash(sale_id, first) == payment_request_hash(sale_id, same)
    assert len(payment_request_hash(sale_id, first)) == 64
    naive = first.model_copy(update={"received_at": first.received_at.replace(tzinfo=None)})
    assert payment_request_hash(sale_id, first) != payment_request_hash(sale_id, naive)


@pytest.mark.parametrize("scenario", ["identical", "changed_amount", "other_sale"])
def test_postgresql_same_key_races_create_only_one_payment(postgres_test_session_factory, monkeypatch, scenario):
    session_factory = postgres_test_session_factory
    db = session_factory()
    tenant = Tenant(id=uuid.uuid4(), name="P.4 concurrency")
    db.add(tenant)
    db.flush()
    method = PaymentMethod(tenant_id=tenant.id, label="Cash", normalized_label="cash", type="cash", is_active=True, sort_order=0)
    sales = [Sale(tenant_id=tenant.id, sale_date=date(2026, 10, 1), currency="ARS", subtotal_ars=Decimal("100"), discount_total_ars=Decimal("0"), total_ars=Decimal("100"), status="confirmed") for _ in range(2)]
    db.add_all([method, *sales])
    db.commit()
    tenant_id, method_id, sale_ids = tenant.id, method.id, [sale.id for sale in sales]
    db.close()
    barrier = Barrier(2)
    calls = local()
    original_lookup = SalePaymentRepository.get_by_idempotency_key
    def synchronized_lookup(repository, lookup_tenant, key):
        result = original_lookup(repository, lookup_tenant, key)
        calls.count = getattr(calls, "count", 0) + 1
        # Same sale: both first lookups see absence before contending for its lock.
        # Different sales: force both second lookups to see absence, testing unique recovery.
        if calls.count == (2 if scenario == "other_sale" else 1):
            assert result is None
            barrier.wait(timeout=10)
        return result
    def submit(index):
        session = session_factory()
        service = SalePaymentService(session)
        try:
            payload = SalePaymentCreate(payment_method_id=method_id, amount_ars=Decimal("45" if index and scenario == "changed_amount" else "40"), received_at=datetime(2026, 10, 1, 12, tzinfo=UTC))
            sale_id = sale_ids[index] if scenario == "other_sale" else sale_ids[0]
            payment = service.create(tenant_id, sale_id, payload, user_id=None, idempotency_key="race-key")
            return "replayed" if service.idempotency_replayed else "created", payment.id
        except AppError as exc:
            return exc.code, None
        finally:
            session.close()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(SalePaymentRepository, "get_by_idempotency_key", synchronized_lookup)
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(submit, range(2)))
        db = session_factory()
        payments = list(db.scalars(select(SalePayment).where(SalePayment.tenant_id == tenant_id)))
        assert len(payments) == 1
        assert payments[0].amount_ars in (Decimal("40.00"), Decimal("45.00"))
        statuses = sorted(result[0] for result in results)
        if scenario == "identical":
            assert statuses == ["created", "replayed"]
            assert results[0][1] == results[1][1] == payments[0].id
        else:
            assert statuses == ["created", "sale_payment_idempotency_conflict"]
        assert sum((payment.amount_ars for payment in payments), Decimal("0")) <= Decimal("100")
    finally:
        db.close()
        db = session_factory()
        for model in (SalePayment, Sale, PaymentMethod, Tenant):
            column = model.id if model is Tenant else model.tenant_id
            db.execute(delete(model).where(column == tenant_id))
        db.commit()
        db.close()

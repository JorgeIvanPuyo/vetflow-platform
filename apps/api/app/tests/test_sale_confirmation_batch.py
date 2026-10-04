"""P.8: split payments, durable intent, rollback and real PostgreSQL races."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from threading import Barrier, local

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.db.session import get_db
from app.models.inventory_item import InventoryItem
from app.models.payment import PaymentMethod, SalePayment, SalePaymentBatch
from app.models.user import User
from app.repositories.payment import SalePaymentBatchRepository
from app.schemas.payment import SalePaymentCreate
from app.schemas.sale import SaleConfirm, SaleDetailRead
from app.services.payment import SalePaymentService
from app.services.sale import SaleService
from app.services.sale_confirmation import SaleConfirmationService
from app.tests.test_sale_confirmation_payment import _assert_rollback
from app.tests.test_sale_transaction_composition import (
    _seed, _state, postgres_transaction_factory, transaction_factory,
)


def _seed_batch(factory, *, tenant_id=None, total=100):
    case = _seed(factory, tenant_id=tenant_id)
    with factory.begin() as db:
        sale = SaleService(db).get(case.tenant_id, case.sale_id)
        sale.subtotal_ars = sale.total_ars = Decimal(total)
        sale.items[0].unit_price_ars = Decimal(total) / 2
        sale.items[0].line_subtotal_ars = sale.items[0].line_total_ars = Decimal(total)
    return case


@pytest.fixture()
def case(db_session):
    return _seed_batch(sessionmaker(bind=db_session.get_bind(), autoflush=False))


def _rows(case, amounts=(20, 30, 50)):
    return [{"payment_method_id": str(case.method_id), "amount_ars": str(amount),
             "reference": f"REF-{index}", "notes": None}
            for index, amount in enumerate(amounts)]


def _post(client, case, rows, *, key="batch", tenant_id=None):
    headers = {"X-Tenant-Id": str(tenant_id or case.tenant_id)}
    if key is not None:
        headers["Idempotency-Key"] = key
    return client.post(f"/api/v1/sales/{case.sale_id}/confirm", headers=headers,
                       json={"confirm": True, "initial_payments": rows})


def _batches(db, case):
    return list(db.scalars(select(SalePaymentBatch).where(
        SalePaymentBatch.tenant_id == case.tenant_id, SalePaymentBatch.sale_id == case.sale_id)))


def _rollback(db, case, *, total=100, stock=10):
    _assert_rollback(db, case, total=total, stock=stock)
    assert _batches(db, case) == []


@pytest.mark.parametrize("amounts,status,balance", [((20, 30, 50), "paid", 0), ((20, 30), "partial", 50)])
def test_batch_full_partial_repeated_method_and_persistent_membership(client, db_session, case, amounts, status, balance):
    before = datetime.now(UTC)
    response = _post(client, case, _rows(case, amounts))
    after = datetime.now(UTC)
    assert response.status_code == 200, response.text
    assert response.headers["Idempotency-Replayed"] == "false"
    detail = response.json()["data"]
    assert response.json()["meta"] == {}
    assert detail["payment_status"] == status
    assert Decimal(detail["paid_total_ars"]) == sum(amounts)
    assert Decimal(detail["balance_due_ars"]) == balance
    assert len({p["id"] for p in detail["payments"]}) == len(amounts)
    for payment in detail["payments"]:
        assert payment["payment_method_label_snapshot"] == "Cash"
        assert before <= datetime.fromisoformat(payment["received_at"]).replace(tzinfo=UTC) <= after
    batch, = _batches(db_session, case)
    assert batch.idempotency_key == "batch" and len(batch.request_hash) == 64
    members = SalePaymentBatchRepository(db_session).list_payments(case.tenant_id, batch.id)
    assert {str(p.id) for p in members} == {p["id"] for p in detail["payments"]}
    assert all(p.idempotency_key is None and p.idempotency_request_hash is None for p in members)
    assert _state(db_session, case) == ("confirmed", 8, 1, len(amounts), balance)


def test_three_different_methods_and_snapshots(client, db_session, case):
    methods = [PaymentMethod(tenant_id=case.tenant_id, label=label, normalized_label=label.lower(), type=kind)
               for label, kind in [("QR Juliana", "digital_wallet"), ("Transferencia Lida", "bank_transfer")]]
    db_session.add_all(methods)
    db_session.commit()
    rows = _rows(case)
    rows[1]["payment_method_id"], rows[2]["payment_method_id"] = map(lambda p: str(p.id), methods)
    response = _post(client, case, rows)
    assert response.status_code == 200, response.text
    assert {p["payment_method_label_snapshot"] for p in response.json()["data"]["payments"]} == {"Cash", "QR Juliana", "Transferencia Lida"}


@pytest.mark.parametrize("invalid", [[], [{}], None, "not-a-list", [{}] * 21])
def test_batch_cardinality_and_null_rejected(client, db_session, case, invalid):
    assert _post(client, case, invalid).status_code == 422
    _rollback(db_session, case)


@pytest.mark.parametrize("single", [None, "valid"])
def test_both_keys_rejected_even_null(client, db_session, case, single):
    response = client.post(f"/api/v1/sales/{case.sale_id}/confirm", headers={"X-Tenant-Id": str(case.tenant_id)},
                           json={"confirm": True, "initial_payment": _rows(case)[0] if single else None,
                                 "initial_payments": _rows(case)})
    assert response.status_code == 422 and "no ambos" in response.text
    _rollback(db_session, case)


@pytest.mark.parametrize("amount", ["0", "-1", "0.001", "100000000000000.00", "NaN", "Infinity"])
def test_each_row_keeps_p2_limits(client, db_session, case, amount):
    rows = _rows(case)
    rows[1]["amount_ars"] = amount
    assert _post(client, case, rows).status_code == 422
    _rollback(db_session, case)


@pytest.mark.parametrize("key", [None, "", "has space", "x" * 129, b"\xe1"])
def test_batch_requires_valid_idempotency_key(client, db_session, case, key):
    assert _post(client, case, _rows(case), key=key).status_code == 422
    _rollback(db_session, case)


def test_total_checked_before_any_writes(client, db_session, case, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("Excess total must fail before writes")
    monkeypatch.setattr(SalePaymentBatchRepository, "create", unexpected)
    response = _post(client, case, _rows(case, (60, 50)))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "sale_payment_batch_exceeds_total"
    _rollback(db_session, case)


@pytest.mark.parametrize("bad_method", ["inactive", "foreign", "missing"])
def test_invalid_second_method_rolls_back_prior_payment(client, db_session, case, other_tenant, bad_method):
    if bad_method == "missing":
        method_id = uuid.uuid4()
    else:
        method = PaymentMethod(tenant_id=other_tenant.id if bad_method == "foreign" else case.tenant_id,
                               label="Bad", normalized_label="bad", type="cash", is_active=bad_method != "inactive")
        db_session.add(method)
        db_session.commit()
        method_id = method.id
    rows = _rows(case)
    rows[1]["payment_method_id"] = str(method_id)
    response = _post(client, case, rows)
    assert response.status_code == (409 if bad_method == "inactive" else 404)
    assert response.json()["error"]["code"] == ("payment_method_inactive" if bad_method == "inactive" else "payment_method_not_found")
    _rollback(db_session, case)
    assert _post(client, case, _rows(case)).status_code == 200  # Failed intent does not consume the key.


def test_zero_total_batch_rejected_legacy_paid(client, db_session):
    case = _seed_batch(sessionmaker(bind=db_session.get_bind(), autoflush=False), total=0)
    assert _post(client, case, _rows(case, (1, 1))).status_code == 409
    _rollback(db_session, case, total=0)
    response = client.post(f"/api/v1/sales/{case.sale_id}/confirm", headers={"X-Tenant-Id": str(case.tenant_id)}, json={"confirm": True})
    assert response.status_code == 200
    assert response.json()["data"]["payment_status"] == "paid"


def test_insufficient_stock_rolls_back_reserved_batch(client, db_session, case):
    item = db_session.scalar(select(InventoryItem).where(InventoryItem.tenant_id == case.tenant_id, InventoryItem.id == case.item_id))
    item.current_stock = 1
    db_session.commit()
    assert _post(client, case, _rows(case)).status_code == 409
    _rollback(db_session, case, stock=1)


@pytest.mark.parametrize("date_mode", ["omitted", "null", "explicit"])
def test_replay_uses_persistent_batch_same_ids_and_inventory(client, db_session, case, date_mode):
    rows = _rows(case)
    if date_mode != "omitted":
        for row in rows:
            row["received_at"] = None if date_mode == "null" else "2026-10-01T12:00:00Z"
    first = _post(client, case, rows)
    assert first.status_code == 200, first.text
    # A fresh coordinator is instantiated for every HTTP request.
    replay = _post(client, case, rows)
    assert replay.status_code == 200 and replay.json() == first.json()
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert len(_batches(db_session, case)) == 1
    assert _state(db_session, case) == ("confirmed", 8, 1, 3, 0)


def test_normalized_intent_and_timezone_equivalence(client, db_session, case):
    rows = _rows(case, (20, 30))
    rows[0].update(reference="  REF-0  ", notes="   ", received_at="2026-10-01T09:00:00-03:00")
    first = _post(client, case, rows)
    assert first.status_code == 200
    rows[0].update(reference="REF-0", notes=None, received_at="2026-10-01T12:00:00Z", amount_ars="20.00")
    rows[1]["received_at"] = None
    replay = _post(client, case, rows)
    assert replay.status_code == 200 and replay.json() == first.json()
    assert replay.headers["Idempotency-Replayed"] == "true"


@pytest.mark.parametrize("change", ["sale", "amount", "method", "count", "order", "reference", "notes", "received_at"])
def test_same_key_different_intent_conflicts_without_mutation(client, db_session, case, change):
    rows = _rows(case)
    first = _post(client, case, rows)
    assert first.status_code == 200
    target = case
    if change == "sale":
        target = _seed_batch(sessionmaker(bind=db_session.get_bind(), autoflush=False), tenant_id=case.tenant_id)
        rows = _rows(target)
    elif change == "count":
        rows.pop()
    elif change == "order":
        rows.reverse()
    else:
        field = "payment_method_id" if change == "method" else "amount_ars" if change == "amount" else change
        rows[1][field] = str(uuid.uuid4()) if change == "method" else "29" if change == "amount" else "2026-10-02T12:00:00Z" if change == "received_at" else "changed"
    response = _post(client, target, rows)
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "sale_payment_batch_idempotency_conflict"
    db_session.expire_all()
    assert _state(db_session, case) == ("confirmed", 8, 1, 3, 0)
    assert len(_batches(db_session, case)) == 1
    if change == "sale":
        _rollback(db_session, target)


def test_keys_scoped_to_tenant_and_foreign_sale_hidden(client, db_session, case):
    factory = sessionmaker(bind=db_session.get_bind(), autoflush=False)
    other = _seed_batch(factory)
    assert _post(client, case, _rows(case)).status_code == 200
    assert _post(client, other, _rows(other)).status_code == 200
    assert _post(client, case, _rows(case), tenant_id=other.tenant_id, key="foreign-new").status_code == 404
    assert SalePaymentBatchRepository(db_session).list_payments(other.tenant_id, _batches(db_session, case)[0].id) == []
    assert len(_batches(db_session, case)) == len(_batches(db_session, other)) == 1


def test_individual_key_namespace_and_current_replay_detail(client, db_session, case):
    rows = _rows(case, (20, 30))
    assert _post(client, case, rows, key="shared-key").status_code == 200
    individual = SalePaymentService(db_session).create(
        case.tenant_id, case.sale_id, SalePaymentCreate(payment_method_id=case.method_id, amount_ars=10,
                                                      received_at=datetime(2026, 10, 1, tzinfo=UTC)),
        user_id=None, idempotency_key="shared-key")
    assert individual.batch_id is None
    method = db_session.scalar(select(PaymentMethod).where(PaymentMethod.tenant_id == case.tenant_id, PaymentMethod.id == case.method_id))
    method.is_active = False
    method.label = "Changed label"
    db_session.commit()
    replay = _post(client, case, rows, key="shared-key")
    assert replay.status_code == 200 and replay.headers["Idempotency-Replayed"] == "true"
    assert Decimal(replay.json()["data"]["paid_total_ars"]) == 60
    assert all(p["payment_method_label_snapshot"] == "Cash" for p in replay.json()["data"]["payments"])
    assert _state(db_session, case) == ("confirmed", 8, 1, 3, 40)


def test_batch_identity_survives_voiding_member(client, db_session, case):
    rows = _rows(case, (20, 30))
    first = _post(client, case, rows)
    assert first.status_code == 200
    original_ids = {p["id"] for p in first.json()["data"]["payments"]}
    member = next(p for p in first.json()["data"]["payments"] if Decimal(p["amount_ars"]) == 20)
    SalePaymentService(db_session).void(case.tenant_id, uuid.UUID(member["id"]), reason="Correction", user_id=None)
    replay = _post(client, case, rows)
    assert replay.status_code == 200 and replay.headers["Idempotency-Replayed"] == "true"
    assert {p["id"] for p in replay.json()["data"]["payments"]} == original_ids
    assert Decimal(replay.json()["data"]["paid_total_ars"]) == 30
    assert len(_batches(db_session, case)) == 1


def test_precheck_does_not_replace_persistent_balance_validation(client, db_session, case):
    # Adverse historical state: the existing aggregate must still be honored.
    historical = SalePayment(tenant_id=case.tenant_id, sale_id=case.sale_id, payment_method_id=case.method_id,
                             payment_method_label_snapshot="Historic cash", payment_method_type_snapshot="cash",
                             amount_ars=40, received_at=datetime(2026, 10, 1, tzinfo=UTC), is_active=True)
    db_session.add(historical)
    db_session.commit()
    historical_id = historical.id
    response = _post(client, case, _rows(case))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "sale_payment_exceeds_balance"
    db_session.expire_all()
    assert _state(db_session, case) == ("draft", 10, 0, 1, 60)
    assert _batches(db_session, case) == []
    payments, _ = SalePaymentService(db_session).list(case.tenant_id, case.sale_id)
    assert [p.id for p in payments] == [historical_id]
    assert payments[0].payment_method_label_snapshot == "Historic cash"


def test_foreign_actor_rejected_before_batch_reservation(db_session, case, other_tenant):
    actor = User(tenant_id=other_tenant.id, email="foreign-p8@example.com", full_name="Foreign", role="contador", is_active=True)
    db_session.add(actor)
    db_session.commit()
    with pytest.raises(AppError) as caught:
        SaleConfirmationService(db_session).confirm(case.tenant_id, case.sale_id,
            SaleConfirm(confirm=True, initial_payments=_rows(case)), user_id=actor.id, idempotency_key="foreign-actor")
    assert caught.value.status_code == 404 and caught.value.code == "user_not_found"
    _rollback(db_session, case)


@pytest.mark.parametrize("failure", ["after_second", "before_commit", "sql_insert", "batch_insert"])
def test_durable_full_rollback_on_injected_failure(transaction_factory, monkeypatch, failure):
    case = _seed_batch(transaction_factory)
    with transaction_factory() as db:
        service = SaleConfirmationService(db)
        create = service.payments.repository.create
        calls = 0
        def injected(payment):
            nonlocal calls
            calls += 1
            if failure == "sql_insert" and calls == 3:
                payment.amount_ars = -1
            result = create(payment)
            if failure == "after_second" and calls == 2:
                raise RuntimeError("injected after second payment")
            return result
        monkeypatch.setattr(service.payments.repository, "create", injected)
        if failure == "before_commit":
            def fail_commit():
                raise RuntimeError("injected before commit")
            monkeypatch.setattr(db, "commit", fail_commit)
        if failure == "batch_insert":
            create_batch = service.batches.create
            def fail_batch(batch):
                create_batch(batch)
                raise RuntimeError("injected after batch insert")
            monkeypatch.setattr(service.batches, "create", fail_batch)
        with pytest.raises(IntegrityError if failure == "sql_insert" else RuntimeError):
            service.confirm(case.tenant_id, case.sale_id, SaleConfirm(confirm=True, initial_payments=_rows(case)),
                            user_id=None, idempotency_key="failed")
        assert not db.in_transaction()
    with transaction_factory() as observer:
        _rollback(observer, case)
    with transaction_factory() as db:
        monkeypatch.undo()
        SaleConfirmationService(db).confirm(case.tenant_id, case.sale_id, SaleConfirm(confirm=True, initial_payments=_rows(case)),
                                            user_id=None, idempotency_key="failed")
    with transaction_factory() as observer:
        assert _state(observer, case) == ("confirmed", 8, 1, 3, 0)


def test_one_outer_commit_actors_and_no_per_payment_sale_locks(transaction_factory, monkeypatch):
    case = _seed_batch(transaction_factory)
    actor_id = uuid.uuid4()
    with transaction_factory.begin() as db:
        db.add(User(id=actor_id, tenant_id=case.tenant_id, email="p8@example.com", full_name="P8 Operator", role="contador", is_active=True))
    with transaction_factory(expire_on_commit=False) as db:
        service = SaleConfirmationService(db)
        commit = db.commit
        commits = []
        def record_commit():
            commits.append(True)
            commit()
        def unexpected_lock(*args, **kwargs):
            raise AssertionError("Batch member must reuse coordinator's Sale lock")
        monkeypatch.setattr(db, "commit", record_commit)
        monkeypatch.setattr(service.payments.sale_repository, "get_by_id", unexpected_lock)
        sale = service.confirm(case.tenant_id, case.sale_id, SaleConfirm(confirm=True, initial_payments=_rows(case)),
                               user_id=actor_id, idempotency_key="one-commit")
        detail = SaleDetailRead.model_validate(sale)
        assert len(commits) == 1
        assert detail.confirmed_by_user_id == actor_id and detail.confirmed_by_user_name == "P8 Operator"
        assert all(p.created_by_user_id == actor_id and p.created_by_user_name == "P8 Operator" for p in detail.payments)


@pytest.mark.parametrize("race", ["same_intent", "different_intent", "different_keys"])
def test_postgresql_concurrent_http_batches(client, postgres_transaction_factory, monkeypatch, race):
    factory = postgres_transaction_factory
    case = _seed_batch(factory)
    barrier, calls = Barrier(2), local()
    lookup = SalePaymentBatchRepository.get_by_idempotency_key
    def synchronized_lookup(repository, tenant_id, key):
        result = lookup(repository, tenant_id, key)
        calls.count = getattr(calls, "count", 0) + 1
        if calls.count == 1:
            assert result is None
            barrier.wait(timeout=15)
        return result
    monkeypatch.setattr(SalePaymentBatchRepository, "get_by_idempotency_key", synchronized_lookup)
    def get_test_db():
        with factory() as db:
            yield db
    client.app.dependency_overrides[get_db] = get_test_db
    def checkout(index):
        amounts = (20, 80) if index == 0 or race == "same_intent" else (30, 70)
        with TestClient(client.app) as request_client:
            return _post(request_client, case, _rows(case, amounts), key=f"race-{index}" if race == "different_keys" else "race")
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(checkout, range(2)))
    if race == "same_intent":
        assert [r.status_code for r in responses] == [200, 200]
        assert sorted(r.headers["Idempotency-Replayed"] for r in responses) == ["false", "true"]
        assert responses[0].json() == responses[1].json()
    else:
        assert sorted(r.status_code for r in responses) == [200, 409]
        loser = next(r for r in responses if r.status_code == 409)
        assert loser.json()["error"]["code"] == ("sale_payment_batch_idempotency_conflict" if race == "different_intent" else "sale_not_editable")
    with factory() as observer:
        assert _state(observer, case) == ("confirmed", 8, 1, 2, 0)
        assert len(_batches(observer, case)) == 1


@pytest.mark.parametrize("shared_inventory", [False, True])
def test_postgresql_cross_sale_unique_race_rolls_back_loser(postgres_transaction_factory, monkeypatch, shared_inventory):
    factory = postgres_transaction_factory
    first = _seed_batch(factory)
    cases = [first, _seed_batch(factory, tenant_id=first.tenant_id)]
    if shared_inventory:
        with factory.begin() as db:
            second = SaleService(db).get(cases[1].tenant_id, cases[1].sale_id)
            second.items[0].inventory_item_id = first.item_id
        cases[1].item_id = first.item_id
    barrier = Barrier(2)
    create = SalePaymentBatchRepository.create
    def synchronize_reservation(repository, batch):
        barrier.wait(timeout=15)
        return create(repository, batch)
    monkeypatch.setattr(SalePaymentBatchRepository, "create", synchronize_reservation)
    def checkout(case):
        with factory() as db:
            try:
                SaleConfirmationService(db).confirm(case.tenant_id, case.sale_id,
                    SaleConfirm(confirm=True, initial_payments=_rows(case)), user_id=None, idempotency_key="cross-sale")
                return case, "created"
            except AppError as error:
                assert error.code == "sale_payment_batch_idempotency_conflict"
                assert not db.in_transaction()
                return case, "conflict"
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(checkout, cases))
    assert sorted(outcome for _, outcome in results) == ["conflict", "created"]
    with factory() as observer:
        for case, outcome in results:
            if outcome == "created":
                assert _state(observer, case) == ("confirmed", 8, 1, 3, 0)
                assert len(_batches(observer, case)) == 1
            else:
                _rollback(observer, case, stock=8 if shared_inventory else 10)

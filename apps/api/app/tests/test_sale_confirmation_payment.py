"""P.6: checkout API, durable rollback and real PostgreSQL request races."""

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
from app.models.payment import PaymentMethod, SalePayment
from app.models.user import User
from app.repositories.payment import SalePaymentRepository
from app.schemas.sale import SaleConfirm, SaleDetailRead
from app.services.sale import SaleService
from app.services.sale_confirmation import SaleConfirmationService
from app.tests.test_sale_transaction_composition import (
    _seed,
    _state,
    postgres_transaction_factory,
    transaction_factory,
)


@pytest.fixture()
def case(db_session):
    return _seed(sessionmaker(bind=db_session.get_bind(), autoflush=False))


def _payment(case, **changes):
    return {
        "payment_method_id": str(case.method_id), "amount_ars": "7.00",
        "received_at": "2026-10-01T12:00:00Z", "reference": "REF-1", "notes": "Cobro inicial",
        **changes,
    }


def _post(client, case, payment, *, key="p6-intent", tenant_id=None):
    headers = {"X-Tenant-Id": str(tenant_id or case.tenant_id)}
    if key is not None:
        headers["Idempotency-Key"] = key
    return client.post(
        f"/api/v1/sales/{case.sale_id}/confirm", headers=headers,
        json={"confirm": True, "initial_payment": payment},
    )


def _assert_rollback(db, case, *, stock=10, total=20):
    db.expire_all()
    assert _state(db, case) == ("draft", stock, 0, 0, total)
    sale = SaleService(db).get(case.tenant_id, case.sale_id)
    assert sale.confirmed_at is None
    assert sale.confirmed_by_user_id is None
    assert sale.inventory_operation_id is None
    assert db.scalar(select(SalePayment.id).where(
        SalePayment.tenant_id == case.tenant_id, SalePayment.sale_id == case.sale_id,
    )) is None


@pytest.mark.parametrize("omit", [False, True])
def test_legacy_confirmation_without_payment(client, db_session, case, omit):
    body = {"confirm": True}
    if not omit:
        body["initial_payment"] = None
    response = client.post(
        f"/api/v1/sales/{case.sale_id}/confirm",
        headers={"X-Tenant-Id": str(case.tenant_id)}, json=body,
    )
    assert response.status_code == 200, response.text
    assert "Idempotency-Replayed" not in response.headers
    assert response.json()["meta"] == {}
    detail = response.json()["data"]
    assert detail["payments"] == [] and detail["payment_status"] == "unpaid"
    assert Decimal(detail["balance_due_ars"]) == 20
    assert _state(db_session, case) == ("confirmed", 8, 1, 0, 20)


@pytest.mark.parametrize("amount, status, balance", [("20.00", "paid", 0), ("7.00", "partial", 13)])
def test_full_and_partial_initial_payment(client, db_session, case, amount, status, balance):
    response = _post(client, case, _payment(case, amount_ars=amount))
    assert response.status_code == 200, response.text
    assert response.headers["Idempotency-Replayed"] == "false"
    detail = response.json()["data"]
    assert detail["status"] == "confirmed" and len(detail["items"]) == 1
    assert detail["payment_status"] == status
    assert Decimal(detail["paid_total_ars"]) == Decimal(amount)
    assert Decimal(detail["balance_due_ars"]) == balance
    payment = detail["payments"][0]
    assert payment["payment_method_label_snapshot"] == "Cash"
    assert payment["payment_method_type_snapshot"] == "cash"
    assert payment["reference"] == "REF-1" and payment["notes"] == "Cobro inicial"
    assert _state(db_session, case) == ("confirmed", 8, 1, 1, balance)


@pytest.mark.parametrize("date_mode", ["explicit", "omitted", "null"])
def test_retry_after_commit_reuses_payment_and_inventory(client, db_session, case, date_mode):
    payment = _payment(case)
    if date_mode == "omitted":
        del payment["received_at"]
    elif date_mode == "null":
        payment["received_at"] = None
    before = datetime.now(UTC)
    first = _post(client, case, payment)
    after = datetime.now(UTC)
    assert first.status_code == 200, first.text
    replay = _post(client, case, payment)
    assert replay.status_code == 200, replay.text
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json() == first.json()
    if date_mode != "explicit":
        received = datetime.fromisoformat(first.json()["data"]["payments"][0]["received_at"])
        assert before <= received.replace(tzinfo=UTC) <= after
    assert _state(db_session, case) == ("confirmed", 8, 1, 1, 13)


@pytest.mark.parametrize("key", [None, "", " ", "\t", "two words", "a" * 129])
def test_initial_payment_requires_valid_key(client, db_session, case, key):
    response = _post(client, case, _payment(case), key=key)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "validation_error"
    _assert_rollback(db_session, case)


@pytest.mark.parametrize("amount", ["0", "-1", "1.001", "10000000000000000", "NaN", "Infinity"])
def test_initial_amount_uses_existing_payment_validation(client, db_session, case, amount):
    response = _post(client, case, _payment(case, amount_ars=amount))
    assert response.status_code == 422, response.text
    _assert_rollback(db_session, case)


@pytest.mark.parametrize("failure", ["inactive", "foreign", "overpayment"])
def test_payment_error_after_internal_confirmation_rolls_back_everything(client, db_session, case, failure):
    payment = _payment(case)
    if failure == "inactive":
        method = db_session.scalar(select(PaymentMethod).where(
            PaymentMethod.tenant_id == case.tenant_id, PaymentMethod.id == case.method_id,
        ))
        method.is_active = False
        db_session.commit()
        status, code = 409, "payment_method_inactive"
    elif failure == "foreign":
        foreign = _seed(sessionmaker(bind=db_session.get_bind(), autoflush=False))
        payment["payment_method_id"] = str(foreign.method_id)
        status, code = 404, "payment_method_not_found"
    else:
        payment["amount_ars"] = "20.01"
        status, code = 409, "sale_payment_exceeds_balance"
    response = _post(client, case, payment)
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    _assert_rollback(db_session, case)


def test_insufficient_stock_never_creates_payment(client, db_session, case):
    item = db_session.scalar(select(InventoryItem).where(
        InventoryItem.tenant_id == case.tenant_id, InventoryItem.id == case.item_id,
    ))
    item.current_stock = Decimal("1")
    db_session.commit()
    response = _post(client, case, _payment(case))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "sale_insufficient_stock"
    _assert_rollback(db_session, case, stock=1)


@pytest.mark.parametrize("with_payment", [False, True])
def test_zero_total_confirmation_never_creates_fictitious_payment(client, db_session, case, with_payment):
    sale = SaleService(db_session).get(case.tenant_id, case.sale_id)
    sale.subtotal_ars = sale.total_ars = Decimal("0")
    sale.items[0].unit_price_ars = sale.items[0].line_subtotal_ars = sale.items[0].line_total_ars = Decimal("0")
    db_session.commit()
    response = _post(client, case, _payment(case) if with_payment else None, key="zero" if with_payment else None)
    if with_payment:
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "sale_payment_exceeds_balance"
        _assert_rollback(db_session, case, total=0)
    else:
        assert response.status_code == 200
        assert response.json()["data"]["payment_status"] == "paid"
        assert response.json()["data"]["payments"] == []
        assert _state(db_session, case) == ("confirmed", 8, 1, 0, 0)


@pytest.mark.parametrize("field", ["amount_ars", "payment_method_id", "received_at", "reference", "notes", "sale"])
def test_changed_intent_conflicts_without_additional_writes(client, db_session, case, field):
    payload = _payment(case)
    first = _post(client, case, payload)
    assert first.status_code == 200
    other = _seed(sessionmaker(bind=db_session.get_bind(), autoflush=False), tenant_id=case.tenant_id)
    target = case
    if field == "sale":
        target = other
    else:
        payload[field] = {
            "amount_ars": "8.00", "payment_method_id": str(other.method_id),
            "received_at": "2026-10-01T12:00:01Z", "reference": "REF-2", "notes": "Cambio",
        }[field]
    conflict = _post(client, target, payload)
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["error"]["code"] == "sale_payment_idempotency_conflict"
    assert _post(client, case, _payment(case)).json() == first.json()
    assert _state(db_session, case) == ("confirmed", 8, 1, 1, 13)
    _assert_rollback(db_session, other)


def test_equal_key_is_scoped_to_tenant_and_foreign_sale_is_hidden(client, db_session, case):
    foreign = _seed(sessionmaker(bind=db_session.get_bind(), autoflush=False))
    first = _post(client, foreign, _payment(foreign))
    assert first.status_code == 200
    denied = _post(client, foreign, _payment(foreign), tenant_id=case.tenant_id)
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "sale_not_found"
    local_response = _post(client, case, _payment(case))
    assert local_response.status_code == 200
    assert local_response.json()["data"]["payments"][0]["id"] != first.json()["data"]["payments"][0]["id"]
    assert _state(db_session, case) == _state(db_session, foreign) == ("confirmed", 8, 1, 1, 13)


def test_replay_returns_current_summary_and_original_snapshots(client, db_session, case):
    first = _post(client, case, _payment(case)).json()["data"]
    extra = client.post(
        f"/api/v1/sales/{case.sale_id}/payments",
        headers={"X-Tenant-Id": str(case.tenant_id), "Idempotency-Key": "later"},
        json=_payment(case, amount_ars="13.00"),
    )
    assert extra.status_code == 201
    method = db_session.scalar(select(PaymentMethod).where(
        PaymentMethod.tenant_id == case.tenant_id, PaymentMethod.id == case.method_id,
    ))
    method.label, method.is_active = "Renamed", False
    db_session.commit()
    replay = _post(client, case, _payment(case))
    assert replay.status_code == 200 and replay.headers["Idempotency-Replayed"] == "true"
    detail = replay.json()["data"]
    assert detail["payment_status"] == "paid" and Decimal(detail["balance_due_ars"]) == 0
    assert len(detail["payments"]) == 2
    assert first["payments"][0] in detail["payments"]
    assert _state(db_session, case) == ("confirmed", 8, 1, 2, 0)


def test_existing_confirmed_sale_with_new_key_cannot_checkout_again(client, db_session, case):
    assert _post(client, case, None, key=None).status_code == 200
    response = _post(client, case, _payment(case), key="new")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "sale_not_editable"
    assert _state(db_session, case) == ("confirmed", 8, 1, 0, 20)


def test_normalized_key_amount_date_and_text_keep_same_checkout_intent(client, db_session, case):
    first = _post(client, case, _payment(case, amount_ars="7", reference="  REF-1  ", notes=" "), key=" p6-normalized ")
    assert first.status_code == 200
    payload = _payment(case, amount_ars="7e0", received_at="2026-10-01T09:00:00-03:00")
    del payload["notes"]
    replay = _post(client, case, payload, key="p6-normalized")
    assert replay.status_code == 200 and replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json() == first.json()
    assert _state(db_session, case) == ("confirmed", 8, 1, 1, 13)


def test_generated_date_intent_is_stable_but_conflicts_with_explicit_date(client, db_session, case):
    payload = _payment(case)
    del payload["received_at"]
    first = _post(client, case, payload)
    assert first.status_code == 200
    replay = _post(client, case, {**payload, "received_at": None})
    assert replay.status_code == 200 and replay.json() == first.json()
    effective_date = first.json()["data"]["payments"][0]["received_at"]
    conflict = _post(client, case, {**payload, "received_at": effective_date})
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "sale_payment_idempotency_conflict"
    assert _state(db_session, case) == ("confirmed", 8, 1, 1, 13)


def test_failed_checkout_does_not_reserve_key_and_can_retry_after_correction(client, db_session, case):
    response = _post(client, case, _payment(case, amount_ars="21.00"))
    assert response.status_code == 409
    _assert_rollback(db_session, case)
    corrected = _post(client, case, _payment(case))
    assert corrected.status_code == 200
    assert corrected.headers["Idempotency-Replayed"] == "false"
    assert _state(db_session, case) == ("confirmed", 8, 1, 1, 13)


@pytest.mark.parametrize("failure", ["before_commit", "payment_insert", "sql_insert", "inventory"])
def test_coordinator_unexpected_failure_rolls_back_durable_state(transaction_factory, monkeypatch, failure):
    case = _seed(transaction_factory)
    with transaction_factory() as db:
        service = SaleConfirmationService(db)
        if failure == "before_commit":
            def fail_commit():
                assert _state(db, case) == ("confirmed", 8, 1, 1, 13)
                with transaction_factory() as observer:
                    _assert_rollback(observer, case)
                raise RuntimeError("injected before commit")
            monkeypatch.setattr(db, "commit", fail_commit)
        elif failure in ("payment_insert", "sql_insert"):
            create = service.payments.repository.create
            def fail_insert(payment):
                if failure == "sql_insert":
                    payment.amount_ars = Decimal("-1")
                create(payment)
                raise RuntimeError("injected after payment insert")
            monkeypatch.setattr(service.payments.repository, "create", fail_insert)
        else:
            register = service.sales.inventory_service.register_sale_movement
            def fail_movement(*args, **kwargs):
                register(*args, **kwargs)
                raise RuntimeError("injected after inventory write")
            monkeypatch.setattr(service.sales.inventory_service, "register_sale_movement", fail_movement)
        with pytest.raises(IntegrityError if failure == "sql_insert" else RuntimeError):
            service.confirm(case.tenant_id, case.sale_id, SaleConfirm(confirm=True, initial_payment=_payment(case)), user_id=None, idempotency_key="failure")
        assert not db.in_transaction()
    with transaction_factory() as observer:
        _assert_rollback(observer, case)


def test_coordinator_commits_once_and_reloads_with_expiration_disabled(transaction_factory, monkeypatch):
    case = _seed(transaction_factory)
    actor_id = uuid.uuid4()
    with transaction_factory.begin() as setup:
        setup.add(User(id=actor_id, tenant_id=case.tenant_id, email="p6@example.com", full_name="P.6 Operator", role="contador", is_active=True))
    with transaction_factory(expire_on_commit=False) as db:
        commits = []
        commit = db.commit
        def record_commit():
            commits.append(True)
            commit()
        monkeypatch.setattr(db, "commit", record_commit)
        sale = SaleConfirmationService(db).confirm(
            case.tenant_id, case.sale_id, SaleConfirm(confirm=True, initial_payment=_payment(case)),
            user_id=actor_id, idempotency_key="one-commit",
        )
        detail = SaleDetailRead.model_validate(sale)
        assert len(commits) == 1
        assert detail.confirmed_by_user_id == actor_id
        assert detail.confirmed_by_user_name == "P.6 Operator"
        assert detail.payments[0].created_by_user_id == actor_id
        assert detail.paid_total_ars == 7 and detail.balance_due_ars == 13
    with transaction_factory() as observer:
        assert _state(observer, case) == ("confirmed", 8, 1, 1, 13)


@pytest.mark.parametrize("same_key", [True, False])
def test_postgresql_concurrent_checkout_requests(client, postgres_transaction_factory, monkeypatch, same_key):
    factory = postgres_transaction_factory
    case = _seed(factory)
    barrier = Barrier(2)
    calls = local()
    lookup = SalePaymentRepository.get_by_idempotency_key
    def synchronized_lookup(repository, tenant_id, key):
        result = lookup(repository, tenant_id, key)
        calls.count = getattr(calls, "count", 0) + 1
        if calls.count == 1:
            assert result is None
            barrier.wait(timeout=15)
        return result
    monkeypatch.setattr(SalePaymentRepository, "get_by_idempotency_key", synchronized_lookup)
    def get_test_db():
        with factory() as db:
            yield db
    client.app.dependency_overrides[get_db] = get_test_db
    def checkout(index):
        # A separate HTTP client and SQLAlchemy Session for each request.
        with TestClient(client.app) as request_client:
            return _post(request_client, case, _payment(case), key="race" if same_key else f"race-{index}")
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(checkout, range(2)))
    if same_key:
        assert [response.status_code for response in responses] == [200, 200]
        assert sorted(response.headers["Idempotency-Replayed"] for response in responses) == ["false", "true"]
        assert responses[0].json() == responses[1].json()
    else:
        assert sorted(response.status_code for response in responses) == [200, 409]
        loser = next(response for response in responses if response.status_code == 409)
        assert loser.json()["error"]["code"] == "sale_not_editable"
    with factory() as observer:
        assert _state(observer, case) == ("confirmed", 8, 1, 1, 13)


def test_postgresql_cross_sale_key_collision_rolls_back_losing_confirmation(postgres_transaction_factory, monkeypatch):
    factory = postgres_transaction_factory
    first = _seed(factory)
    cases = [first, _seed(factory, tenant_id=first.tenant_id)]
    barrier = Barrier(2)
    calls = local()
    lookup = SalePaymentRepository.get_by_idempotency_key
    def synchronize_after_confirmation(repository, tenant_id, key):
        result = lookup(repository, tenant_id, key)
        calls.count = getattr(calls, "count", 0) + 1
        if calls.count == 4:
            assert result is None
            barrier.wait(timeout=15)
        return result
    monkeypatch.setattr(SalePaymentRepository, "get_by_idempotency_key", synchronize_after_confirmation)
    def checkout(case):
        with factory() as db:
            try:
                SaleConfirmationService(db).confirm(
                    case.tenant_id, case.sale_id, SaleConfirm(confirm=True, initial_payment=_payment(case)),
                    user_id=None, idempotency_key="cross-sale-race",
                )
                return case, "created"
            except AppError as error:
                assert error.code == "sale_payment_idempotency_conflict"
                assert not db.in_transaction()
                return case, "conflict"
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(checkout, cases))
    assert sorted(result for _, result in results) == ["conflict", "created"]
    with factory() as observer:
        for case, outcome in results:
            if outcome == "created":
                assert _state(observer, case) == ("confirmed", 8, 1, 1, 13)
            else:
                _assert_rollback(observer, case)

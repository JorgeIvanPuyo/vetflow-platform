"""P.5: real outer transactions, including SQLite's legacy SAVEPOINT behavior."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from threading import Barrier, local
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.errors import AppError
from app.db.base import Base
from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.owner import Owner
from app.models.payment import PaymentMethod, SalePayment
from app.models.sale import Sale
from app.models.tenant import Tenant
from app.repositories.payment import SalePaymentRepository
from app.schemas.payment import SalePaymentCreate, SalePaymentRead
from app.services.payment import SalePaymentService
from app.services.sale import SaleService
from app.tests.test_sale_confirmation_concurrency import _sale


@pytest.fixture()
def postgres_transaction_factory(postgres_test_session_factory):
    engine = postgres_test_session_factory.kw["bind"]
    schema = "p5_" + uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    scoped_engine = engine.execution_options(schema_translate_map={None: schema})
    try:
        Base.metadata.create_all(scoped_engine)
        yield sessionmaker(bind=scoped_engine, autoflush=False)
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))


@pytest.fixture(params=["sqlite", "postgresql"])
def transaction_factory(request, tmp_path):
    if request.param == "postgresql":
        return request.getfixturevalue("postgres_transaction_factory")
    # Separate connections verify durable state, not the Session's identity map.
    # Keep sqlite3 legacy transaction mode to catch SAVEPOINT-as-COMMIT bugs.
    engine = create_engine(f"sqlite:///{tmp_path / 'p5.sqlite'}")
    Base.metadata.create_all(engine)
    request.addfinalizer(engine.dispose)
    return sessionmaker(bind=engine, autoflush=False)


def _seed(factory, *, confirmed=False, tenant_id=None, with_owner=True):
    with factory.begin() as db:
        if tenant_id is None:
            tenant = Tenant(id=uuid.uuid4(), name="P.5")
            db.add(tenant)
            db.flush()
            tenant_id = tenant.id
        item = InventoryItem(
            tenant_id=tenant_id, internal_code=uuid.uuid4().hex[:10], name="P.5 item",
            category="supply", unit="unit", current_stock=Decimal("10"),
            minimum_stock=Decimal("0"), sale_price_ars=Decimal("10"), is_active=True,
            purchase_tax_rate_percentage=Decimal("0"), profit_margin_percentage=Decimal("0"),
            sale_tax_rate_percentage=Decimal("0"),
        )
        method = PaymentMethod(
            tenant_id=tenant_id, label="Cash", normalized_label=uuid.uuid4().hex,
            type="cash", is_active=True, sort_order=0,
        )
        db.add_all([item, method])
        db.flush()
        owner = None
        if with_owner:
            owner = Owner(tenant_id=tenant_id, full_name="P.5 Customer", phone="555")
            db.add(owner)
            db.flush()
        sale = _sale(tenant_id, item, Decimal("2"))
        sale.owner_id = owner.id if owner else None
        sale.owner_name_snapshot = owner.full_name if owner else None
        if confirmed:
            sale.status = "confirmed"
        db.add(sale)
        db.flush()
        return SimpleNamespace(tenant_id=tenant_id, sale_id=sale.id, item_id=item.id, method_id=method.id, owner_id=owner.id if owner else None)


def _payload(case, **changes):
    return SalePaymentCreate(
        **{"payment_method_id": case.method_id, "amount_ars": Decimal("7"),
           "received_at": datetime(2026, 10, 1, 12, tzinfo=UTC), **changes}
    )


def _state(db, case):
    sale = SaleService(db).get(case.tenant_id, case.sale_id)
    stock = db.scalar(select(InventoryItem.current_stock).where(
        InventoryItem.tenant_id == case.tenant_id, InventoryItem.id == case.item_id))
    movements = db.scalar(select(func.count(InventoryMovement.id)).where(
        InventoryMovement.tenant_id == case.tenant_id, InventoryMovement.source_id == str(case.sale_id)))
    payments, summary = SalePaymentService(db).list(case.tenant_id, case.sale_id)
    return sale.status, stock, movements, len(payments), summary["balance_due_ars"]


def _no_transaction_completion(*args, **kwargs):
    raise AssertionError("Only the caller may complete the outer transaction")


def test_internal_confirmation_is_uncommitted_and_outer_rollback_restores_inventory(transaction_factory, monkeypatch):
    case = _seed(transaction_factory)
    with transaction_factory() as db:
        db.begin()
        with monkeypatch.context() as patch:
            patch.setattr(db, "commit", _no_transaction_completion)
            patch.setattr(db, "rollback", _no_transaction_completion)
            sale = SaleService(db).confirm_in_transaction(case.tenant_id, case.sale_id, confirmed_by_user_id=None)
            assert sale.status == "confirmed" and sale.inventory_operation_id is not None
        assert _state(db, case) == ("confirmed", 8, 1, 0, 20)
        with transaction_factory() as observer:
            assert _state(observer, case) == ("draft", 10, 0, 0, 20)
        db.rollback()
    with transaction_factory() as observer:
        assert _state(observer, case) == ("draft", 10, 0, 0, 20)


@pytest.mark.parametrize("key", [None, "p5-payment"])
def test_internal_payment_rollback_has_no_durable_payment(transaction_factory, monkeypatch, key):
    case = _seed(transaction_factory, confirmed=True)
    with transaction_factory() as db:
        db.begin()
        with monkeypatch.context() as patch:
            patch.setattr(db, "commit", _no_transaction_completion)
            patch.setattr(db, "rollback", _no_transaction_completion)
            payment = SalePaymentService(db).create_in_transaction(
                case.tenant_id, case.sale_id, _payload(case), user_id=None, idempotency_key=key)
            assert SalePaymentRead.model_validate(payment).amount_ars == 7
        assert _state(db, case) == ("confirmed", 10, 0, 1, 13)
        with transaction_factory() as observer:
            assert _state(observer, case) == ("confirmed", 10, 0, 0, 20)
        db.rollback()
    with transaction_factory() as observer:
        assert _state(observer, case) == ("confirmed", 10, 0, 0, 20)


@pytest.mark.parametrize("commit", [False, True])
@pytest.mark.parametrize("key", [None, "p5-composed"])
def test_composed_confirmation_and_payment(transaction_factory, monkeypatch, commit, key):
    case = _seed(transaction_factory)
    with transaction_factory() as db:
        db.begin()
        with monkeypatch.context() as patch:
            patch.setattr(db, "commit", _no_transaction_completion)
            patch.setattr(db, "rollback", _no_transaction_completion)
            sale = SaleService(db).confirm_in_transaction(case.tenant_id, case.sale_id, confirmed_by_user_id=None)
            payment = SalePaymentService(db).create_in_transaction(
                case.tenant_id, case.sale_id, _payload(case), user_id=None, idempotency_key=key)
            payment_id = payment.id
            assert sale.paid_total_ars == 7 and sale.balance_due_ars == 13
            assert sale.payment_status == "partial"
        with transaction_factory() as observer:
            assert _state(observer, case) == ("draft", 10, 0, 0, 20)
        db.commit() if commit else db.rollback()
    with transaction_factory() as observer:
        assert _state(observer, case) == (("confirmed", 8, 1, 1, 13) if commit else ("draft", 10, 0, 0, 20))
    if commit and key:
        with transaction_factory() as db:
            service = SalePaymentService(db)
            replay = service.create(case.tenant_id, case.sale_id, _payload(case), user_id=None, idempotency_key=key)
            assert service.idempotency_replayed and replay.id == payment_id


@pytest.mark.parametrize("failure,code", [
    ("method", "payment_method_not_found"), ("overpayment", "sale_payment_exceeds_balance"),
])
def test_payment_business_error_leaves_confirmation_for_caller_to_rollback(transaction_factory, failure, code):
    case = _seed(transaction_factory)
    changes = {"payment_method_id": uuid.uuid4()} if failure == "method" else {"amount_ars": Decimal("21")}
    with transaction_factory() as db:
        db.begin()
        SaleService(db).confirm_in_transaction(case.tenant_id, case.sale_id, confirmed_by_user_id=None)
        with pytest.raises(AppError) as error:
            SalePaymentService(db).create_in_transaction(case.tenant_id, case.sale_id, _payload(case, **changes), user_id=None, idempotency_key="p5-error")
        assert error.value.code == code
        assert db.is_active and _state(db, case) == ("confirmed", 8, 1, 0, 20)
        db.rollback()
    with transaction_factory() as observer:
        assert _state(observer, case) == ("draft", 10, 0, 0, 20)


@pytest.mark.parametrize("operation", ["confirm", "payment"])
def test_legacy_wrapper_rolls_back_prior_writes_on_business_error(transaction_factory, operation):
    case = _seed(transaction_factory, confirmed=True)
    with transaction_factory() as db:
        item = db.scalar(select(InventoryItem).where(InventoryItem.tenant_id == case.tenant_id, InventoryItem.id == case.item_id))
        item.name = "must roll back"
        db.flush()
        with pytest.raises(AppError):
            if operation == "confirm":
                SaleService(db).confirm(case.tenant_id, case.sale_id, confirmed_by_user_id=None)
            else:
                SalePaymentService(db).create(case.tenant_id, case.sale_id, _payload(case, amount_ars=Decimal("21")), user_id=None)
        assert not db.in_transaction()
    with transaction_factory() as observer:
        assert observer.get(InventoryItem, case.item_id).name == "P.5 item"


@pytest.mark.parametrize("outcome", ["replay", "conflict", "unrelated_error"])
def test_unique_savepoint_preserves_outer_changes_and_recovers_session(transaction_factory, monkeypatch, outcome):
    case = _seed(transaction_factory, confirmed=True)
    prior = _seed(transaction_factory, tenant_id=case.tenant_id)
    with transaction_factory() as db:
        original = SalePaymentService(db).create(case.tenant_id, case.sale_id, _payload(case), user_id=None, idempotency_key="p5-key")
        original_id = original.id
    with transaction_factory() as db:
        db.begin()
        SaleService(db).confirm_in_transaction(prior.tenant_id, prior.sale_id, confirmed_by_user_id=None)
        service = SalePaymentService(db)
        real_lookup = service.repository.get_by_idempotency_key
        calls = []
        def miss_first_two(*args):
            calls.append(1)
            return None if len(calls) <= 2 else real_lookup(*args)
        # Force the INSERT recovery path; the actual database raises UNIQUE.
        monkeypatch.setattr(service.repository, "get_by_idempotency_key", miss_first_two)
        if outcome == "unrelated_error":
            real_create = service.repository.create
            def invalid_insert(payment):
                payment.idempotency_key = "unrelated-key"
                payment.amount_ars = Decimal("-1")
                return real_create(payment)
            monkeypatch.setattr(service.repository, "create", invalid_insert)
        payload = _payload(case, amount_ars=Decimal("8" if outcome == "conflict" else "7"))
        with monkeypatch.context() as patch:
            patch.setattr(db, "commit", _no_transaction_completion)
            patch.setattr(db, "rollback", _no_transaction_completion)
            if outcome == "replay":
                replay = service.create_in_transaction(case.tenant_id, case.sale_id, payload, user_id=None, idempotency_key="p5-key")
                assert replay.id == original_id and service.idempotency_replayed
            else:
                with pytest.raises(AppError if outcome == "conflict" else IntegrityError) as error:
                    service.create_in_transaction(case.tenant_id, case.sale_id, payload, user_id=None, idempotency_key="p5-key")
                if outcome == "conflict":
                    assert error.value.code == "sale_payment_idempotency_conflict"
        assert db.is_active and db.in_transaction() and not db.in_nested_transaction()
        assert len(calls) == (2 if outcome == "unrelated_error" else 3)
        assert _state(db, prior) == ("confirmed", 8, 1, 0, 20)
        assert real_lookup(case.tenant_id, "p5-key").id == original_id
        # The coordinator can still write after recovering the SAVEPOINT.
        SalePaymentService(db).create_in_transaction(prior.tenant_id, prior.sale_id, _payload(prior), user_id=None)
        db.commit()
    with transaction_factory() as observer:
        assert _state(observer, prior) == ("confirmed", 8, 1, 1, 13)
        assert _state(observer, case) == ("confirmed", 10, 0, 1, 13)


@pytest.mark.parametrize("commit", [False, True])
def test_postgresql_concurrent_unique_conflict_preserves_both_outer_confirmations(postgres_transaction_factory, monkeypatch, commit):
    factory = postgres_transaction_factory
    first = _seed(factory)
    cases = [first, _seed(factory, tenant_id=first.tenant_id)]
    barrier = Barrier(2)
    calls = local()
    lookup = SalePaymentRepository.get_by_idempotency_key
    def synchronized_lookup(repository, tenant_id, key):
        result = lookup(repository, tenant_id, key)
        calls.count = getattr(calls, "count", 0) + 1
        if calls.count == 2:
            assert result is None
            barrier.wait(timeout=10)
        return result
    monkeypatch.setattr(SalePaymentRepository, "get_by_idempotency_key", synchronized_lookup)
    def compose(case):
        with factory() as db:
            db.begin()
            SaleService(db).confirm_in_transaction(case.tenant_id, case.sale_id, confirmed_by_user_id=None)
            try:
                SalePaymentService(db).create_in_transaction(case.tenant_id, case.sale_id, _payload(case), user_id=None, idempotency_key="race")
            except AppError as error:
                assert error.code == "sale_payment_idempotency_conflict"
                assert db.is_active and _state(db, case) == ("confirmed", 8, 1, 0, 20)
                db.commit() if commit else db.rollback()
                return case, "conflict"
            db.commit()
            return case, "created"
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(compose, cases))
    assert sorted(result for _, result in results) == ["conflict", "created"]
    with factory() as observer:
        for case, result in results:
            expected = ("confirmed", 8, 1, 1, 13) if result == "created" else (("confirmed", 8, 1, 0, 20) if commit else ("draft", 10, 0, 0, 20))
            assert _state(observer, case) == expected


@pytest.mark.parametrize("operation", ["confirm", "payment"])
def test_legacy_wrapper_rolls_back_unexpected_error_after_writes(transaction_factory, monkeypatch, operation):
    case = _seed(transaction_factory)
    with transaction_factory() as db:
        sales = SaleService(db)
        if operation == "confirm":
            save = sales.repository.save
            def fail_after_save(sale):
                save(sale)
                raise RuntimeError("failure after inventory and confirmation writes")
            monkeypatch.setattr(sales.repository, "save", fail_after_save)
            with pytest.raises(RuntimeError, match="failure after"):
                sales.confirm(case.tenant_id, case.sale_id, confirmed_by_user_id=None)
        else:
            sales.confirm_in_transaction(case.tenant_id, case.sale_id, confirmed_by_user_id=None)
            payments = SalePaymentService(db)
            create = payments.repository.create
            def invalid_insert(payment):
                payment.amount_ars = Decimal("-1")
                return create(payment)
            monkeypatch.setattr(payments.repository, "create", invalid_insert)
            with pytest.raises(IntegrityError):
                payments.create(case.tenant_id, case.sale_id, _payload(case), user_id=None, idempotency_key="p5-sql-error")
        assert not db.in_transaction()
    with transaction_factory() as observer:
        assert _state(observer, case) == ("draft", 10, 0, 0, 20)


def test_outer_flush_failure_is_not_treated_as_insert_collision(transaction_factory, monkeypatch):
    case = _seed(transaction_factory)
    with transaction_factory() as db:
        SaleService(db).confirm_in_transaction(case.tenant_id, case.sale_id, confirmed_by_user_id=None)
        db.add(PaymentMethod(tenant_id=case.tenant_id, label="Invalid", normalized_label="invalid", type="INVALID"))
        service = SalePaymentService(db)
        def fail_if_insert_called(*args):
            raise AssertionError("The outer pending state must flush before inserting the payment")
        monkeypatch.setattr(service.repository, "create", fail_if_insert_called)
        with pytest.raises(IntegrityError):
            service.create_in_transaction(case.tenant_id, case.sale_id, _payload(case), user_id=None, idempotency_key="p5-outer-failure")
        assert not db.is_active
        db.rollback()
    with transaction_factory() as observer:
        assert _state(observer, case) == ("draft", 10, 0, 0, 20)


def test_internal_operations_reject_foreign_sale_and_method(transaction_factory):
    case = _seed(transaction_factory)
    foreign = _seed(transaction_factory, confirmed=True)
    with transaction_factory() as db:
        for operation in (
            lambda: SaleService(db).confirm_in_transaction(case.tenant_id, foreign.sale_id, confirmed_by_user_id=None),
            lambda: SalePaymentService(db).create_in_transaction(case.tenant_id, foreign.sale_id, _payload(foreign), user_id=None, idempotency_key="p5-foreign"),
        ):
            with pytest.raises(AppError) as error:
                operation()
            assert error.value.code == "sale_not_found"
        SaleService(db).confirm_in_transaction(case.tenant_id, case.sale_id, confirmed_by_user_id=None)
        with pytest.raises(AppError) as error:
            SalePaymentService(db).create_in_transaction(case.tenant_id, case.sale_id, _payload(foreign), user_id=None)
        assert error.value.code == "payment_method_not_found"
        db.rollback()
    with transaction_factory() as observer:
        assert _state(observer, case) == ("draft", 10, 0, 0, 20)
        assert _state(observer, foreign) == ("confirmed", 10, 0, 0, 20)


def test_internal_results_serialize_actor_and_snapshots_before_commit(transaction_factory):
    from app.models.user import User
    from app.schemas.sale import SaleDetailRead

    case = _seed(transaction_factory)
    actor_id = uuid.uuid4()
    with transaction_factory.begin() as db:
        db.add(User(id=actor_id, tenant_id=case.tenant_id, email="p5-actor@example.com",
                    full_name="P.5 Operator", role="contador", is_active=True))
    with transaction_factory() as db:
        sale = SaleService(db).confirm_in_transaction(case.tenant_id, case.sale_id, confirmed_by_user_id=actor_id)
        detail = SaleDetailRead.model_validate(sale)
        assert detail.confirmed_by_user_id == actor_id
        assert detail.confirmed_by_user_name == "P.5 Operator"
        assert detail.confirmed_by_user_email == "p5-actor@example.com"
        payment = SalePaymentService(db).create_in_transaction(
            case.tenant_id, case.sale_id, _payload(case), user_id=actor_id, idempotency_key="p5-actor")
        read_payment = SalePaymentRead.model_validate(payment)
        assert read_payment.created_by_user_name == "P.5 Operator"
        assert read_payment.created_by_user_email == "p5-actor@example.com"
        assert read_payment.payment_method_label_snapshot == "Cash"
        assert read_payment.payment_method_type_snapshot == "cash"
        detail = SaleDetailRead.model_validate(sale)
        assert detail.paid_total_ars == 7 and detail.balance_due_ars == 13
        assert len(detail.payments) == 1
        db.rollback()
    with transaction_factory() as observer:
        assert _state(observer, case) == ("draft", 10, 0, 0, 20)

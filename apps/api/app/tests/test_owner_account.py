"""P.12: derived activity, global balance, independent filters and isolation."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event, select

from app.core.errors import AppError
from app.models.owner import Owner
from app.models.patient import Patient
from app.models.payment import SalePayment
from app.models.sale import Sale
from app.models.tenant_preference import TenantPreference
from app.schemas.payment import SalePaymentCreate
from app.services.payment import SalePaymentService
from app.services.receivables import OwnerReceivablesService
from app.services.sale import SaleService
from app.tests.test_owner_receivables import CUTOFF, _configure, _get, _sale
from app.tests.test_sale_transaction_composition import postgres_transaction_factory, transaction_factory
from app.tests.test_sales import _create, _headers, _owner
from app.tests.test_sale_payments import _method


def _activity(factory, case, **pagination):
    with factory() as db:
        data, meta = OwnerReceivablesService(db).activity(case.tenant_id, case.owner_id,
            page=pagination.get("page", 1), page_size=pagination.get("page_size", 20))
        return data.model_dump(mode="json"), meta


def _pay(factory, case, amount, offset=1):
    with factory() as db:
        payment = SalePaymentService(db).create(case.tenant_id, case.sale_id, SalePaymentCreate(
            payment_method_id=case.method_id, amount_ars=Decimal(amount), received_at=CUTOFF + timedelta(days=offset),
            reference="Transferencia 123", notes="Cobro posterior"), user_id=None)
        return payment.id


@pytest.mark.parametrize("payments,balance", [([], "100.00"), (["30.00"], "70.00"), (["20.00", "30.00"], "50.00"), (["100.00"], "0.00")])
def test_sale_and_payments_explain_current_balance_including_paid_history(transaction_factory, payments, balance):
    case = _sale(transaction_factory)
    _configure(transaction_factory, case.tenant_id)
    payment_ids = [_pay(transaction_factory, case, amount, i + 1) for i, amount in enumerate(payments)]
    activity, meta = _activity(transaction_factory, case)
    events = activity["events"]
    assert activity["tracking_configured"] is True
    assert meta["total"] == len(payments) + 1
    assert [row["type"] for row in events] == ["payment_recorded"] * len(payments) + ["sale_confirmed"]
    assert events[-1]["amount_ars"] == "100.00"
    assert [row["payment_id"] for row in events[:-1]] == [str(x) for x in reversed(payment_ids)]
    assert [row["amount_ars"] for row in events[:-1]] == list(reversed(payments))
    for row in events[:-1]:
        assert row["payment_method_label"] == "Cash" and row["reference"] == "Transferencia 123"
        assert row["notes"] == "Cobro posterior" and row["payment_is_active"] is True
    current, _ = _get(transaction_factory, case)
    assert current["total_outstanding_ars"] == balance
    if balance == "0.00":
        assert current["sales"] == [] and current["open_sales_count"] == 0


def test_void_keeps_original_event_and_adds_reliable_cancellation(transaction_factory):
    case = _sale(transaction_factory)
    _configure(transaction_factory, case.tenant_id)
    payment_id = _pay(transaction_factory, case, "30.01")
    with transaction_factory() as db:
        SalePaymentService(db).void(case.tenant_id, payment_id, reason="Corrección", user_id=None)
    data, meta = _activity(transaction_factory, case)
    assert meta["total"] == 3
    recorded = next(row for row in data["events"] if row["type"] == "payment_recorded")
    voided = next(row for row in data["events"] if row["type"] == "payment_cancelled")
    assert recorded["payment_is_active"] is False
    assert voided["reason"] == "Corrección" and voided["amount_ars"] == "30.01"
    assert voided["payment_id"] == recorded["payment_id"] == str(payment_id)
    assert voided["occurred_at"] != recorded["occurred_at"]
    assert voided["event_id"] != recorded["event_id"]
    assert _get(transaction_factory, case)[0]["total_outstanding_ars"] == "100.00"


def test_reversal_keeps_history_without_inventing_refund_or_credit(transaction_factory):
    case = _sale(transaction_factory, status="draft", confirmed_at=None)
    _configure(transaction_factory, case.tenant_id)
    with transaction_factory() as db:
        SaleService(db).confirm(case.tenant_id, case.sale_id, confirmed_by_user_id=None)
    _pay(transaction_factory, case, "30.00")
    with transaction_factory() as db:
        SaleService(db).reverse(case.tenant_id, case.sale_id, reason="Servicio cancelado", reversed_by_user_id=None)
    data, meta = _activity(transaction_factory, case)
    assert meta["total"] == 3
    reverse = next(row for row in data["events"] if row["type"] == "sale_reversed")
    assert reverse["reason"] == "Servicio cancelado" and reverse["amount_ars"] is None
    assert any(row["type"] == "payment_recorded" and row["payment_is_active"] for row in data["events"])
    assert _get(transaction_factory, case)[0]["sales"] == []


@pytest.mark.parametrize("status", ["draft", "cancelled"])
def test_unconfirmed_sales_never_enter_activity(transaction_factory, status):
    case = _sale(transaction_factory, status=status, confirmed_at=None)
    _configure(transaction_factory, case.tenant_id)
    assert _activity(transaction_factory, case)[0]["events"] == []


@pytest.mark.parametrize("offset,included", [(-1, False), (0, True), (1, True)])
def test_cutoff_is_based_on_confirmation_even_for_later_payments(transaction_factory, offset, included):
    case = _sale(transaction_factory, confirmed_at=CUTOFF + timedelta(microseconds=offset))
    _configure(transaction_factory, case.tenant_id)
    _pay(transaction_factory, case, "30.00", offset=10)
    data, meta = _activity(transaction_factory, case)
    assert meta["total"] == (2 if included else 0)
    assert bool(data["events"]) is included


@pytest.mark.parametrize("configured", [False, True])
def test_null_or_missing_tracking_has_no_activity_or_implicit_configuration(transaction_factory, configured):
    case = _sale(transaction_factory, paid="30.00")
    if configured:
        _configure(transaction_factory, case.tenant_id, None)
    data, meta = _activity(transaction_factory, case)
    assert data["tracking_configured"] is False and data["tracking_started_at"] is None
    assert data["events"] == [] and meta["total"] == 0
    with transaction_factory() as db:
        preferences = db.scalar(select(TenantPreference).where(TenantPreference.tenant_id == case.tenant_id))
        assert (preferences is not None) is configured
        assert preferences is None or preferences.receivables_tracking_started_at is None


def test_archived_owner_and_empty_owner_remain_accessible(transaction_factory):
    case = _sale(transaction_factory, paid="100.00")
    _configure(transaction_factory, case.tenant_id)
    with transaction_factory.begin() as db:
        owner = db.scalar(select(Owner).where(Owner.tenant_id == case.tenant_id, Owner.id == case.owner_id))
        owner.is_active = False
    assert _activity(transaction_factory, case)[1]["total"] == 2
    with transaction_factory.begin() as db:
        empty = Owner(tenant_id=case.tenant_id, full_name="Sin actividad", phone="555")
        db.add(empty); db.flush(); case.owner_id = empty.id
    assert _activity(transaction_factory, case)[0]["events"] == []


def test_activity_is_tenant_scoped_even_with_corrupt_foreign_links(transaction_factory):
    case = _sale(transaction_factory, paid="30.00")
    foreign = _sale(transaction_factory, paid="50.00")
    _configure(transaction_factory, case.tenant_id)
    _configure(transaction_factory, foreign.tenant_id)
    with transaction_factory.begin() as db:
        patient = Patient(tenant_id=foreign.tenant_id, owner_id=foreign.owner_id, name="SECRET PATIENT", species="canine")
        db.add(patient); db.flush()
        own_sale = db.scalar(select(Sale).where(Sale.tenant_id == case.tenant_id, Sale.id == case.sale_id))
        own_sale.patient_id = patient.id; own_sale.patient_name_snapshot = patient.name
        foreign_sale = db.scalar(select(Sale).where(Sale.tenant_id == foreign.tenant_id, Sale.id == foreign.sale_id))
        foreign_sale.owner_id = case.owner_id
        db.add(SalePayment(tenant_id=foreign.tenant_id, sale_id=case.sale_id, payment_method_id=foreign.method_id,
            payment_method_label_snapshot="SECRET PAYMENT", payment_method_type_snapshot="cash", amount_ars=60,
            received_at=CUTOFF, is_active=True))
        own_payment = db.scalar(select(SalePayment).where(SalePayment.tenant_id == case.tenant_id, SalePayment.sale_id == case.sale_id))
        own_payment.payment_method_id = foreign.method_id
        own_payment.payment_method_label_snapshot = "SECRET METHOD"
    data, meta = _activity(transaction_factory, case)
    assert meta["total"] == 2
    assert "SECRET" not in str(data) and str(foreign.sale_id) not in str(data)
    assert all(row["patient_id"] is None and row["patient_name_snapshot"] is None for row in data["events"])
    assert all(row["payment_method_label"] is None for row in data["events"])
    with transaction_factory() as db:
        for tenant_id, owner_id in [(case.tenant_id, foreign.owner_id), (foreign.tenant_id, case.owner_id), (case.tenant_id, uuid.uuid4())]:
            with pytest.raises(AppError) as error:
                OwnerReceivablesService(db).activity(tenant_id, owner_id, page=1, page_size=20)
            assert error.value.status_code == 404


def test_activity_pagination_is_stable_and_independent_of_global_summary(transaction_factory):
    case = _sale(transaction_factory, paid="30.00")
    _configure(transaction_factory, case.tenant_id)
    for _ in range(11):
        _sale(transaction_factory, tenant_id=case.tenant_id, owner_id=case.owner_id, paid="30.00")
    first, meta = _activity(transaction_factory, case, page_size=10)
    second, _ = _activity(transaction_factory, case, page=2, page_size=10)
    third, _ = _activity(transaction_factory, case, page=3, page_size=10)
    assert meta == {"page": 1, "page_size": 10, "total": 24, "total_pages": 3}
    rows = first["events"] + second["events"] + third["events"]
    assert len(rows) == len({row["event_id"] for row in rows}) == 24
    assert first == _activity(transaction_factory, case, page_size=10)[0]
    keys = [(row["occurred_at"], row["event_id"].split(":")[1], row["type"]) for row in rows]
    assert keys == sorted(keys, reverse=True)
    beyond, beyond_meta = _activity(transaction_factory, case, page=9, page_size=10)
    assert beyond["events"] == [] and beyond_meta["total"] == 24
    assert _get(transaction_factory, case, page_size=1)[0]["total_outstanding_ars"] == "840.00"


def test_pending_filters_only_change_list_and_pagination_not_global_summary(transaction_factory):
    case = _sale(transaction_factory, total="100.01", paid="30.00")
    _configure(transaction_factory, case.tenant_id)
    other = _sale(transaction_factory, tenant_id=case.tenant_id, owner_id=case.owner_id, total="200.02", paid="50.00")
    with transaction_factory.begin() as db:
        patient = Patient(tenant_id=case.tenant_id, owner_id=case.owner_id, name="Luna", species="canine")
        db.add(patient); db.flush(); patient_id = patient.id
        first_sale = db.scalar(select(Sale).where(Sale.tenant_id == case.tenant_id, Sale.id == case.sale_id))
        first_sale.sale_date = date(2026, 10, 1); first_sale.patient_id = patient.id
        second_sale = db.scalar(select(Sale).where(Sale.tenant_id == case.tenant_id, Sale.id == other.sale_id))
        second_sale.sale_date = date(2026, 10, 2)
    with transaction_factory() as db:
        service = OwnerReceivablesService(db)
        for filters in [{"date_from": date(2026, 10, 1), "date_to": date(2026, 10, 1)}, {"patient_id": patient_id}]:
            data, meta = service.get(case.tenant_id, case.owner_id, page=1, page_size=1, **filters)
            assert (data.total_outstanding_ars, data.open_sales_count) == (Decimal("220.03"), 2)
            assert meta["total"] == 1 and meta["total_pages"] == 1
            assert data.sales[0].sale_id == case.sale_id
        data, meta = service.get(case.tenant_id, case.owner_id, page=1, page_size=20, patient_id=uuid.uuid4())
        assert not data.sales and meta["total"] == 0 and data.total_outstanding_ars == Decimal("220.03")
        with pytest.raises(AppError) as error:
            service.get(case.tenant_id, case.owner_id, page=1, page_size=20, date_from=date(2026, 10, 2), date_to=date(2026, 10, 1))
        assert error.value.status_code == 422


def test_activity_query_count_stays_constant_as_sales_and_events_grow(transaction_factory):
    case = _sale(transaction_factory, paid="30.00")
    _configure(transaction_factory, case.tenant_id)
    engine = transaction_factory.kw["bind"]
    statements = []
    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    for count in [1, 25]:
        if count > 1:
            for _ in range(count - 1):
                _sale(transaction_factory, tenant_id=case.tenant_id, owner_id=case.owner_id, paid="30.00")
        event.listen(engine, "before_cursor_execute", record)
        try:
            statements.clear()
            data, meta = _activity(transaction_factory, case, page_size=100)
            assert len(data["events"]) == meta["total"] == count * 2
            assert len(statements) == 3
            assert all(sql.lstrip().upper().startswith(("SELECT", "WITH")) for sql in statements)
        finally:
            event.remove(engine, "before_cursor_execute", record)


def test_api_split_confirmation_has_independent_payment_events_and_scoped_access(client, db_session, tenant, other_tenant):
    db_session.add(TenantPreference(tenant_id=tenant.id, currency_code="ARS", locale="es-AR", receivables_tracking_started_at=CUTOFF))
    db_session.commit()
    owner, cash = _owner(client, tenant), _method(client, tenant)
    transfer = _method(client, tenant, label="Transferencia", type="bank_transfer")
    sale = _create(client, tenant, owner_id=owner["id"], items=[{"line_type": "service", "description": "Consulta", "quantity": "1", "unit_price_ars": "100"}])
    confirmed = client.post(f"/api/v1/sales/{sale['id']}/confirm", headers={**_headers(tenant), "Idempotency-Key": "p12-batch"},
        json={"confirm": True, "initial_payments": [{"payment_method_id": cash["id"], "amount_ars": "20.00"}, {"payment_method_id": transfer["id"], "amount_ars": "30.00"}]})
    assert confirmed.status_code == 200, confirmed.text
    url = f"/api/v1/owners/{owner['id']}/receivables"
    response = client.get(url + "/activity", headers=_headers(tenant))
    assert response.status_code == 200, response.text
    events = response.json()["data"]["events"]
    payments = [row for row in events if row["type"] == "payment_recorded"]
    assert len(events) == 3 and len(payments) == 2
    assert {row["amount_ars"] for row in payments} == {"20.00", "30.00"}
    assert {row["payment_method_label"] for row in payments} == {cash["label"], transfer["label"]}
    assert client.get(url, headers=_headers(tenant)).json()["data"]["total_outstanding_ars"] == "50.00"
    assert client.get(url + "/activity", headers=_headers(other_tenant)).status_code == 404
    for params in [{"page": 0}, {"page_size": 0}, {"page_size": 101}]:
        assert client.get(url + "/activity", headers=_headers(tenant), params=params).status_code == 422
    assert client.get(url, headers=_headers(tenant), params={"date_from": "2026-10-02", "date_to": "2026-10-01"}).status_code == 422

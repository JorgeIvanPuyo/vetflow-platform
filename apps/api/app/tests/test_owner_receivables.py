"""P.11 derived balances: cutoff, active payments, pagination and isolation."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event, func, select

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
from app.tests.test_sale_transaction_composition import _seed, postgres_transaction_factory, transaction_factory
from app.tests.test_sales import _create, _headers, _owner
from app.tests.test_sale_payments import _method


CUTOFF = datetime(2026, 10, 2, 13, tzinfo=UTC)


def _configure(factory, tenant_id, cutoff=CUTOFF):
    with factory.begin() as db:
        db.add(TenantPreference(tenant_id=tenant_id, receivables_tracking_started_at=cutoff, currency_code="ARS", locale="es-AR"))


def _sale(factory, *, tenant_id=None, owner_id=None, total="100.00", paid="0.00", status="confirmed", confirmed_at=CUTOFF, active=True):
    case = _seed(factory, tenant_id=tenant_id)
    with factory.begin() as db:
        sale = SaleService(db).get(case.tenant_id, case.sale_id)
        if owner_id is not None:
            sale.owner_id = owner_id
            case.owner_id = owner_id
        sale.subtotal_ars = sale.total_ars = Decimal(total)
        sale.items[0].unit_price_ars = Decimal(total) / 2
        sale.items[0].line_subtotal_ars = sale.items[0].line_total_ars = Decimal(total)
        sale.status = status
        sale.confirmed_at = confirmed_at
        if Decimal(paid) > 0:
            payment = SalePayment(tenant_id=case.tenant_id, sale_id=case.sale_id, payment_method_id=case.method_id,
                payment_method_label_snapshot="Cash", payment_method_type_snapshot="cash",
                amount_ars=Decimal(paid), received_at=CUTOFF, is_active=active,
                voided_at=None if active else CUTOFF, void_reason=None if active else "Anulado")
            db.add(payment)
    return case


def _get(factory, case, *, page=1, page_size=20):
    with factory() as db:
        data, meta = OwnerReceivablesService(db).get(case.tenant_id, case.owner_id, page=page, page_size=page_size)
        return data.model_dump(mode="json"), meta


@pytest.mark.parametrize("configured", [False, True])
def test_missing_or_null_cutoff_never_infers_historical_debt(transaction_factory, configured):
    case = _sale(transaction_factory, confirmed_at=datetime(2020, 1, 1, tzinfo=UTC))
    if configured:
        _configure(transaction_factory, case.tenant_id, None)
    data, meta = _get(transaction_factory, case)
    assert data["tracking_configured"] is False and data["tracking_started_at"] is None
    assert (data["total_outstanding_ars"], data["open_sales_count"], data["sales"]) == ("0.00", 0, [])
    assert meta == {"page": 1, "page_size": 20, "total": 0, "total_pages": 0}
    with transaction_factory() as db:
        assert db.scalar(select(func.count(TenantPreference.id)).where(TenantPreference.tenant_id == case.tenant_id)) == int(configured)
        sale = SaleService(db).get(case.tenant_id, case.sale_id)
        assert sale.status == "confirmed" and sale.total_ars == 100 and not sale.payments


def test_configured_owner_without_sales_has_legitimate_zero_balance(transaction_factory):
    case = _seed(transaction_factory)
    _configure(transaction_factory, case.tenant_id)
    with transaction_factory.begin() as db:
        owner = Owner(tenant_id=case.tenant_id, full_name="Sin ventas", phone="555")
        db.add(owner)
        db.flush()
        case.owner_id = owner.id
    data, _ = _get(transaction_factory, case)
    assert data["tracking_configured"] is True
    assert (data["total_outstanding_ars"], data["open_sales_count"], data["sales"]) == ("0.00", 0, [])


@pytest.mark.parametrize("total,paid,status,active,offset,expected", [
    ("100.00", "0.00", "confirmed", True, 0, "100.00"),
    ("100.00", "30.00", "confirmed", True, 1, "70.00"),
    ("100.00", "100.00", "confirmed", True, 1, "0.00"),
    ("0.00", "0.00", "confirmed", True, 1, "0.00"),
    ("100.00", "30.00", "confirmed", False, 1, "100.00"),
    ("100.00", "0.00", "confirmed", True, -1, "0.00"),
    ("100.00", "0.00", "draft", True, 1, "0.00"),
    ("100.00", "0.00", "cancelled", True, 1, "0.00"),
    ("100.00", "0.00", "reversed", True, 1, "0.00"),
    ("100.00", "30.00", "reversed", True, 1, "0.00"),
    ("100.00", "130.00", "confirmed", True, 1, "0.00"),
    ("0.13", "0.03", "confirmed", True, 1, "0.10"),
])
def test_eligibility_and_amounts_match_canonical_sale_semantics(transaction_factory, total, paid, status, active, offset, expected):
    case = _sale(transaction_factory, total=total, paid=paid, status=status, active=active, confirmed_at=CUTOFF + timedelta(seconds=offset))
    _configure(transaction_factory, case.tenant_id)
    data, meta = _get(transaction_factory, case)
    assert data["total_outstanding_ars"] == expected
    included = Decimal(expected) > 0
    assert data["open_sales_count"] == meta["total"] == len(data["sales"]) == int(included)
    if included:
        row = data["sales"][0]
        with transaction_factory() as db:
            detail = SaleService(db).get(case.tenant_id, case.sale_id)
            assert row["sale_id"] == str(detail.id)
            assert Decimal(row["paid_total_ars"]) == detail.paid_total_ars
            assert Decimal(row["balance_due_ars"]) == detail.balance_due_ars
            assert row["payment_status"] == detail.payment_status


def test_global_summary_pagination_and_order_are_stable(transaction_factory):
    first = _sale(transaction_factory, total="1.13", paid="0.03")
    _configure(transaction_factory, first.tenant_id)
    ids = [first.sale_id]
    for _ in range(36):
        ids.append(_sale(transaction_factory, tenant_id=first.tenant_id, owner_id=first.owner_id, total="1.13", paid="0.03").sale_id)
    # Same tenant, other owner; foreign tenant; paid; pre-cutoff all excluded.
    _sale(transaction_factory, tenant_id=first.tenant_id, total="900.00")
    _sale(transaction_factory, total="900.00")
    _sale(transaction_factory, tenant_id=first.tenant_id, owner_id=first.owner_id, paid="100.00")
    _sale(transaction_factory, tenant_id=first.tenant_id, owner_id=first.owner_id, confirmed_at=CUTOFF - timedelta(seconds=1))
    seen = []
    for page, length in [(1, 20), (2, 17), (3, 0)]:
        data, meta = _get(transaction_factory, first, page=page)
        assert (data["total_outstanding_ars"], data["open_sales_count"]) == ("40.70", 37)
        assert meta == {"page": page, "page_size": 20, "total": 37, "total_pages": 2}
        assert len(data["sales"]) == length
        seen.extend(row["sale_id"] for row in data["sales"])
    assert seen == [str(identity) for identity in sorted(ids, reverse=True)]
    assert len(set(seen)) == 37


def test_archived_owner_remains_visible_and_tenant_cutoffs_are_independent(transaction_factory):
    first, second = _sale(transaction_factory), _sale(transaction_factory)
    _configure(transaction_factory, first.tenant_id)
    _configure(transaction_factory, second.tenant_id, CUTOFF + timedelta(days=1))
    with transaction_factory.begin() as db:
        owner = db.scalar(select(Owner).where(Owner.tenant_id == first.tenant_id, Owner.id == first.owner_id))
        owner.is_active = False
    assert _get(transaction_factory, first)[0]["total_outstanding_ars"] == "100.00"
    assert _get(transaction_factory, second)[0]["total_outstanding_ars"] == "0.00"
    with transaction_factory() as db:
        for tenant_id, owner_id in [(second.tenant_id, first.owner_id), (first.tenant_id, second.owner_id), (first.tenant_id, uuid.uuid4())]:
            with pytest.raises(AppError) as error:
                OwnerReceivablesService(db).get(tenant_id, owner_id, page=1, page_size=20)
            assert (error.value.status_code, error.value.code) == (404, "owner_not_found")


def test_corrupt_foreign_payments_sales_and_patient_links_do_not_leak(transaction_factory):
    first = _sale(transaction_factory, paid="30.00")
    second = _sale(transaction_factory)
    _configure(transaction_factory, first.tenant_id)
    _configure(transaction_factory, second.tenant_id)
    with transaction_factory.begin() as db:
        db.add(SalePayment(tenant_id=second.tenant_id, sale_id=first.sale_id, payment_method_id=second.method_id,
            payment_method_label_snapshot="Foreign", payment_method_type_snapshot="cash", amount_ars=70, received_at=CUTOFF, is_active=True))
        foreign_patient = Patient(tenant_id=second.tenant_id, owner_id=second.owner_id, name="Secret patient", species="canine")
        db.add(foreign_patient)
        db.flush()
        own_sale = SaleService(db).get(first.tenant_id, first.sale_id)
        own_sale.patient_id = foreign_patient.id
        own_sale.patient_name_snapshot = foreign_patient.name
        foreign_sale = SaleService(db).get(second.tenant_id, second.sale_id)
        foreign_sale.owner_id = first.owner_id
    data, _ = _get(transaction_factory, first)
    assert data["total_outstanding_ars"] == "70.00" and data["open_sales_count"] == 1
    assert data["sales"][0]["paid_total_ars"] == "30.00"
    assert data["sales"][0]["patient_id"] is None and data["sales"][0]["patient_name_snapshot"] is None
    assert str(second.sale_id) not in str(data) and "Secret patient" not in str(data)
    assert _get(transaction_factory, second)[0]["open_sales_count"] == 0


def test_query_count_is_constant_without_payment_or_patient_n_plus_one(transaction_factory):
    first = _sale(transaction_factory, paid="30.00")
    _configure(transaction_factory, first.tenant_id)
    statements = []
    engine = transaction_factory.kw["bind"]
    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    for size in [1, 30]:
        if size > 1:
            for _ in range(size - 1):
                _sale(transaction_factory, tenant_id=first.tenant_id, owner_id=first.owner_id, paid="30.00")
        event.listen(engine, "before_cursor_execute", record)
        try:
            statements.clear()
            data, _ = _get(transaction_factory, first, page_size=100)
            assert len(data["sales"]) == size
            assert len(statements) == 3  # Owner, preferences, one summary/page SQL.
            assert all(statement.lstrip().upper().startswith(("SELECT", "WITH")) for statement in statements)
        finally:
            event.remove(engine, "before_cursor_execute", record)


def test_api_tracks_initial_later_void_and_reversed_payments_dynamically(client, db_session, tenant, other_tenant):
    db_session.add(TenantPreference(tenant_id=tenant.id, currency_code="ARS", locale="es-AR", receivables_tracking_started_at=CUTOFF))
    db_session.commit()
    owner = _owner(client, tenant)
    method = _method(client, tenant)
    sale = _create(client, tenant, owner_id=owner["id"], items=[{"line_type": "service", "description": "Consulta", "quantity": "1", "unit_price_ars": "100"}])
    sale_url = f"/api/v1/sales/{sale['id']}"
    url = f"/api/v1/owners/{owner['id']}/receivables"
    assert client.get(url, headers=_headers(other_tenant)).status_code == 404
    assert client.get(url, headers=_headers(tenant)).json()["data"]["open_sales_count"] == 0
    assert client.post(sale_url + "/confirm", headers={**_headers(tenant), "Idempotency-Key": "initial"},
        json={"confirm": True, "initial_payment": {"payment_method_id": method["id"], "amount_ars": "30"}}).status_code == 200
    def get(expected, count):
        response = client.get(url, headers=_headers(tenant))
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert (data["total_outstanding_ars"], data["open_sales_count"]) == (expected, count)
        return data
    get("70.00", 1)
    payments = []
    for amount, balance, count in [("20", "50.00", 1), ("50", "0.00", 0)]:
        paid = client.post(sale_url + "/payments", headers=_headers(tenant), json={"payment_method_id": method["id"], "amount_ars": amount, "received_at": CUTOFF.isoformat()})
        assert paid.status_code == 201, paid.text
        payments.append(paid.json()["data"])
        get(balance, count)
    void = client.post(f"/api/v1/sale-payments/{payments[-1]['id']}/void", headers=_headers(tenant), json={"reason": "Corrección"})
    assert void.status_code == 200, void.text
    get("50.00", 1)
    assert client.patch(f"/api/v1/owners/{owner['id']}", headers=_headers(tenant), json={"is_active": False}).status_code == 200
    get("50.00", 1)
    assert client.post(sale_url + "/reverse", headers=_headers(tenant), json={"reason": "Corrección"}).status_code == 200
    assert get("0.00", 0)["sales"] == []


def test_batch_is_one_receivable_with_the_sum_of_active_payments(client, db_session, tenant):
    db_session.add(TenantPreference(tenant_id=tenant.id, currency_code="ARS", locale="es-AR", receivables_tracking_started_at=CUTOFF))
    db_session.commit()
    owner, method = _owner(client, tenant), _method(client, tenant)
    other_method = _method(client, tenant, label="Transferencia", type="bank_transfer")
    sale = _create(client, tenant, owner_id=owner["id"], items=[{"line_type": "service", "description": "Consulta", "quantity": "1", "unit_price_ars": "100"}])
    result = client.post(f"/api/v1/sales/{sale['id']}/confirm", headers={**_headers(tenant), "Idempotency-Key": "batch"},
        json={"confirm": True, "initial_payments": [{"payment_method_id": selected["id"], "amount_ars": value} for selected, value in [(method, "20"), (other_method, "30")]]})
    assert result.status_code == 200, result.text
    response = client.get(f"/api/v1/owners/{owner['id']}/receivables", headers=_headers(tenant))
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert (data["total_outstanding_ars"], data["open_sales_count"]) == ("50.00", 1)
    assert data["sales"][0]["paid_total_ars"] == "50.00"


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}])
def test_api_validates_pagination(client, tenant, params):
    owner = _owner(client, tenant)
    response = client.get(f"/api/v1/owners/{owner['id']}/receivables", headers=_headers(tenant), params=params)
    assert response.status_code == 422


def test_postgresql_aggregate_preserves_cents_beyond_one_sale_numeric_limit(postgres_transaction_factory):
    from app.core.sale_limits import SALE_PRICE_MAX
    from app.schemas.sale import SaleCreate

    factory = postgres_transaction_factory
    first = _seed(factory)
    _configure(factory, first.tenant_id)
    with factory() as db:
        for paid in ["0.01", "0.02"]:
            sales = SaleService(db)
            sale = sales.create(first.tenant_id, SaleCreate.model_validate({
                "owner_id": first.owner_id, "sale_date": "2026-10-02",
                "items": [
                    {"line_type": "service", "description": "Máximo P.2", "quantity": "100", "unit_price_ars": str(SALE_PRICE_MAX)},
                    {"line_type": "service", "description": "Centavos", "quantity": "1", "unit_price_ars": "0.99"},
                ],
            }), created_by_user_id=None)
            sales.confirm(first.tenant_id, sale.id, confirmed_by_user_id=None)
            SalePaymentService(db).create(first.tenant_id, sale.id,
                SalePaymentCreate(payment_method_id=first.method_id, amount_ars=paid, received_at=CUTOFF), user_id=None)
    data, _ = _get(factory, first)
    assert data["total_outstanding_ars"] == "199999999999999.95"

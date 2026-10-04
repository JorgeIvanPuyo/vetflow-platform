"""P.12.1 signals derive from P.11, including all of an owner's patients."""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event, select

from app.models.owner import Owner
from app.models.patient import Patient
from app.models.payment import SalePayment
from app.models.sale import Sale
from app.models.tenant_preference import TenantPreference
from app.repositories.receivables import ReceivablesRepository
from app.schemas.payment import SalePaymentCreate
from app.services.owner import OwnerService
from app.services.patient import PatientService
from app.services.payment import SalePaymentService
from app.services.sale import SaleService
from app.tests.test_owner_receivables import CUTOFF, _configure, _get, _sale
from app.tests.test_sale_transaction_composition import postgres_transaction_factory, transaction_factory
from app.tests.test_sales import _create, _headers, _owner
from app.tests.test_sale_payments import _method


def _patients(factory, case, count=3):
    with factory.begin() as db:
        patients = [Patient(tenant_id=case.tenant_id, owner_id=case.owner_id,
                            name=f"Pet {i}", species="canine") for i in range(count)]
        db.add_all(patients); db.flush()
        return [patient.id for patient in patients]


def _signals(factory, case):
    with factory() as db:
        owners = OwnerService(db)
        owner = owners.get_owner(case.tenant_id, case.owner_id)
        single = owners.build_owner_response(case.tenant_id, owner)
        listed, _ = owners.list_owners(case.tenant_id)
        row = next(row for row in owners.build_owner_list_response(case.tenant_id, listed) if row["id"] == str(case.owner_id))
        assert single["has_active_receivable"] is row["has_active_receivable"]
        patients = PatientService(db)
        pets, _ = patients.list_patients(case.tenant_id, owner_id=case.owner_id)
        for pet in pets:
            detail = patients.build_patient_response(pet)
            assert detail["owner_has_active_receivable"] is single["has_active_receivable"]
        for pet in patients.build_patient_list_response(pets):
            assert pet["owner_has_active_receivable"] is single["has_active_receivable"]
        return single["has_active_receivable"]


@pytest.mark.parametrize("configured", [False, True])
def test_tracking_missing_or_null_has_no_signal_and_does_not_configure_it(transaction_factory, configured):
    case = _sale(transaction_factory)
    _patients(transaction_factory, case)
    if configured:
        _configure(transaction_factory, case.tenant_id, None)
    assert _signals(transaction_factory, case) is False
    with transaction_factory() as db:
        preference = db.scalar(select(TenantPreference).where(TenantPreference.tenant_id == case.tenant_id))
        assert (preference is not None) is configured
        assert preference is None or preference.receivables_tracking_started_at is None


@pytest.mark.parametrize("total,paid,status,offset,expected", [
    ("100.00", "0.00", "confirmed", 0, True),
    ("100.00", "30.00", "confirmed", 1, True),
    ("100.00", "100.00", "confirmed", 1, False),
    ("100.00", "130.00", "confirmed", 1, False),
    ("0.00", "0.00", "confirmed", 1, False),
    ("0.01", "0.00", "confirmed", 0, True),
    ("100.00", "0.00", "confirmed", -1, False),
    ("100.00", "0.00", "draft", 1, False),
    ("100.00", "0.00", "cancelled", 1, False),
    ("100.00", "0.00", "reversed", 1, False),
])
def test_owner_and_all_patients_match_positive_p11_balance(transaction_factory, total, paid, status, offset, expected):
    case = _sale(transaction_factory, total=total, paid=paid, status=status,
                 confirmed_at=CUTOFF + timedelta(microseconds=offset))
    _configure(transaction_factory, case.tenant_id)
    _patients(transaction_factory, case)
    assert _signals(transaction_factory, case) is expected
    assert (Decimal(_get(transaction_factory, case)[0]["total_outstanding_ars"]) > 0) is expected


def test_multiple_sales_do_not_net_an_overpayment_against_another_debt(transaction_factory):
    case = _sale(transaction_factory, total="100.00", paid="130.00")
    _configure(transaction_factory, case.tenant_id)
    _sale(transaction_factory, tenant_id=case.tenant_id, owner_id=case.owner_id, total="0.01")
    _patients(transaction_factory, case)
    assert _signals(transaction_factory, case) is True
    assert _get(transaction_factory, case)[0]["total_outstanding_ars"] == "0.01"


def test_payment_void_and_reversal_revalidate_without_persisting_a_signal(transaction_factory):
    case = _sale(transaction_factory, status="draft", confirmed_at=None)
    _configure(transaction_factory, case.tenant_id)
    with transaction_factory() as db:
        SaleService(db).confirm(case.tenant_id, case.sale_id, confirmed_by_user_id=None)
    _patients(transaction_factory, case)
    assert _signals(transaction_factory, case) is True
    with transaction_factory() as db:
        payment = SalePaymentService(db).create(case.tenant_id, case.sale_id, SalePaymentCreate(
            payment_method_id=case.method_id, amount_ars=Decimal("100.00"), received_at=CUTOFF), user_id=None)
        payment_id = payment.id
    assert _signals(transaction_factory, case) is False
    with transaction_factory() as db:
        SalePaymentService(db).void(case.tenant_id, payment_id, reason="Corrección", user_id=None)
    assert _signals(transaction_factory, case) is True
    with transaction_factory() as db:
        SaleService(db).reverse(case.tenant_id, case.sale_id, reason="Cancelado", reversed_by_user_id=None)
    assert _signals(transaction_factory, case) is False
    assert "has_active_receivable" not in Owner.__table__.c
    assert "owner_has_active_receivable" not in Patient.__table__.c


def test_archived_owner_with_debt_and_its_patients_keep_the_signal(transaction_factory):
    case = _sale(transaction_factory)
    _configure(transaction_factory, case.tenant_id)
    _patients(transaction_factory, case)
    with transaction_factory.begin() as db:
        owner = db.scalar(select(Owner).where(Owner.tenant_id == case.tenant_id, Owner.id == case.owner_id))
        owner.is_active = False
    assert _signals(transaction_factory, case) is True


def test_signals_scope_owner_sales_payments_and_corrupt_patient_links(transaction_factory):
    case = _sale(transaction_factory, paid="100.00")
    foreign = _sale(transaction_factory)
    _configure(transaction_factory, case.tenant_id)
    _configure(transaction_factory, foreign.tenant_id)
    with transaction_factory.begin() as db:
        foreign_sale = db.scalar(select(Sale).where(Sale.tenant_id == foreign.tenant_id, Sale.id == foreign.sale_id))
        foreign_sale.owner_id = case.owner_id
        patient = Patient(tenant_id=case.tenant_id, owner_id=foreign.owner_id, name="Corrupt link", species="canine")
        db.add(patient); db.flush(); patient_id = patient.id
    assert _signals(transaction_factory, case) is False
    with transaction_factory() as db:
        signals = ReceivablesRepository(db).owner_signals(case.tenant_id, {case.owner_id, foreign.owner_id, uuid.uuid4()})
        assert set(signals) == {case.owner_id}
        service = PatientService(db)
        data = service.build_patient_response(service.get_patient(case.tenant_id, patient_id))
        assert data["owner_name"] is None and data["owner_has_active_receivable"] is False
    # A payment from another clinic cannot hide our debt.
    unpaid = _sale(transaction_factory, tenant_id=case.tenant_id, owner_id=case.owner_id)
    with transaction_factory.begin() as db:
        db.add(SalePayment(tenant_id=foreign.tenant_id, sale_id=unpaid.sale_id,
            payment_method_id=foreign.method_id, payment_method_label_snapshot="Foreign",
            payment_method_type_snapshot="cash", amount_ars=100, received_at=CUTOFF, is_active=True))
    assert _signals(transaction_factory, case) is True


def test_empty_lookup_does_not_execute_sql(transaction_factory):
    with transaction_factory() as db:
        def unexpected(*args):
            raise AssertionError("Empty lookup executed SQL")
        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", unexpected)
        try:
            assert ReceivablesRepository(db).owner_signals(uuid.uuid4(), set()) == {}
        finally:
            event.remove(engine, "before_cursor_execute", unexpected)


def test_query_counts_are_constant_for_lists_and_details(transaction_factory):
    case = _sale(transaction_factory)
    _configure(transaction_factory, case.tenant_id)
    patient_id = _patients(transaction_factory, case, count=1)[0]
    engine = transaction_factory.kw["bind"]
    statements = []
    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    def measure(kind):
        with transaction_factory() as db:
            statements.clear()
            event.listen(engine, "before_cursor_execute", record)
            try:
                owners, patients = OwnerService(db), PatientService(db)
                if kind == "owners":
                    rows, _ = owners.list_owners(case.tenant_id, page_size=100)
                    owners.build_owner_list_response(case.tenant_id, rows)
                elif kind == "patients":
                    rows, _ = patients.list_patients(case.tenant_id, page_size=100)
                    patients.build_patient_list_response(rows)
                elif kind == "owner":
                    owners.build_owner_response(case.tenant_id, owners.get_owner(case.tenant_id, case.owner_id))
                else:
                    patients.build_patient_response(patients.get_patient(case.tenant_id, patient_id))
            finally:
                event.remove(engine, "before_cursor_execute", record)
            assert all(sql.lstrip().upper().startswith(("SELECT", "WITH")) for sql in statements)
            return len(statements)
    expected = {"owners": 3, "patients": 3, "owner": 2, "patient": 2}
    assert {kind: measure(kind) for kind in expected} == expected
    for _ in range(24):
        another = _sale(transaction_factory, tenant_id=case.tenant_id)
        _patients(transaction_factory, another, count=1)
    assert {kind: measure(kind) for kind in expected} == expected


def test_api_additive_flags_filters_and_foreign_resource_404(client, db_session, tenant, other_tenant):
    db_session.add(TenantPreference(tenant_id=tenant.id, currency_code="ARS", locale="es-AR",
                                   receivables_tracking_started_at=CUTOFF))
    db_session.commit()
    owner = _owner(client, tenant)
    sale = _create(client, tenant, owner_id=owner["id"], items=[{
        "line_type": "service", "description": "Consulta", "quantity": "1", "unit_price_ars": "100"}])
    assert client.post(f"/api/v1/sales/{sale['id']}/confirm", headers=_headers(tenant), json={"confirm": True}).status_code == 200
    pets = [client.post("/api/v1/patients", headers=_headers(tenant), json={
        "owner_id": owner["id"], "name": name, "species": "canine"}).json()["data"] for name in ["Luna", "Milo", "Nina"]]
    assert all(pet["owner_has_active_receivable"] is True for pet in pets)
    owners = client.get("/api/v1/owners", headers=_headers(tenant), params={"search": owner["full_name"], "page_size": 1}).json()
    assert owners["data"][0]["has_active_receivable"] is True
    patients = client.get("/api/v1/patients", headers=_headers(tenant), params={"owner_id": owner["id"], "page_size": 2}).json()
    assert len(patients["data"]) == 2 and patients["meta"]["total"] == 3
    assert all(pet["owner_has_active_receivable"] is True for pet in patients["data"])
    assert client.get(f"/api/v1/owners/{owner['id']}", headers=_headers(other_tenant)).status_code == 404
    assert client.get(f"/api/v1/patients/{pets[0]['id']}", headers=_headers(other_tenant)).status_code == 404
    method = _method(client, tenant)
    response = client.post(f"/api/v1/sales/{sale['id']}/payments", headers=_headers(tenant), json={
        "payment_method_id": method["id"], "amount_ars": "100.00", "received_at": CUTOFF.isoformat()})
    assert response.status_code == 201, response.text
    assert client.get(f"/api/v1/owners/{owner['id']}", headers=_headers(tenant)).json()["data"]["has_active_receivable"] is False
    assert all(client.get(f"/api/v1/patients/{pet['id']}", headers=_headers(tenant)).json()["data"]["owner_has_active_receivable"] is False for pet in pets)

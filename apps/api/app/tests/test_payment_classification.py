"""F/C.0 reuses the existing operational type, without a second stored category."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.payment import PaymentMethod
from app.models.tenant import Tenant
from app.tests.test_sale_payments import _headers, _method, _pay, _sale
from app.tests.test_payment_reports import report

TYPES = ['cash', 'bank_transfer', 'debit_card', 'credit_card', 'digital_wallet', 'other']


@pytest.mark.parametrize('kind', TYPES)
def test_explicit_type_roundtrips_create_read_and_filter(client, tenant, kind):
    # A misleading human label cannot classify a method.
    method = _method(client, tenant, type=kind, label='EFECTIVO / QR / TRANSFERENCIA')
    response = client.get(f"/api/v1/payment-methods/{method['id']}", headers=_headers(tenant))
    assert response.status_code == 200 and response.json()['data']['type'] == kind
    assert 'payment_kind' not in response.json()['data']
    listed = client.get('/api/v1/payment-methods', headers=_headers(tenant), params={'type': kind}).json()['data']
    assert [m['id'] for m in listed] == [method['id']]


@pytest.mark.parametrize('kind', TYPES)
def test_unused_method_classification_can_be_edited(client, tenant, kind):
    method = _method(client, tenant, type='other')
    response = client.patch(f"/api/v1/payment-methods/{method['id']}", headers=_headers(tenant), json={'type': kind})
    assert response.status_code == 200 and response.json()['data']['type'] == kind


@pytest.mark.parametrize('kind', TYPES)
def test_rename_and_inactivation_preserve_type(client, tenant, kind):
    method = _method(client, tenant, type=kind, label='QR LIDA')
    for change in [{'label': 'QR MERCADO PAGO LIDA'}, {'is_active': False}]:
        response = client.patch(f"/api/v1/payment-methods/{method['id']}", headers=_headers(tenant), json=change)
        assert response.status_code == 200 and response.json()['data']['type'] == kind
    assert response.json()['data']['is_active'] is False


def test_existing_contract_without_payment_kind_remains_usable(client, tenant):
    method = _method(client, tenant, type='other')
    response = _pay(client, tenant, _sale(client, tenant), method)
    assert response.status_code == 201
    assert response.json()['data']['payment_method_type_snapshot'] == 'other'
    assert report(client, tenant)['data']['summary']['payment_count'] == 1


@pytest.mark.parametrize('payload', [{'type': 'crypto'}, {'type': 'card'}, {'type': None}, {}])
def test_invalid_null_and_missing_creation_type_are_rejected(client, tenant, payload):
    response = client.post('/api/v1/payment-methods', headers=_headers(tenant), json={'label': 'QR', **payload})
    assert response.status_code == 422


@pytest.mark.parametrize('value', ['crypto', 'electronic_other', None])
def test_invalid_update_type_is_rejected_and_preserves_method(client, tenant, value):
    method = _method(client, tenant, type='digital_wallet')
    assert client.patch(f"/api/v1/payment-methods/{method['id']}", headers=_headers(tenant), json={'type': value}).status_code == 422
    assert client.get(f"/api/v1/payment-methods/{method['id']}", headers=_headers(tenant)).json()['data']['type'] == 'digital_wallet'


def test_classification_cannot_be_read_or_changed_across_tenants(client, tenant, other_tenant):
    local = _method(client, tenant, type='cash')
    foreign = _method(client, other_tenant, type='bank_transfer')
    assert client.get(f"/api/v1/payment-methods/{foreign['id']}", headers=_headers(tenant)).status_code == 404
    assert client.patch(f"/api/v1/payment-methods/{foreign['id']}", headers=_headers(tenant), json={'type': 'cash'}).status_code == 404
    assert client.get('/api/v1/payment-methods?type=bank_transfer', headers=_headers(tenant)).json()['data'] == []
    assert client.get(f"/api/v1/payment-methods/{local['id']}", headers=_headers(other_tenant)).status_code == 404
    assert client.get(f"/api/v1/payment-methods/{foreign['id']}", headers=_headers(other_tenant)).json()['data']['type'] == 'bank_transfer'


def test_payments_unchanged_and_reports_keep_methods_separate_after_rename_inactivation(client, db_session, tenant):
    sale = _sale(client, tenant)
    methods = [_method(client, tenant, label=label, type='digital_wallet') for label in ['QR Juliana', 'QR Lida']]
    payments = [_pay(client, tenant, sale, method, '20.00').json()['data'] for method in methods]
    before = report(client, tenant)['data']
    assert len(before['summary']['by_method']) == 2
    for method in methods:
        response = client.patch(f"/api/v1/payment-methods/{method['id']}", headers=_headers(tenant), json={'label': method['label'] + ' Mercado Pago', 'is_active': False})
        assert response.status_code == 200 and response.json()['data']['type'] == 'digital_wallet'
        assert client.patch(f"/api/v1/payment-methods/{method['id']}", headers=_headers(tenant), json={'type': 'cash'}).status_code == 409
    after = report(client, tenant)['data']
    assert after['payments'] == before['payments']
    assert after['summary']['total_amount_ars'] == before['summary']['total_amount_ars'] == '40.00'
    assert after['summary']['payment_count'] == 2
    assert {g['payment_method_id'] for g in after['summary']['by_method']} == {m['id'] for m in methods}
    assert all(g['is_active'] is False for g in after['summary']['by_method'])
    history = client.get(f"/api/v1/sales/{sale['id']}/payments", headers=_headers(tenant)).json()['data']
    assert sorted(history, key=lambda p: p['id']) == sorted(payments, key=lambda p: p['id'])


def test_postgres_existing_classification_constraints(postgres_test_session_factory):
    with postgres_test_session_factory.kw['bind'].connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode='create_savepoint') as db:
                tenant = Tenant(name='F/C.0 test');db.add(tenant);db.flush()
                for kind in TYPES:
                    db.add(PaymentMethod(tenant_id=tenant.id, label=kind, normalized_label=kind, type=kind, is_active=True))
                db.flush()
                assert set(db.scalars(select(PaymentMethod.type).where(PaymentMethod.tenant_id == tenant.id))) == set(TYPES)
                for invalid in [None, 'card', 'electronic_other', 'invalid']:
                    with pytest.raises(IntegrityError):
                        with db.begin_nested():
                            db.add(PaymentMethod(tenant_id=tenant.id, label='invalid', normalized_label='invalid', type=invalid, is_active=True));db.flush()
                assert len(list(db.scalars(select(PaymentMethod).where(PaymentMethod.tenant_id == tenant.id)))) == 6
        finally: transaction.rollback()

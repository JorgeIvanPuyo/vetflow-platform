from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.models.payment import PaymentMethod, SalePayment
from app.models.sale import Sale
from app.models.tenant import Tenant
from app.models.tenant_preference import TenantPreference
from app.models.user import User
from app.services.payment_report import PaymentReportService
from app.tests.test_sale_payments import _headers, _method, _pay, _sale
from app.tests.test_sales import _patient, _owner

URL = '/api/v1/reports/payments'
DAY = '2026-08-09'


def report(client, tenant, **params):
    response = client.get(URL, headers=_headers(tenant), params={'date_from': DAY, 'date_to': DAY, **params})
    assert response.status_code == 200, response.text
    return response.json()


def paid(client, tenant, sale, method, amount='10.00', **overrides):
    response = _pay(client, tenant, sale, method, amount, **overrides)
    assert response.status_code == 201, response.text
    return response.json()['data']


def test_one_active_payment_and_detail(client, tenant):
    sale, method = _sale(client, tenant), _method(client, tenant)
    payment = paid(client, tenant, sale, method)
    result = report(client, tenant)
    assert result['data']['summary']['total_amount_ars'] == '10.00'
    assert result['data']['summary']['payment_count'] == 1
    row = result['data']['payments'][0]
    assert row['payment_id'] == payment['id'] and row['sale_id'] == sale['id']
    assert row['owner_name'] == sale['owner_name_snapshot'] and row['reference'] == 'REF-1'
    assert row['received_at'].endswith('Z') and row['created_by_user_id'] is None


def test_three_methods_split_and_repeated_method(client, tenant):
    sale = _sale(client, tenant)
    methods = [_method(client, tenant, label=label, type=kind) for label, kind in [('Efectivo', 'cash'), ('Transferencia', 'bank_transfer'), ('QR Juliana', 'digital_wallet')]]
    for method, amount in zip(methods, ['20.00', '30.00', '40.00']): paid(client, tenant, sale, method, amount)
    paid(client, tenant, sale, methods[0], '10.00')
    summary = report(client, tenant)['data']['summary']
    assert summary['payment_count'] == 4 and summary['total_amount_ars'] == '100.00'
    groups = {g['payment_method_id']: g for g in summary['by_method']}
    assert groups[methods[0]['id']]['payment_count'] == 2
    assert [groups[m['id']]['amount_ars'] for m in methods] == ['30.00', '30.00', '40.00']
    assert Decimal(summary['total_amount_ars']) == sum(Decimal(g['amount_ars']) for g in groups.values())


def test_divided_checkout_payments_are_counted_individually(client, tenant):
    sale = _sale(client, tenant, status='draft')
    owner = _owner(client, tenant)
    assert client.patch(f"/api/v1/sales/{sale['id']}", headers=_headers(tenant), json={'owner_id': owner['id']}).status_code == 200
    methods = [_method(client, tenant, label=label) for label in ['Caja', 'QR', 'Banco']]
    response = client.post(f"/api/v1/sales/{sale['id']}/confirm", headers={**_headers(tenant), 'Idempotency-Key': 'p13-divided-checkout'}, json={
        'confirm': True, 'initial_payments': [{'payment_method_id': m['id'], 'amount_ars': a, 'received_at': f'{DAY}T12:00:00Z'} for m, a in zip(methods, ['20.00', '30.00', '50.00'])],
    })
    assert response.status_code == 200, response.text
    summary = report(client, tenant)['data']['summary']
    assert summary['payment_count'] == 3 and summary['total_amount_ars'] == '100.00'


def test_later_receivable_payment_uses_received_not_sale_or_cutoff(client, db_session, tenant):
    sale, method = _sale(client, tenant), _method(client, tenant)
    prefs = db_session.scalar(select(TenantPreference).where(TenantPreference.tenant_id == tenant.id))
    prefs.receivables_tracking_started_at = datetime(2026, 10, 1, tzinfo=UTC)
    paid(client, tenant, sale, method, received_at='2026-08-20T12:00:00Z')
    assert report(client, tenant)['data']['summary']['payment_count'] == 0
    assert report(client, tenant, date_from='2026-08-20', date_to='2026-08-20')['data']['summary']['payment_count'] == 1


def test_voided_payment_excluded_from_every_part(client, tenant):
    sale, method = _sale(client, tenant), _method(client, tenant)
    payment = paid(client, tenant, sale, method)
    assert client.post(f"/api/v1/sale-payments/{payment['id']}/void", headers=_headers(tenant), json={'reason': 'Duplicado'}).status_code == 200
    result = report(client, tenant)['data']
    assert result['payments'] == [] and result['summary'] == {'total_amount_ars': '0.00', 'payment_count': 0, 'by_method': []}


def test_reversed_sale_keeps_its_active_payment(client, tenant):
    sale, method = _sale(client, tenant), _method(client, tenant)
    paid(client, tenant, sale, method)
    assert client.post(f"/api/v1/sales/{sale['id']}/reverse", headers=_headers(tenant), json={'reason': 'Corrección'}).status_code == 200
    assert report(client, tenant)['data']['summary']['total_amount_ars'] == '10.00'


def test_rename_groups_identity_preserves_snapshots_and_inactive_selector(client, tenant):
    sale, method = _sale(client, tenant), _method(client, tenant)
    paid(client, tenant, sale, method, received_at=f'{DAY}T10:00:00Z')
    assert client.patch(f"/api/v1/payment-methods/{method['id']}", headers=_headers(tenant), json={'label': 'Caja nueva'}).status_code == 200
    paid(client, tenant, sale, method, received_at=f'{DAY}T13:00:00Z')
    client.patch(f"/api/v1/payment-methods/{method['id']}", headers=_headers(tenant), json={'label': 'Último nombre', 'is_active': False})
    result = report(client, tenant, payment_method_id=method['id'])['data']
    assert len(result['summary']['by_method']) == 1
    assert result['summary']['by_method'][0]['label'] == 'Caja nueva'
    assert result['summary']['by_method'][0]['is_active'] is False
    assert [p['payment_method_label'] for p in result['payments']] == ['Caja nueva', 'Efectivo']
    assert result['methods'][0] == {'payment_method_id': method['id'], 'label': 'Último nombre', 'is_active': False}


def test_method_filter_applies_to_summary_and_page(client, tenant):
    sale = _sale(client, tenant)
    methods = [_method(client, tenant, label=label) for label in ['Cash', 'QR']]
    for m in methods: paid(client, tenant, sale, m)
    result = report(client, tenant, payment_method_id=methods[0]['id'])
    assert result['meta']['total'] == result['data']['summary']['payment_count'] == 1
    assert result['data']['payments'][0]['payment_method_id'] == methods[0]['id']
    assert len(result['data']['methods']) == 2


@pytest.mark.parametrize('instant,included', [
    ('2026-08-09T04:59:59.999999Z', False), ('2026-08-09T05:00:00Z', True),
    ('2026-08-10T04:59:59.999999Z', True), ('2026-08-10T05:00:00Z', False),
])
def test_panama_inclusive_day_exclusive_next_day(client, tenant, instant, included):
    paid(client, tenant, _sale(client, tenant), _method(client, tenant), received_at=instant)
    assert report(client, tenant)['data']['summary']['payment_count'] == int(included)


@pytest.mark.parametrize('zone,day,start,end', [
    ('Asia/Tokyo', '2026-08-09', '2026-08-08T15:00:00Z', '2026-08-09T15:00:00Z'),
    ('America/Argentina/Buenos_Aires', DAY, '2026-08-09T03:00:00Z', '2026-08-10T03:00:00Z'),
    ('America/New_York', '2026-03-08', '2026-03-08T05:00:00Z', '2026-03-09T04:00:00Z'),
    ('America/New_York', '2026-11-01', '2026-11-01T04:00:00Z', '2026-11-02T05:00:00Z'),
])
def test_timezone_and_dst_day_lengths(client, db_session, tenant, zone, day, start, end):
    tenant.timezone = zone; db_session.commit()
    sale, method = _sale(client, tenant), _method(client, tenant)
    paid(client, tenant, sale, method, received_at=start)
    paid(client, tenant, sale, method, received_at=end)
    result = report(client, tenant, date_from=day, date_to=day)['data']
    assert result['summary']['payment_count'] == 1 and result['timezone'] == zone


def test_decimal_sum_and_summary_independent_of_pagination(client, tenant):
    sale, method = _sale(client, tenant), _method(client, tenant)
    for amount in ['0.10', '0.20', '0.33']: paid(client, tenant, sale, method, amount)
    first, second = report(client, tenant, page_size=1), report(client, tenant, page_size=1, page=2)
    assert first['data']['summary'] == second['data']['summary']
    assert first['data']['summary']['total_amount_ars'] == '0.63'
    assert len(first['data']['payments']) == 1 and first['meta']['total_pages'] == 3
    assert first['data']['payments'][0]['payment_id'] != second['data']['payments'][0]['payment_id']
    assert report(client, tenant, page_size=1, page=9)['data']['payments'] == []


def test_summary_covers_150_payments_with_20_on_page(client, db_session, tenant):
    sale, method = _sale(client, tenant), _method(client, tenant)
    for _ in range(150):
        db_session.add(SalePayment(tenant_id=tenant.id, sale_id=uuid.UUID(sale['id']), payment_method_id=uuid.UUID(method['id']), payment_method_label_snapshot='Efectivo', payment_method_type_snapshot='cash', amount_ars=Decimal('0.10'), received_at=datetime(2026, 8, 9, 12, tzinfo=UTC), is_active=True))
    db_session.commit()
    result = report(client, tenant)
    assert len(result['data']['payments']) == 20 and result['meta']['total'] == 150
    assert result['data']['summary']['total_amount_ars'] == '15.00'


def test_tenant_payments_methods_foreign_uuid_and_random_uuid(client, tenant, other_tenant):
    local_method, foreign_method = _method(client, tenant), _method(client, other_tenant)
    paid(client, tenant, _sale(client, tenant), local_method)
    paid(client, other_tenant, _sale(client, other_tenant), foreign_method, '90.00')
    result = report(client, tenant)['data']
    assert result['summary']['total_amount_ars'] == '10.00'
    assert [m['payment_method_id'] for m in result['methods']] == [local_method['id']]
    errors = [client.get(URL, headers=_headers(tenant), params={'payment_method_id': value}) for value in [foreign_method['id'], str(uuid.uuid4())]]
    assert all(r.status_code == 404 for r in errors) and errors[0].json() == errors[1].json()


@pytest.mark.parametrize('relation', ['sale', 'method', 'owner', 'patient', 'user'])
def test_corrupt_foreign_relationship_never_exposes_foreign_data(client, db_session, tenant, other_tenant, relation):
    sale, method = _sale(client, tenant), _method(client, tenant)
    payment = paid(client, tenant, sale, method)
    row = db_session.get(SalePayment, uuid.UUID(payment['id']))
    sold = db_session.get(Sale, uuid.UUID(sale['id']))
    foreign_sale, foreign_method = _sale(client, other_tenant), _method(client, other_tenant, label='FOREIGN SECRET')
    owner = _owner(client, other_tenant, name='FOREIGN SECRET')
    patient = _patient(client, other_tenant, owner['id'], name='FOREIGN SECRET')
    if relation == 'sale': row.sale_id = uuid.UUID(foreign_sale['id'])
    if relation == 'method': row.payment_method_id = uuid.UUID(foreign_method['id']); row.payment_method_label_snapshot = 'FOREIGN SECRET'
    if relation == 'owner': sold.owner_id = uuid.UUID(owner['id']); sold.owner_name_snapshot = 'FOREIGN SECRET'
    if relation == 'patient': sold.patient_id = uuid.UUID(patient['id']); sold.patient_name_snapshot = 'FOREIGN SECRET'
    if relation == 'user':
        user = User(tenant_id=other_tenant.id, email='foreign@example.com', full_name='FOREIGN SECRET', role='clinic_admin')
        db_session.add(user); db_session.flush(); row.created_by_user_id = user.id
    db_session.commit()
    result = report(client, tenant)['data']
    assert 'FOREIGN SECRET' not in str(result)
    if relation in ['sale', 'method']: assert result['summary']['payment_count'] == 0
    else: assert result['payments'][0][{'owner': 'owner_id', 'patient': 'patient_id', 'user': 'created_by_user_id'}[relation]] is None


def test_optional_parties_and_local_actor(client, db_session, tenant):
    sale, method = _sale(client, tenant), _method(client, tenant)
    payment = paid(client, tenant, sale, method, reference=None)
    sold = db_session.get(Sale, uuid.UUID(sale['id']))
    sold.owner_id = sold.patient_id = None; sold.owner_name_snapshot = sold.patient_name_snapshot = None
    actor = User(tenant_id=tenant.id, email='local@example.com', full_name='Operadora', role='secretaria')
    db_session.add(actor); db_session.flush()
    db_session.get(SalePayment, uuid.UUID(payment['id'])).created_by_user_id = actor.id
    db_session.commit()
    row = report(client, tenant)['data']['payments'][0]
    assert row['owner_id'] is row['owner_name'] is row['patient_id'] is row['patient_name'] is row['reference'] is None
    assert row['created_by_user_name'] == 'Operadora'


def test_stable_order_uses_timestamp_then_uuid(client, tenant):
    sale, method = _sale(client, tenant), _method(client, tenant)
    payments = [paid(client, tenant, sale, method) for _ in range(3)]
    latest = paid(client, tenant, sale, method, received_at=f'{DAY}T13:00:00Z')
    assert [p['payment_id'] for p in report(client, tenant)['data']['payments']] == [latest['id'], *sorted([p['id'] for p in payments], reverse=True)]


@pytest.mark.parametrize('params', [
    {'date_from': '2026-08-10', 'date_to': DAY}, {'date_from': 'bad'}, {'date_to': '9999-12-31'},
    {'page': 0}, {'page_size': 101}, {'payment_method_id': 'bad'},
])
def test_invalid_filters(client, tenant, params):
    assert client.get(URL, headers=_headers(tenant), params=params).status_code == 422


@pytest.mark.parametrize('zone,day', [('Invalid/Zone', DAY), ('Pacific/Apia', '2011-12-30')])
def test_invalid_zone_and_nonexistent_day(client, db_session, tenant, zone, day):
    tenant.timezone = zone; db_session.commit()
    assert client.get(URL, headers=_headers(tenant), params={'date_from': day, 'date_to': day}).status_code == 422


def test_default_today_uses_clinic_clock(client, db_session, tenant, monkeypatch):
    import app.services.payment_report as service
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None): return cls(2026, 10, 3, 2, tzinfo=UTC).astimezone(tz)
    monkeypatch.setattr(service, 'datetime', Clock)
    tenant.timezone = 'America/Panama'; db_session.commit()
    data = client.get(URL, headers=_headers(tenant)).json()['data']
    assert data['date_from'] == data['date_to'] == '2026-10-02'


def test_report_query_count_constant_and_selector_not_truncated(client, db_session, tenant):
    sale, method = _sale(client, tenant), _method(client, tenant)
    paid(client, tenant, sale, method)
    for i in range(105): db_session.add(PaymentMethod(tenant_id=tenant.id, label=f'M{i}', normalized_label=f'm{i}', type='other', is_active=False))
    db_session.commit()
    queries = []
    def track(conn, cursor, statement, parameters, context, many):
        if statement.lstrip().upper().startswith(('SELECT', 'WITH')): queries.append(statement)
    event.listen(db_session.get_bind(), 'before_cursor_execute', track)
    try: result = report(client, tenant)
    finally: event.remove(db_session.get_bind(), 'before_cursor_execute', track)
    assert len(result['data']['methods']) == 106
    # Context tenant lookup + profile + methods + aggregate + page + preferences.
    assert len(queries) <= 6, queries


@pytest.mark.parametrize('role', ['clinic_admin', 'medico_veterinario', 'secretaria', 'contador', 'superadmin'])
def test_existing_sales_read_roles_and_acting_tenant_scope(client, db_session, tenant, other_tenant, role):
    user = User(tenant_id=tenant.id, email=f'{role}@example.com', full_name=role, role=role)
    db_session.add(user); db_session.commit()
    response = client.get(URL, headers={'X-User-Email': user.email, 'X-Acting-Tenant-Id': str(other_tenant.id)})
    assert response.status_code == 200
    # A foreign method exists only in the other clinic.
    method = _method(client, other_tenant)
    response = client.get(URL, headers={'X-User-Email': user.email, 'X-Acting-Tenant-Id': str(other_tenant.id)})
    assert (method['id'] in [m['payment_method_id'] for m in response.json()['data']['methods']]) == (role == 'superadmin')


def test_report_requires_authentication_outside_development(client, tenant, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setenv('APP_ENV', 'production'); get_settings.cache_clear()
    assert client.get(URL, headers=_headers(tenant)).status_code == 401


def test_postgres_exact_large_totals_and_utc_boundaries(postgres_test_session_factory):
    engine = postgres_test_session_factory.kw['bind']
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode='create_savepoint') as db:
                tenant = Tenant(name='P13 isolated test', timezone='America/Panama')
                db.add(tenant); db.flush()
                method = PaymentMethod(tenant_id=tenant.id, label='Cash', normalized_label='cash', type='cash', is_active=True)
                sale = Sale(tenant_id=tenant.id, sale_date=date(2026, 8, 1), currency='ARS', status='confirmed', subtotal_ars=Decimal('99999999999999.99'), total_ars=Decimal('99999999999999.99'), discount_total_ars=Decimal('0.00'))
                db.add_all([method, sale]); db.flush()
                for instant, amount in [(datetime(2026, 8, 9, 5, tzinfo=UTC), '99999999999999.99'), (datetime(2026, 8, 10, 4, 59, 59, 999999, tzinfo=UTC), '0.02'), (datetime(2026, 8, 10, 5, tzinfo=UTC), '10.00')]:
                    db.add(SalePayment(tenant_id=tenant.id, sale_id=sale.id, payment_method_id=method.id, payment_method_label_snapshot='Cash', payment_method_type_snapshot='cash', amount_ars=Decimal(amount), received_at=instant, is_active=True))
                db.flush()
                result, meta = PaymentReportService(db).read(tenant.id, date_from=date(2026, 8, 9), date_to=date(2026, 8, 9), payment_method_id=None, page=1, page_size=1)
                assert result.summary.total_amount_ars == Decimal('100000000000000.01')
                assert result.summary.total_amount_ars == result.summary.by_method[0].amount_ars
                assert meta['total'] == 2 and len(result.payments) == 1
        finally: transaction.rollback()

"""P.12.2 uses the existing clinic settings permission and derives receivables."""
from datetime import UTC, datetime
import uuid

import pytest
from sqlalchemy import select

from app.models.patient import Patient
from app.models.payment import SalePayment
from app.models.sale import Sale
from app.models.tenant_preference import TenantPreference
from app.tests.test_clinic_preferences import _create_user, _user_headers
from app.tests.test_sales import _create, _headers, _owner

URL = '/api/v1/clinic/preferences'
DATE = 'receivables_tracking_start_date'
STAMP = 'receivables_tracking_started_at'


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    import app.services.clinic as clinic
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            value = cls(2026, 10, 5, 2, tzinfo=UTC)
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)
    monkeypatch.setattr(clinic, 'datetime', Clock)


def _admin(db, tenant, role='clinic_admin'):
    return _user_headers(_create_user(db, tenant, f'{uuid.uuid4()}@example.com', 'Operator', role).email)


@pytest.mark.parametrize('timezone,day,expected', [
    ('America/Panama', '2026-10-04', '2026-10-04T05:00:00+00:00'),
    ('America/Argentina/Buenos_Aires', '2026-10-04', '2026-10-04T03:00:00+00:00'),
    ('Asia/Tokyo', '2026-10-05', '2026-10-04T15:00:00+00:00'),
    ('America/New_York', '2026-07-01', '2026-07-01T04:00:00+00:00'),
    ('America/New_York', '2026-01-01', '2026-01-01T05:00:00+00:00'),
])
def test_date_uses_clinic_midnight_utc_and_persists(client, db_session, tenant, timezone, day, expected):
    tenant.timezone = timezone; db_session.commit()
    headers = _admin(db_session, tenant)
    assert client.get(URL, headers=headers).json()['data'][STAMP] is None
    response = client.patch(URL, headers=headers, json={DATE: day})
    assert response.status_code == 200, response.text
    actual = datetime.fromisoformat(response.json()['data'][STAMP].replace('Z', '+00:00'))
    assert actual == datetime.fromisoformat(expected)
    assert actual.utcoffset().total_seconds() == 0
    persisted = db_session.scalar(select(TenantPreference).where(TenantPreference.tenant_id == tenant.id)).receivables_tracking_started_at
    assert persisted.replace(tzinfo=UTC) == actual
    assert client.get(URL, headers=headers).json()['data'][STAMP] == response.json()['data'][STAMP]


@pytest.mark.parametrize('payload', [
    {DATE: '2026-10-05'},  # Panama is still Oct 4 at this instant.
    {STAMP: '2026-10-05T00:00:00-05:00'},
    {STAMP: '2026-10-05T05:00:00Z'},
    {DATE: None}, {DATE: '2026-02-30'},
    {DATE: '2026-10-04', STAMP: '2026-10-04T05:00:00Z'},
    {STAMP: '2026-10-04T00:00:00'},
])
def test_invalid_and_future_inputs_do_not_activate_tracking(client, db_session, tenant, payload):
    headers = _admin(db_session, tenant)
    client.get(URL, headers=headers)
    response = client.patch(URL, headers=headers, json=payload)
    assert response.status_code == 422, response.text
    assert client.get(URL, headers=headers).json()['data'][STAMP] is None


def test_timestamp_contract_utc_and_nullable_is_preserved(client, db_session, tenant):
    headers = _admin(db_session, tenant)
    result = client.patch(URL, headers=headers, json={STAMP: '2026-10-02T08:00:00-05:00'})
    assert result.status_code == 200
    assert datetime.fromisoformat(result.json()['data'][STAMP].replace('Z', '+00:00')) == datetime(2026, 10, 2, 13, tzinfo=UTC)
    assert client.patch(URL, headers=headers, json={STAMP: None}).json()['data'][STAMP] is None


@pytest.mark.parametrize('role', ['clinic_admin', 'medico_veterinario', 'contador', 'secretaria'])
def test_existing_settings_roles_can_update_their_clinic_only(client, db_session, tenant, other_tenant, role):
    headers = _admin(db_session, tenant, role)
    headers['X-Tenant-Id'] = str(other_tenant.id)
    headers['X-Acting-Tenant-Id'] = str(other_tenant.id)
    response = client.patch(URL, headers=headers, json={DATE: '2026-10-01'})
    assert response.status_code == 200
    assert response.json()['data']['tenant_id'] == str(tenant.id)
    assert client.get(URL, headers=_headers(other_tenant)).json()['data'][STAMP] is None


def test_unpermitted_user_cannot_modify_settings(client, db_session, tenant):
    response = client.patch(URL, headers=_admin(db_session, tenant, 'superadmin'), json={DATE: '2026-10-01'})
    assert response.status_code == 403
    assert client.patch(URL, headers=_headers(tenant), json={DATE: '2026-10-01'}).status_code == 403
    assert client.get(URL, headers=_headers(tenant)).json()['data'][STAMP] is None


def test_cutoff_changes_eligibility_and_badges_without_changing_sales_or_payments(client, db_session, tenant):
    headers = _admin(db_session, tenant)
    owner = _owner(client, tenant)
    patient = Patient(tenant_id=tenant.id, owner_id=uuid.UUID(owner['id']), name='Luna', species='canine')
    db_session.add(patient); db_session.commit(); patient_id = patient.id
    sale = _create(client, tenant, owner_id=owner['id'])
    model = db_session.scalar(select(Sale).where(Sale.id == uuid.UUID(sale['id']), Sale.tenant_id == tenant.id))
    model.status = 'confirmed'; model.confirmed_at = datetime(2026, 10, 2, 12, tzinfo=UTC)
    db_session.commit()
    def snapshots():
        sales = client.get(f"/api/v1/sales/{sale['id']}", headers=headers).json()['data']
        payments = list(db_session.scalars(select(SalePayment).where(SalePayment.tenant_id == tenant.id)))
        return sales, payments
    before = snapshots()
    url = f"/api/v1/owners/{owner['id']}/receivables"
    for day, configured, amount, badge in [(None, False, '0.00', False), ('2026-10-01', True, '50.00', True), ('2026-10-03', True, '0.00', False), ('2026-10-01', True, '50.00', True)]:
        if day:
            assert client.patch(URL, headers=headers, json={DATE: day}).status_code == 200
        account = client.get(url, headers=headers).json()['data']
        assert account['tracking_configured'] is configured
        assert account['total_outstanding_ars'] == amount
        assert account['open_sales_count'] == int(badge)
        owner_data = client.get(f"/api/v1/owners/{owner['id']}", headers=headers).json()['data']
        patient_data = client.get(f'/api/v1/patients/{patient_id}', headers=headers).json()['data']
        assert owner_data['has_active_receivable'] is badge
        assert patient_data['owner_has_active_receivable'] is badge
        assert snapshots() == before


@pytest.mark.parametrize('timezone,day,code', [
    ('Invalid/Zone', '2026-10-01', 'invalid_clinic_timezone'),
    ('Pacific/Apia', '2011-12-30', 'invalid_receivables_start_date'),
])
def test_invalid_zone_or_nonexistent_calendar_day_does_not_choose_a_fallback(client, db_session, tenant, timezone, day, code):
    tenant.timezone = timezone; db_session.commit()
    headers = _admin(db_session, tenant)
    response = client.patch(URL, headers=headers, json={DATE: day})
    assert response.status_code == 422
    assert response.json()['error']['code'] == code
    assert client.get(URL, headers=headers).json()['data'][STAMP] is None

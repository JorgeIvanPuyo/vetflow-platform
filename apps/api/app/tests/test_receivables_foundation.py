"""P.10: identified pending balances, preserved owners and explicit cutoffs."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.models.owner import Owner
from app.models.patient import Patient
from app.models.payment import SalePayment, SalePaymentBatch
from app.models.sale import Sale
from app.models.tenant_preference import TenantPreference
from app.repositories.receivables import receivable_sale_criteria
from app.schemas.owner import OwnerUpdate
from app.schemas.sale import SaleConfirm
from app.services.owner import OwnerService
from app.services.sale import SaleService
from app.services.sale_confirmation import SaleConfirmationService, batch_request_hash
from app.tests.test_clinic_preferences import _create_user, _user_headers
from app.tests.test_sale_confirmation_batch import _rows
from app.tests.test_sale_transaction_composition import (
    _seed, _state, postgres_transaction_factory, transaction_factory,
)
from app.tests.test_sales import _create, _headers, _owner, _patient


def _case(factory, *, owner=False, total=100, tenant_id=None):
    case = _seed(factory, with_owner=owner, tenant_id=tenant_id)
    with factory.begin() as db:
        sale = SaleService(db).get(case.tenant_id, case.sale_id)
        sale.subtotal_ars = sale.total_ars = Decimal(total)
        line = sale.items[0]
        line.unit_price_ars = Decimal(total) / 2
        line.line_subtotal_ars = line.line_total_ars = Decimal(total)
    return case


def _intent(case, mode, amounts):
    values = {"confirm": True}
    if mode == "single":
        values["initial_payment"] = _rows(case, amounts)[0]
    elif mode == "batch":
        values["initial_payments"] = _rows(case, amounts)
    return SaleConfirm.model_validate(values)


@pytest.mark.parametrize("owner,total,mode,amounts,allowed", [
    (False, 100, "single", (100,), True),
    (False, 100, "batch", (50, 50), True),
    (False, 100, "single", (50,), False),
    (False, 100, "none", (), False),
    (False, 100, "batch", (20, 30), False),
    (False, 0, "none", (), True),
    (True, 100, "none", (), True),
    (True, 100, "single", (50,), True),
    (True, 100, "batch", (20, 30), True),
])
def test_final_balance_requires_owner_and_rejection_rolls_back_every_write(
    transaction_factory, owner, total, mode, amounts, allowed,
):
    case = _case(transaction_factory, owner=owner, total=total)
    with transaction_factory() as db:
        coordinator = SaleConfirmationService(db)
        if allowed:
            sale = coordinator.confirm(case.tenant_id, case.sale_id, _intent(case, mode, amounts), user_id=None, idempotency_key="p10")
            assert sale.status == "confirmed"
            assert sale.balance_due_ars == total - sum(amounts)
        else:
            with pytest.raises(AppError) as error:
                coordinator.confirm(case.tenant_id, case.sale_id, _intent(case, mode, amounts), user_id=None, idempotency_key="p10")
            assert (error.value.status_code, error.value.code) == (409, "sale_owner_required_for_pending_balance")
            assert "seleccionar un propietario" in error.value.message
            assert not db.in_transaction()
    with transaction_factory() as observer:
        expected = ("confirmed", 8, 1, len(amounts), total - sum(amounts)) if allowed else ("draft", 10, 0, 0, total)
        assert _state(observer, case) == expected
        sale = SaleService(observer).get(case.tenant_id, case.sale_id)
        if not allowed:
            assert sale.confirmed_at is None and sale.inventory_operation_id is None
        batches = observer.scalar(select(func.count(SalePaymentBatch.id)).where(
            SalePaymentBatch.tenant_id == case.tenant_id, SalePaymentBatch.sale_id == case.sale_id,
        ))
        assert batches == int(allowed and mode == "batch")


def test_standalone_confirmation_also_rejects_anonymous_pending_balance(transaction_factory):
    case = _case(transaction_factory)
    with transaction_factory() as db:
        with pytest.raises(AppError) as error:
            SaleService(db).confirm(case.tenant_id, case.sale_id, confirmed_by_user_id=None)
        assert error.value.code == "sale_owner_required_for_pending_balance"
    with transaction_factory() as observer:
        assert _state(observer, case) == ("draft", 10, 0, 0, 100)


def test_foreign_owner_cannot_identify_new_pending_balance(transaction_factory):
    case = _case(transaction_factory)
    foreign = _case(transaction_factory, owner=True)
    # Simple legacy FKs allow corrupt cross-clinic links; the service must not.
    with transaction_factory.begin() as db:
        sale = SaleService(db).get(case.tenant_id, case.sale_id)
        sale.owner_id = foreign.owner_id
    with transaction_factory() as db:
        with pytest.raises(AppError) as error:
            SaleConfirmationService(db).confirm(case.tenant_id, case.sale_id,
                SaleConfirm(confirm=True), user_id=None)
        assert error.value.code == "sale_owner_required_for_pending_balance"
    with transaction_factory() as observer:
        assert _state(observer, case) == ("draft", 10, 0, 0, 100)
        assert _state(observer, foreign) == ("draft", 10, 0, 0, 100)


@pytest.mark.parametrize("mode", ["none", "single", "batch"])
def test_api_returns_actionable_error_and_keeps_anonymous_draft(client, db_session, mode):
    factory = sessionmaker(bind=db_session.get_bind(), autoflush=False)
    case = _case(factory)
    response = client.post(f"/api/v1/sales/{case.sale_id}/confirm",
        headers={"X-Tenant-Id": str(case.tenant_id), "Idempotency-Key": "p10-api"},
        json=_intent(case, mode, (20, 30) if mode == "batch" else (50,)).model_dump(mode="json", exclude_unset=True))
    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "sale_owner_required_for_pending_balance",
        "message": "Para dejar un saldo pendiente, primero debes seleccionar un propietario.",
    }
    assert _state(db_session, case) == ("draft", 10, 0, 0, 100)


@pytest.mark.parametrize("mode", ["single", "batch"])
def test_historical_anonymous_partial_confirmation_replay_is_preserved(transaction_factory, mode):
    from app.services.payment import SalePaymentService

    case = _case(transaction_factory)
    payload = _intent(case, mode, (20, 30) if mode == "batch" else (50,))
    # Seed an already committed P.6/P.8 record from before the P.10 rule.
    with transaction_factory() as db:
        sale = SaleService(db).confirm_in_transaction(case.tenant_id, case.sale_id, confirmed_by_user_id=None)
        payments = SalePaymentService(db)
        if mode == "single":
            payments.create_in_transaction(case.tenant_id, case.sale_id, payload.initial_payment, user_id=None, idempotency_key="old")
        else:
            batch = SalePaymentBatch(tenant_id=case.tenant_id, sale_id=case.sale_id, idempotency_key="old", request_hash=batch_request_hash(case.sale_id, payload.initial_payments))
            db.add(batch)
            db.flush()
            for row in payload.initial_payments:
                payments.create_for_locked_sale_in_transaction(case.tenant_id, sale, row, user_id=None, batch=batch)
        db.commit()
    with transaction_factory() as db:
        before = _state(db, case)
        coordinator = SaleConfirmationService(db)
        sale = coordinator.confirm(case.tenant_id, case.sale_id, payload, user_id=None, idempotency_key="old")
        assert coordinator.idempotency_replayed
        assert sale.owner_id is None
        assert _state(db, case) == before


@pytest.mark.parametrize("status", ["draft", "confirmed", "cancelled", "reversed"])
def test_owner_with_any_sale_cannot_be_deleted_and_archive_preserves_history(
    client, db_session, tenant, other_tenant, status,
):
    owner = _owner(client, tenant)
    patient = _patient(client, tenant, owner["id"])
    sale_data = _create(client, tenant, owner_id=owner["id"], patient_id=patient["id"])
    sale = db_session.scalar(select(Sale).where(Sale.tenant_id == tenant.id, Sale.id == uuid.UUID(sale_data["id"])))
    sale.status = status
    if status == "confirmed":
        sale.confirmed_at = datetime(2020, 1, 1, tzinfo=UTC)
    db_session.commit()
    original = client.get(f"/api/v1/sales/{sale.id}", headers=_headers(tenant)).json()["data"]
    url = f"/api/v1/owners/{owner['id']}"
    assert client.delete(url, headers=_headers(other_tenant)).status_code == 404
    assert client.patch(url, headers=_headers(other_tenant), json={"is_active": False}).status_code == 404
    rejected = client.delete(url, headers=_headers(tenant))
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "owner_has_commercial_history"
    archived = client.patch(url, headers=_headers(tenant), json={"is_active": False})
    assert archived.status_code == 200 and archived.json()["data"]["is_active"] is False
    assert client.get(url, headers=_headers(tenant)).json()["data"]["full_name"] == owner["full_name"]
    assert client.get(f"/api/v1/sales/{sale.id}", headers=_headers(tenant)).json()["data"] == original
    assert db_session.scalar(select(Patient.id).where(Patient.tenant_id == tenant.id, Patient.id == uuid.UUID(patient["id"]))) is not None
    assert client.delete(url, headers=_headers(tenant)).status_code == 409
    assert client.patch(url, headers=_headers(tenant), json={"is_active": True}).json()["data"]["is_active"] is True


def test_owner_without_sales_keeps_hard_delete_and_null_archive_is_rejected(client, tenant):
    owner = _owner(client, tenant)
    assert owner["is_active"] is True
    url = f"/api/v1/owners/{owner['id']}"
    assert client.patch(url, headers=_headers(tenant), json={"is_active": None}).status_code == 422
    assert client.delete(url, headers=_headers(tenant)).status_code == 204
    assert client.get(url, headers=_headers(tenant)).status_code == 404


def test_postgresql_fk_rejection_rolls_back_clinical_deletion_for_corrupt_legacy_link(postgres_transaction_factory):
    first = _case(postgres_transaction_factory, owner=True)
    foreign = _case(postgres_transaction_factory, owner=True)
    with postgres_transaction_factory.begin() as db:
        own_sale = SaleService(db).get(first.tenant_id, first.sale_id)
        own_sale.owner_id = None
        foreign_sale = SaleService(db).get(foreign.tenant_id, foreign.sale_id)
        foreign_sale.owner_id = first.owner_id
        patient = Patient(tenant_id=first.tenant_id, owner_id=first.owner_id, name="Preserved", species="canine")
        db.add(patient)
        db.flush()
        patient_id = patient.id
    with postgres_transaction_factory() as db:
        # The scoped history check cannot see the corrupt reference. RESTRICT
        # must protect the Owner and the outer rollback must restore the Patient.
        with pytest.raises(AppError) as error:
            OwnerService(db).delete_owner(first.tenant_id, first.owner_id)
        assert (error.value.status_code, error.value.code) == (409, "owner_has_commercial_history")
        assert not db.in_transaction()
    with postgres_transaction_factory() as observer:
        assert observer.scalar(select(Owner.id).where(Owner.tenant_id == first.tenant_id, Owner.id == first.owner_id)) == first.owner_id
        assert observer.scalar(select(Patient.id).where(Patient.tenant_id == first.tenant_id, Patient.id == patient_id)) == patient_id
        assert SaleService(observer).get(foreign.tenant_id, foreign.sale_id).owner_id == first.owner_id


def test_cutoff_configuration_is_explicit_utc_nullable_and_tenant_scoped(client, db_session, tenant, other_tenant):
    assert client.get("/api/v1/clinic/preferences", headers=_headers(tenant)).json()["data"]["receivables_tracking_started_at"] is None
    admin = _create_user(db_session, tenant, "cutoff-admin@example.com", "Admin", "clinic_admin")
    url = "/api/v1/clinic/preferences"
    key = "receivables_tracking_started_at"
    result = client.patch(url, headers=_user_headers(admin.email), json={key: "2026-10-02T08:00:00-05:00"})
    assert result.status_code == 200, result.text
    assert datetime.fromisoformat(result.json()["data"][key]).replace(tzinfo=UTC) == datetime(2026, 10, 2, 13, tzinfo=UTC)
    assert client.get(url, headers=_headers(other_tenant)).json()["data"][key] is None
    for invalid in ["2026-10-02T13:00:00", "2026-10-02", "invalid"]:
        assert client.patch(url, headers=_user_headers(admin.email), json={key: invalid}).status_code == 422
    assert client.patch(url, headers=_user_headers(admin.email), json={"currency_code": None}).status_code == 422
    assert client.patch(url, headers=_user_headers(admin.email), json={key: None}).json()["data"][key] is None


def test_eligibility_uses_each_tenant_cutoff_boundary_status_and_preserved_owner(transaction_factory):
    cutoff = datetime(2026, 10, 2, 13, tzinfo=UTC)
    first = _case(transaction_factory, owner=True)
    second = _case(transaction_factory, owner=True)
    with transaction_factory.begin() as db:
        db.add_all([TenantPreference(tenant_id=first.tenant_id), TenantPreference(tenant_id=second.tenant_id, receivables_tracking_started_at=cutoff + timedelta(days=1))])
    ids = []
    scenarios = [(-1, "confirmed", True), (0, "confirmed", True), (1, "confirmed", True),
                 (1, "draft", True), (1, "cancelled", True), (1, "reversed", True), (1, "confirmed", False)]
    for offset, status, owner in scenarios:
        case = _case(transaction_factory, owner=owner, tenant_id=first.tenant_id)
        with transaction_factory.begin() as db:
            sale = SaleService(db).get(case.tenant_id, case.sale_id)
            sale.status = status
            sale.confirmed_at = cutoff + timedelta(seconds=offset)
        ids.append(case.sale_id)
    with transaction_factory() as db:
        def eligible(tenant_id):
            return set(db.scalars(select(Sale.id).where(receivable_sale_criteria(tenant_id))))
        assert eligible(first.tenant_id) == set()  # NULL must not infer old debt.
        preferences = db.scalar(select(TenantPreference).where(TenantPreference.tenant_id == first.tenant_id))
        preferences.receivables_tracking_started_at = cutoff
        db.flush()
        assert eligible(first.tenant_id) == {ids[1], ids[2]}
        # An archived owner remains identifiable, including a fully paid sale.
        sale = SaleService(db).get(first.tenant_id, ids[1])
        OwnerService(db).update_owner(first.tenant_id, sale.owner_id, OwnerUpdate(is_active=False))
        from app.services.payment import SalePaymentService
        from app.schemas.payment import SalePaymentCreate
        SalePaymentService(db).create(first.tenant_id, sale.id, SalePaymentCreate(payment_method_id=first.method_id, amount_ars=100, received_at=cutoff), user_id=None)
        assert SaleService(db).get(first.tenant_id, sale.id).balance_due_ars == 0
        assert eligible(first.tenant_id) == {ids[1], ids[2]}
        other = SaleService(db).get(second.tenant_id, second.sale_id)
        other.status = "confirmed"
        other.confirmed_at = cutoff
        db.flush()
        assert eligible(second.tenant_id) == set()
        other.confirmed_at = cutoff + timedelta(days=1)
        db.flush()
        assert eligible(second.tenant_id) == {second.sale_id}
        assert eligible(uuid.uuid4()) == set()  # Missing preference/tenant.
        # A corrupt simple FK must not expose a different clinic's Owner.
        other.owner_id = first.owner_id
        db.flush()
        assert eligible(second.tenant_id) == set()
        db.rollback()


def test_old_confirmed_sale_without_payments_is_unchanged_and_not_eligible(transaction_factory):
    case = _case(transaction_factory, owner=True)
    with transaction_factory.begin() as db:
        sale = SaleService(db).get(case.tenant_id, case.sale_id)
        sale.status = "confirmed"
        sale.confirmed_at = datetime(2020, 1, 1, tzinfo=UTC)
    with transaction_factory() as db:
        before = (case.sale_id, _state(db, case))
        assert not list(db.scalars(select(Sale.id).where(receivable_sale_criteria(case.tenant_id))))
        db.add(TenantPreference(tenant_id=case.tenant_id, receivables_tracking_started_at=datetime(2026, 10, 2, tzinfo=UTC)))
        db.commit()
        assert not list(db.scalars(select(Sale.id).where(receivable_sale_criteria(case.tenant_id))))
        assert (case.sale_id, _state(db, case)) == before
        assert not list(db.scalars(select(SalePayment).where(SalePayment.tenant_id == case.tenant_id)))

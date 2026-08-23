import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from decimal import Decimal
from threading import Barrier

import pytest
from sqlalchemy import delete

from app.core.errors import AppError
from app.db.session import SessionLocal, engine
from app.models.payment import PaymentMethod, SalePayment
from app.models.sale import Sale, SaleItem
from app.models.tenant import Tenant
from app.services.payment import SalePaymentService
from app.schemas.payment import SalePaymentCreate


def _headers(tenant):
    return {"X-Tenant-Id": str(tenant.id)}


def _method(client, tenant, **overrides):
    payload = {"label": "Efectivo", "type": "cash", "is_active": True, "sort_order": 0, **overrides}
    response = client.post("/api/v1/payment-methods", headers=_headers(tenant), json=payload)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _sale(client, tenant, *, status="confirmed", total="100.00"):
    created = client.post("/api/v1/sales", headers=_headers(tenant), json={"owner_id": None, "patient_id": None, "sale_date": "2026-08-09", "items": [{"line_type": "service", "description": "Consulta", "quantity": "1", "unit_price_ars": total, "discount_percentage": "0"}]})
    assert created.status_code == 201, created.text
    sale = created.json()["data"]
    if status == "confirmed":
        response = client.post(f"/api/v1/sales/{sale['id']}/confirm", headers=_headers(tenant), json={"confirm": True})
        assert response.status_code == 200, response.text
        return response.json()["data"]
    if status == "cancelled":
        return client.post(f"/api/v1/sales/{sale['id']}/cancel", headers=_headers(tenant), json={"reason": "No continúa"}).json()["data"]
    return sale


def _pay(client, tenant, sale, method, amount="40.00", **overrides):
    payload = {"payment_method_id": method["id"], "amount_ars": amount, "received_at": "2026-08-09T12:00:00Z", "reference": "REF-1", "notes": "Cobro", **overrides}
    return client.post(f"/api/v1/sales/{sale['id']}/payments", headers=_headers(tenant), json=payload)


@pytest.mark.parametrize("status", ["draft", "cancelled"])
def test_only_confirmed_sales_accept_payments(client, tenant, status):
    method = _method(client, tenant)
    sale = _sale(client, tenant, status=status)
    response = _pay(client, tenant, sale, method)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "sale_payment_not_allowed"


@pytest.mark.parametrize("amount", ["0", "-1", "1.001"])
def test_payment_amount_must_be_positive_decimal_with_two_places(client, tenant, amount):
    response = _pay(client, tenant, _sale(client, tenant), _method(client, tenant), amount)
    assert response.status_code == 422


def test_partial_combined_paid_and_overpayment_statuses(client, tenant):
    sale = _sale(client, tenant)
    cash = _method(client, tenant)
    transfer = _method(client, tenant, label="Transferencia", type="bank_transfer", sort_order=1)
    assert sale["payment_status"] == "unpaid" and sale["paid_total_ars"] == "0.00"
    first = _pay(client, tenant, sale, cash, "40.00")
    assert first.status_code == 201
    detail = client.get(f"/api/v1/sales/{sale['id']}", headers=_headers(tenant)).json()["data"]
    assert detail["paid_total_ars"] == "40.00" and detail["balance_due_ars"] == "60.00" and detail["payment_status"] == "partial"
    assert _pay(client, tenant, sale, transfer, "60.00").status_code == 201
    paid = client.get(f"/api/v1/sales/{sale['id']}", headers=_headers(tenant)).json()["data"]
    assert paid["payment_status"] == "paid" and len(paid["payments"]) == 2
    excess = _pay(client, tenant, sale, cash, "0.01")
    assert excess.status_code == 409 and excess.json()["error"]["code"] == "sale_payment_exceeds_balance"


def test_cross_tenant_and_inactive_method_are_rejected(client, tenant, other_tenant):
    sale = _sale(client, tenant)
    foreign = _method(client, other_tenant)
    assert _pay(client, tenant, sale, foreign).status_code == 404
    local = _method(client, tenant, label="Débito", type="debit_card")
    client.patch(f"/api/v1/payment-methods/{local['id']}", headers=_headers(tenant), json={"is_active": False})
    assert _pay(client, tenant, sale, local).status_code == 409


def test_snapshots_survive_method_rename_and_inactivation_and_type_locks(client, tenant):
    sale = _sale(client, tenant)
    method = _method(client, tenant, label="Efectivo caja")
    payment = _pay(client, tenant, sale, method).json()["data"]
    update = client.patch(f"/api/v1/payment-methods/{method['id']}", headers=_headers(tenant), json={"label": "Caja principal", "is_active": False, "sort_order": 9})
    assert update.status_code == 200 and update.json()["data"]["has_payments"] is True
    locked = client.patch(f"/api/v1/payment-methods/{method['id']}", headers=_headers(tenant), json={"type": "other"})
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "payment_method_type_locked"
    history = client.get(f"/api/v1/sales/{sale['id']}/payments", headers=_headers(tenant)).json()["data"]
    assert history[0]["id"] == payment["id"] and history[0]["payment_method_label_snapshot"] == "Efectivo caja" and history[0]["payment_method_type_snapshot"] == "cash"


def test_void_preserves_trace_recalculates_balance_and_rejects_double_void(client, tenant):
    sale = _sale(client, tenant)
    method = _method(client, tenant)
    payment = _pay(client, tenant, sale, method, "100.00").json()["data"]
    assert client.post(f"/api/v1/sale-payments/{payment['id']}/void", headers=_headers(tenant), json={"reason": "  "}).status_code == 422
    voided = client.post(f"/api/v1/sale-payments/{payment['id']}/void", headers=_headers(tenant), json={"reason": "Cobro duplicado"})
    assert voided.status_code == 200
    assert voided.json()["data"]["is_active"] is False and voided.json()["data"]["voided_at"] and voided.json()["data"]["void_reason"] == "Cobro duplicado"
    detail = client.get(f"/api/v1/sales/{sale['id']}", headers=_headers(tenant)).json()["data"]
    assert detail["payment_status"] == "unpaid" and detail["paid_total_ars"] == "0.00" and len(detail["payments"]) == 1
    assert client.post(f"/api/v1/sale-payments/{payment['id']}/void", headers=_headers(tenant), json={"reason": "Otra"}).status_code == 409


def test_reversal_keeps_active_payments_and_requires_attention(client, tenant):
    sale = _sale(client, tenant)
    method = _method(client, tenant)
    _pay(client, tenant, sale, method, "20.00")
    reversed_sale = client.post(f"/api/v1/sales/{sale['id']}/reverse", headers=_headers(tenant), json={"reason": "Corrección"}).json()["data"]
    assert reversed_sale["payment_status"] == "requires_attention" and reversed_sale["payment_requires_attention"] is True
    assert reversed_sale["paid_total_ars"] == "20.00" and reversed_sale["payments"][0]["is_active"] is True
    assert _pay(client, tenant, reversed_sale, method, "10.00").status_code == 409


def test_list_payment_filters_and_non_applicable_status(client, tenant):
    draft = _sale(client, tenant, status="draft")
    unpaid = _sale(client, tenant)
    partial = _sale(client, tenant)
    method = _method(client, tenant)
    _pay(client, tenant, partial, method, "25.00")
    assert client.get(f"/api/v1/sales/{draft['id']}", headers=_headers(tenant)).json()["data"]["payment_status"] is None
    assert [item["id"] for item in client.get("/api/v1/sales?payment_status=unpaid", headers=_headers(tenant)).json()["data"]] == [unpaid["id"]]
    assert [item["id"] for item in client.get("/api/v1/sales?payment_status=partial", headers=_headers(tenant)).json()["data"]] == [partial["id"]]


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Requires PostgreSQL row locks")
def test_concurrent_payments_cannot_overpay():
    setup = SessionLocal()
    tenant = Tenant(id=uuid.uuid4(), name=f"Payment concurrency {uuid.uuid4()}")
    method = PaymentMethod(tenant_id=tenant.id, label="Efectivo", normalized_label="efectivo", type="cash", is_active=True, sort_order=0)
    sale = Sale(tenant_id=tenant.id, sale_date=date(2026, 8, 9), currency="ARS", subtotal_ars=Decimal("100"), discount_total_ars=Decimal("0"), total_ars=Decimal("100"), status="confirmed", confirmed_at=datetime.now(UTC))
    sale.items.append(SaleItem(tenant_id=tenant.id, line_type="service", service_id=None, inventory_item_id=None, description_snapshot="Servicio", internal_code_snapshot=None, unit_snapshot="service", quantity=Decimal("1"), unit_price_ars=Decimal("100"), discount_percentage=Decimal("0"), line_subtotal_ars=Decimal("100"), line_discount_ars=Decimal("0"), line_total_ars=Decimal("100"), line_order=1))
    setup.add(tenant); setup.flush()
    setup.add_all([method, sale]); setup.commit()
    tenant_id, sale_id, method_id = tenant.id, sale.id, method.id
    setup.close()
    barrier = Barrier(2)
    def pay():
        session = SessionLocal()
        try:
            barrier.wait(timeout=10)
            SalePaymentService(session).create(tenant_id, sale_id, SalePaymentCreate(payment_method_id=method_id, amount_ars=Decimal("70"), received_at=datetime.now(UTC)), user_id=None)
            return "created"
        except AppError as exc:
            return exc.code
        finally:
            session.close()
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: pay(), range(2)))
        assert sorted(results) == ["created", "sale_payment_exceeds_balance"]
        verify = SessionLocal()
        assert SalePaymentService(verify).repository.active_total(tenant_id, sale_id) == Decimal("70.00")
        verify.close()
    finally:
        cleanup = SessionLocal()
        cleanup.execute(delete(SalePayment).where(SalePayment.tenant_id == tenant_id))
        cleanup.execute(delete(SaleItem).where(SaleItem.tenant_id == tenant_id))
        cleanup.execute(delete(Sale).where(Sale.tenant_id == tenant_id))
        cleanup.execute(delete(PaymentMethod).where(PaymentMethod.tenant_id == tenant_id))
        cleanup.execute(delete(Tenant).where(Tenant.id == tenant_id))
        cleanup.commit(); cleanup.close()

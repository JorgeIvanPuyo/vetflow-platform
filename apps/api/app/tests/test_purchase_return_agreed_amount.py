"""Supplier agreement, historical gross reference and stock share the existing return flow."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.purchase_return import PurchaseReturn
from app.services.inventory import InventoryService
from app.tests.test_purchase_discounts import _setup, _body, _read, _receive, _headers
from app.tests.test_purchase_returns import _return_payload, _confirm

pytestmark = pytest.mark.usefixtures("allow_supplier_mutations")


def _received(client, tenant, *, discount=True):
    item, supplier = _setup(client, tenant)
    body = _body(item, supplier, **({"discount_type": "percentage", "discount_value": "10"} if discount else {}))
    body["items"][0]["quantity"] = "10"
    response = client.post("/api/v1/purchases", headers=_headers(tenant), json=body)
    assert response.status_code == 201, response.text
    purchase_id = response.json()["data"]["id"]
    assert _receive(client, tenant, purchase_id).status_code == 200
    return item, _read(client, tenant, purchase_id)


def _draft(client, tenant, purchase, **changes):
    response = client.post(
        f"/api/v1/purchases/{purchase['id']}/returns", headers=_headers(tenant),
        json=_return_payload(purchase, [(0, "2")], **changes),
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _out_count(db_session, tenant):
    return db_session.scalar(select(func.count()).select_from(InventoryMovement).where(
        InventoryMovement.tenant_id == tenant.id, InventoryMovement.movement_type == "purchase_return",
    ))


def _stock(db_session, item):
    db_session.expire_all()
    return db_session.get(InventoryItem, uuid.UUID(item["id"])).current_stock


@pytest.mark.parametrize("amount", ["1700.00", "0.00"])
def test_discounted_return_agreement_persists_without_repricing_or_duplicate_stock(client, tenant, db_session, amount):
    item, purchase = _received(client, tenant)
    assert purchase["amount_payable_ars"] == "9000.00" and purchase["can_register_return"] is True
    original_catalog = client.get(f"/api/v1/inventory/items/{item['id']}", headers=_headers(tenant)).json()["data"]
    draft = _draft(client, tenant, purchase)
    assert draft["agreed_amount_ars"] is None and _stock(db_session, item) == 10
    endpoint = f"/api/v1/purchase-returns/{draft['id']}"
    updated = client.patch(endpoint, headers=_headers(tenant), json={"agreed_amount_ars": amount})
    assert updated.status_code == 200, updated.text
    # An omitted amount on another draft edit preserves the agreement.
    assert client.patch(endpoint, headers=_headers(tenant), json={"reason": "Acuerdo confirmado con proveedor"}).json()["data"]["agreed_amount_ars"] == amount
    confirmed = _confirm(client, tenant, draft["id"])
    assert confirmed.status_code == 200, confirmed.text
    saved = client.get(endpoint, headers=_headers(tenant)).json()["data"]
    assert saved["status"] == "confirmed" and saved["agreed_amount_ars"] == amount
    assert saved["total_ars"] == "2000.00" and saved["tax_total_ars"] == "0.00"
    assert saved["items"][0]["unit_price_without_tax_ars"] == "1000.00"
    assert db_session.scalar(select(PurchaseReturn.agreed_amount_ars).where(PurchaseReturn.tenant_id == tenant.id, PurchaseReturn.id == uuid.UUID(draft["id"]))) == Decimal(amount)
    assert _confirm(client, tenant, draft["id"]).status_code == 409
    assert client.patch(endpoint, headers=_headers(tenant), json={"agreed_amount_ars": "1"}).status_code == 409
    assert _stock(db_session, item) == 8 and _out_count(db_session, tenant) == 1
    catalog = client.get(f"/api/v1/inventory/items/{item['id']}", headers=_headers(tenant)).json()["data"]
    for key in ("purchase_price_ars", "profit_margin_percentage", "sale_price_ars", "purchase_tax_rate_percentage", "sale_tax_rate_percentage", "sale_price_is_manual"):
        assert catalog[key] == original_catalog[key]
    assert catalog["purchase_price_ars"] == "1000.00" and catalog["sale_price_ars"] == "1300.00"
    after = _read(client, tenant, purchase["id"])
    for key in ("total_ars", "subtotal_ars", "tax_total_ars", "discount_type", "discount_value", "discount_amount_ars", "amount_payable_ars", "status"):
        assert after[key] == purchase[key]
    for key in ("quantity", "unit_price_without_tax_ars", "line_subtotal_ars", "line_total_ars", "tax_rate_percentage"):
        assert after["items"][0][key] == purchase["items"][0][key]
    assert after["returns"][0]["agreed_amount_ars"] == amount
    listed = client.get("/api/v1/purchase-returns", headers=_headers(tenant)).json()["data"]
    assert listed[0]["agreed_amount_ars"] == amount
    summary = client.get("/api/v1/purchases/dashboard?date_from=2026-08-01&date_to=2026-08-31", headers=_headers(tenant)).json()["data"]["summary"]
    assert Decimal(summary["net_received_amount_payable_ars"]) == Decimal("9000") - Decimal(amount)
    assert summary["returned_total_ars"] == "2000.00"  # gross reference stays compatible


def test_agreement_can_be_cleared_in_draft_but_is_required_before_confirmation(client, tenant, db_session):
    item, purchase = _received(client, tenant)
    draft = _draft(client, tenant, purchase, agreed_amount_ars="1700")
    response = client.patch(f"/api/v1/purchase-returns/{draft['id']}", headers=_headers(tenant), json={"agreed_amount_ars": None})
    assert response.status_code == 200 and response.json()["data"]["agreed_amount_ars"] is None
    confirmed = _confirm(client, tenant, draft["id"])
    assert confirmed.status_code == 422
    assert confirmed.json()["error"]["code"] == "purchase_return_agreed_amount_required"
    assert _stock(db_session, item) == 10 and _out_count(db_session, tenant) == 0
    assert client.get(f"/api/v1/purchase-returns/{draft['id']}", headers=_headers(tenant)).json()["data"]["status"] == "draft"


@pytest.mark.parametrize("invalid", ["-1", "NaN", "Infinity", "-Infinity", "1.001", "100000000000000"])
def test_invalid_agreement_rejected_on_create_and_edit_without_stock_change(client, tenant, db_session, invalid):
    item, purchase = _received(client, tenant)
    payload = _return_payload(purchase, [(0, "2")], agreed_amount_ars=invalid)
    response = client.post(f"/api/v1/purchases/{purchase['id']}/returns", headers=_headers(tenant), json=payload)
    assert response.status_code == 422, response.text
    draft = _draft(client, tenant, purchase)
    assert client.patch(f"/api/v1/purchase-returns/{draft['id']}", headers=_headers(tenant), json={"agreed_amount_ars": invalid}).status_code == 422
    assert _confirm(client, tenant, draft["id"]).status_code == 422
    assert _stock(db_session, item) == 10 and _out_count(db_session, tenant) == 0


@pytest.mark.parametrize("discount", [False, True])
def test_agreement_and_return_stock_remain_atomic_on_movement_failure(client, tenant, db_session, monkeypatch, discount):
    item, purchase = _received(client, tenant, discount=discount)
    draft = _draft(client, tenant, purchase, **({"agreed_amount_ars": "1700"} if discount else {}))
    original = InventoryService.register_purchase_return_movement

    def fail_after_movement(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("isolated return movement failure")

    with monkeypatch.context() as patch:
        patch.setattr(InventoryService, "register_purchase_return_movement", fail_after_movement)
        with pytest.raises(RuntimeError, match="isolated return movement failure"):
            _confirm(client, tenant, draft["id"])
    assert _stock(db_session, item) == 10 and _out_count(db_session, tenant) == 0
    saved = client.get(f"/api/v1/purchase-returns/{draft['id']}", headers=_headers(tenant)).json()["data"]
    assert saved["status"] == "draft" and saved["agreed_amount_ars"] == ("1700.00" if discount else None)
    assert _confirm(client, tenant, draft["id"]).status_code == 200
    assert _stock(db_session, item) == 8 and _out_count(db_session, tenant) == 1


def test_agreement_is_tenant_scoped(client, tenant, other_tenant, db_session):
    item, purchase = _received(client, tenant)
    draft = _draft(client, tenant, purchase, agreed_amount_ars="1700")
    foreign = _headers(other_tenant)
    endpoint = f"/api/v1/purchase-returns/{draft['id']}"
    assert client.get(endpoint, headers=foreign).status_code == 404
    assert client.patch(endpoint, headers=foreign, json={"agreed_amount_ars": "0"}).status_code == 404
    assert client.post(endpoint + "/confirm", headers=foreign, json={"confirm": True}).status_code == 404
    assert client.post(f"/api/v1/purchases/{purchase['id']}/returns", headers=foreign, json=_return_payload(purchase, [(0, "2")], agreed_amount_ars="0")).status_code == 404
    assert client.get("/api/v1/purchase-returns", headers=foreign).json()["data"] == []
    assert _stock(db_session, item) == 10 and _out_count(db_session, tenant) == 0
    assert client.get(endpoint, headers=_headers(tenant)).json()["data"]["agreed_amount_ars"] == "1700.00"

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text

from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.purchase import Purchase
from app.models.purchase_return import PurchaseReturn
from app.tests.test_purchases import _headers, _create_inventory_item, _create_supplier, _payload, _create_user

pytestmark = pytest.mark.usefixtures("allow_supplier_mutations")


def _setup(client, tenant):
    item = _create_inventory_item(client, tenant)
    response = client.patch(f"/api/v1/inventory/items/{item['id']}", headers=_headers(tenant), json={
        "purchase_price_ars": "1000", "purchase_tax_rate_percentage": "0", "profit_margin_percentage": "30",
    })
    assert response.status_code == 200
    supplier = _create_supplier(client, tenant, name=f"Proveedor {uuid.uuid4().hex[:8]}", tax_id=None)
    return item, supplier


def _body(item, supplier, **changes):
    return _payload(item["id"], supplier["id"], items=[{
        "inventory_item_id": item["id"], "quantity": "1", "unit_price_without_tax_ars": "1000", "tax_rate_percentage": "0",
    }], **changes)


def _create(client, tenant, item, supplier, **discount):
    response = client.post("/api/v1/purchases", headers=_headers(tenant), json=_body(item, supplier, **discount))
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _read(client, tenant, id_):
    response = client.get(f"/api/v1/purchases/{id_}", headers=_headers(tenant))
    assert response.status_code == 200
    return response.json()["data"]


def _receive(client, tenant, id_):
    return client.post(f"/api/v1/purchases/{id_}/receive", headers=_headers(tenant), json={"confirm": True})


@pytest.mark.parametrize(("discount", "amount", "net"), [
    ({}, "0.00", "1000.00"),
    ({"discount_type": "percentage", "discount_value": "10"}, "100.00", "900.00"),
    ({"discount_type": "amount", "discount_value": "150"}, "150.00", "850.00"),
])
def test_purchase_discount_persists_and_keeps_original_totals(client, tenant, discount, amount, net):
    item, supplier = _setup(client, tenant)
    data = _create(client, tenant, item, supplier, **discount)
    read = _read(client, tenant, data["id"])
    for result in (data, read):
        assert result["total_ars"] == "1000.00"
        assert result["discount_amount_ars"] == amount
        assert result["amount_payable_ars"] == net
        assert result["items"][0]["unit_price_without_tax_ars"] == "1000.00"
        assert result["items"][0]["line_total_ars"] == "1000.00"
    listed = client.get("/api/v1/purchases", headers=_headers(tenant)).json()
    assert listed["data"][0]["discount_amount_ars"] == amount
    assert listed["meta"]["summary"]["total_ars"] == "1000.00"
    assert listed["meta"]["summary"]["amount_payable_ars"] == net


def test_discounted_receipt_uses_original_cost_once_and_reversal_preserves_money(client, tenant, db_session):
    item, supplier = _setup(client, tenant)
    data = _create(client, tenant, item, supplier, discount_type="percentage", discount_value="10")
    assert _receive(client, tenant, data["id"]).status_code == 200
    assert _receive(client, tenant, data["id"]).status_code == 409
    model = db_session.get(InventoryItem, uuid.UUID(item["id"]))
    db_session.refresh(model)
    assert (model.purchase_price_ars, model.sale_price_ars, model.current_stock) == (Decimal("1000"), Decimal("1300"), Decimal("1"))
    movement = db_session.scalar(select(InventoryMovement).where(InventoryMovement.tenant_id == tenant.id))
    assert movement.unit_cost_ars == 1000 and movement.total_cost_ars == 1000
    read = _read(client, tenant, data["id"])
    assert (read["total_ars"], read["amount_payable_ars"]) == ("1000.00", "900.00")
    reversed_ = client.post(f"/api/v1/purchases/{data['id']}/reverse-receipt", headers=_headers(tenant), json={"reason": "Corrección"})
    assert reversed_.status_code == 200
    assert reversed_.json()["data"]["discount_amount_ars"] == "100.00"
    assert reversed_.json()["data"]["amount_payable_ars"] == "900.00"
    assert db_session.scalar(select(func.count()).select_from(InventoryMovement)) == 2


def test_discount_rounds_once_on_global_total_including_line_tax(client, tenant):
    item, supplier = _setup(client, tenant)
    second = _create_inventory_item(client, tenant, name="Segundo")
    body = _body(item, supplier, discount_type="percentage", discount_value="10")
    body["items"] = [{"inventory_item_id": product["id"], "quantity": "1", "unit_price_without_tax_ars": "0.05", "tax_rate_percentage": "21"} for product in (item, second)]
    response = client.post("/api/v1/purchases", headers=_headers(tenant), json=body)
    assert response.status_code == 201
    data = response.json()["data"]
    assert (data["subtotal_ars"], data["tax_total_ars"], data["total_ars"]) == ("0.10", "0.02", "0.12")
    assert data["discount_amount_ars"] == "0.01"  # Discount per product would incorrectly total 0.02.
    assert data["amount_payable_ars"] == "0.11"
    assert all(line["line_total_ars"] == "0.06" and line["line_tax_ars"] == "0.01" for line in data["items"])


def test_draft_edits_preserve_omissions_recalculate_percentage_and_explicitly_remove(client, tenant):
    item, supplier = _setup(client, tenant)
    data = _create(client, tenant, item, supplier, discount_type="percentage", discount_value="10")
    endpoint = f"/api/v1/purchases/{data['id']}"
    response = client.patch(endpoint, headers=_headers(tenant), json={"notes": "Otra nota"})
    assert response.status_code == 200
    assert response.json()["data"]["discount_value"] == "10.00"
    line = _body(item, supplier)["items"][0]
    response = client.patch(endpoint, headers=_headers(tenant), json={"items": [{**line, "quantity": "2"}]})
    assert response.status_code == 200
    assert (response.json()["data"]["total_ars"], response.json()["data"]["discount_amount_ars"]) == ("2000.00", "200.00")
    response = client.patch(endpoint, headers=_headers(tenant), json={"discount_type": "amount", "discount_value": "150"})
    assert response.json()["data"]["amount_payable_ars"] == "1850.00"
    fixed_edit = client.patch(endpoint, headers=_headers(tenant), json={"items": [{**line, "quantity": "3"}]})
    assert fixed_edit.status_code == 200
    assert fixed_edit.json()["data"]["discount_amount_ars"] == "150.00"
    assert fixed_edit.json()["data"]["amount_payable_ars"] == "2850.00"
    before = _read(client, tenant, data["id"])
    rejected = client.patch(endpoint, headers=_headers(tenant), json={"notes": "No guardar", "items": [{**line, "unit_price_without_tax_ars": "100"}]})
    assert rejected.status_code == 422
    after = _read(client, tenant, data["id"])
    assert after["items"] == before["items"] and after["notes"] == "Otra nota"
    assert after["amount_payable_ars"] == "2850.00"
    removed = client.patch(endpoint, headers=_headers(tenant), json={"discount_type": "none"}).json()["data"]
    assert (removed["discount_type"], removed["discount_value"], removed["discount_amount_ars"], removed["amount_payable_ars"]) == ("none", "0.00", "0.00", "3000.00")


@pytest.mark.parametrize("discount", [
    {"discount_type": "percentage", "discount_value": "-1"},
    {"discount_type": "amount", "discount_value": "-1"},
    {"discount_type": "percentage", "discount_value": "100.01"},
    {"discount_type": "amount", "discount_value": "1000.01"},
    {"discount_type": "amount", "discount_value": "0.001"},
    *[{"discount_type": "amount", "discount_value": value} for value in ("NaN", "Infinity", "-Infinity")],
    {"discount_type": "none", "discount_value": "10"},
    {"discount_type": "percentage"}, {"discount_value": "10"},
    {"discount_type": None}, {"discount_type": "amount", "discount_value": None},
    {"discount_type": "unknown", "discount_value": "10"},
    {"discount_amount_ars": "100"}, {"amount_payable_ars": "1"},
    {"discount_type": "percentage", "discount_value": "10", "discount_percentage": "5"},
])
def test_invalid_discounts_do_not_create_partial_purchase(client, tenant, db_session, discount):
    item, supplier = _setup(client, tenant)
    response = client.post("/api/v1/purchases", headers=_headers(tenant), json=_body(item, supplier, **discount))
    assert response.status_code == 422
    assert db_session.scalar(select(func.count()).select_from(Purchase)) == 0
    assert db_session.scalar(select(func.count()).select_from(InventoryMovement)) == 0


@pytest.mark.parametrize(("type_", "value", "net"), [
    ("percentage", "0", "1000.00"), ("percentage", "100", "0.00"),
    ("amount", "0", "1000.00"), ("amount", "1000", "0.00"),
])
def test_zero_and_complete_discounts_do_not_create_financial_movements(client, tenant, db_session, type_, value, net):
    item, supplier = _setup(client, tenant)
    data = _create(client, tenant, item, supplier, discount_type=type_, discount_value=value)
    assert data["amount_payable_ars"] == net
    assert db_session.scalar(text("SELECT count(*) FROM sale_payments")) == 0
    assert db_session.scalar(select(func.count()).select_from(InventoryMovement)) == 0
    assert _receive(client, tenant, data["id"]).status_code == 200
    assert db_session.scalar(text("SELECT count(*) FROM sale_payments")) == 0
    read = _read(client, tenant, data["id"])
    assert read["amount_payable_ars"] == net
    assert read["items"][0]["unit_price_without_tax_ars"] == "1000.00"


@pytest.mark.parametrize("state", ["received", "cancelled", "reversed"])
def test_discount_is_immutable_after_leaving_draft(client, tenant, state):
    item, supplier = _setup(client, tenant)
    data = _create(client, tenant, item, supplier, discount_type="amount", discount_value="150")
    endpoint = f"/api/v1/purchases/{data['id']}"
    if state == "cancelled":
        assert client.post(endpoint + "/cancel", headers=_headers(tenant), json={"reason": "Corrección"}).status_code == 200
    else:
        assert _receive(client, tenant, data["id"]).status_code == 200
        if state == "reversed":
            assert client.post(endpoint + "/reverse-receipt", headers=_headers(tenant), json={"reason": "Corrección"}).status_code == 200
    response = client.patch(endpoint, headers=_headers(tenant), json={"discount_type": "none", "notes": "No cambiar"})
    assert response.status_code == 409
    read = _read(client, tenant, data["id"])
    assert read["discount_amount_ars"] == "150.00" and read["amount_payable_ars"] == "850.00"
    assert read["notes"] != "No cambiar"


def test_discount_writes_and_money_reads_are_tenant_scoped_and_keep_auth(client, tenant, other_tenant, db_session):
    item, supplier = _setup(client, tenant)
    foreign_item, foreign_supplier = _setup(client, other_tenant)
    data = _create(client, tenant, item, supplier, discount_type="percentage", discount_value="10")
    assert client.patch(f"/api/v1/purchases/{data['id']}", headers=_headers(other_tenant), json={"discount_type": "none"}).status_code == 404
    assert client.get(f"/api/v1/purchases/{data['id']}", headers=_headers(other_tenant)).status_code == 404
    assert _receive(client, other_tenant, data["id"]).status_code == 404
    for product, vendor in [(foreign_item, supplier), (item, foreign_supplier)]:
        assert client.post("/api/v1/purchases", headers=_headers(tenant), json=_body(product, vendor, discount_type="amount", discount_value="1")).status_code == 404
    user = _create_user(db_session, tenant)
    user.is_active = False; db_session.commit()
    assert client.patch(f"/api/v1/purchases/{data['id']}", headers={"X-User-Email": user.email}, json={"discount_type": "none"}).status_code == 403
    assert _read(client, tenant, data["id"])["discount_amount_ars"] == "100.00"


def test_financial_summary_and_dashboard_expose_net_without_redefining_gross(client, tenant, other_tenant):
    item, supplier = _setup(client, tenant)
    draft = _create(client, tenant, item, supplier, discount_type="percentage", discount_value="10")
    received = _create(client, tenant, item, supplier, discount_type="amount", discount_value="150")
    assert _receive(client, tenant, received["id"]).status_code == 200
    other_item, other_supplier = _setup(client, other_tenant)
    _create(client, other_tenant, other_item, other_supplier, discount_type="percentage", discount_value="50")
    listed = client.get("/api/v1/purchases?page_size=1", headers=_headers(tenant)).json()
    assert listed["meta"]["summary"]["total_ars"] == "2000.00"
    assert listed["meta"]["summary"]["discount_amount_ars"] == "250.00"
    assert listed["meta"]["summary"]["amount_payable_ars"] == "1750.00"
    dashboard = client.get("/api/v1/purchases/dashboard?date_from=2026-08-01&date_to=2026-08-31", headers=_headers(tenant)).json()["data"]
    summary = dashboard["summary"]
    assert summary["registered_total_ars"] == "2000.00" and summary["registered_amount_payable_ars"] == "1750.00"
    assert summary["received_total_ars"] == "1000.00" and summary["received_amount_payable_ars"] == "850.00"
    assert summary["net_received_amount_payable_ars"] == "850.00"
    assert dashboard["top_suppliers"][0]["received_amount_payable_ars"] == "850.00"
    assert {r["id"] for r in dashboard["recent_purchases"]} == {draft["id"], received["id"]}
    assert {r["amount_payable_ars"] for r in dashboard["recent_purchases"]} == {"900.00", "850.00"}


def test_discounted_purchase_does_not_invent_a_gross_return_amount(client, tenant, db_session):
    item, supplier = _setup(client, tenant)
    data = _create(client, tenant, item, supplier, discount_type="percentage", discount_value="10")
    assert _receive(client, tenant, data["id"]).status_code == 200
    read = _read(client, tenant, data["id"])
    assert read["can_register_return"] is True
    response = client.post(f"/api/v1/purchases/{data['id']}/returns", headers=_headers(tenant), json={
        "return_date": "2026-08-09", "reason": "Devolver", "items": [{"purchase_item_id": read["items"][0]["id"], "quantity": "1"}],
    })
    assert response.status_code == 201
    draft = response.json()["data"]
    assert draft["agreed_amount_ars"] is None
    assert draft["total_ars"] == "1000.00"
    confirmation = client.post(f"/api/v1/purchase-returns/{draft['id']}/confirm", headers=_headers(tenant), json={"confirm": True})
    assert confirmation.status_code == 422
    assert confirmation.json()["error"]["code"] == "purchase_return_agreed_amount_required"
    assert db_session.scalar(select(func.count()).select_from(PurchaseReturn).where(PurchaseReturn.status == "confirmed")) == 0
    model = db_session.get(InventoryItem, uuid.UUID(item["id"]))
    db_session.refresh(model)
    assert model.current_stock == 1 and model.sale_price_ars == 1300


@pytest.mark.parametrize(("line_cost", "expected_cost", "expected_sale"), [("1200", "1200", "1560"), ("900", "1000", "1300")])
def test_receipt_compares_undiscounted_unit_cost_not_discounted_purchase_total(client, tenant, db_session, line_cost, expected_cost, expected_sale):
    item, supplier = _setup(client, tenant)
    body = _body(item, supplier, discount_type="percentage", discount_value="90")
    body["items"][0]["unit_price_without_tax_ars"] = line_cost
    response = client.post("/api/v1/purchases", headers=_headers(tenant), json=body)
    assert response.status_code == 201
    purchase = response.json()["data"]
    assert _receive(client, tenant, purchase["id"]).status_code == 200
    product = db_session.get(InventoryItem, uuid.UUID(item["id"]))
    db_session.refresh(product)
    assert product.purchase_price_ars == Decimal(expected_cost)
    assert product.sale_price_ars == Decimal(expected_sale)
    assert product.current_stock == 1
    read = _read(client, tenant, purchase["id"])
    assert Decimal(read["amount_payable_ars"]) == Decimal(line_cost) / 10
    assert Decimal(read["items"][0]["unit_price_without_tax_ars"]) == Decimal(line_cost)


@pytest.mark.parametrize("change", [
    {"discount_type": None}, {"discount_value": None}, {"discount_value": "0"},
    {"discount_type": "percentage"}, {"discount_type": "amount", "discount_value": "-1"},
])
def test_update_requires_a_valid_explicit_pair_and_keeps_previous_discount_on_error(client, tenant, change):
    item, supplier = _setup(client, tenant)
    data = _create(client, tenant, item, supplier, discount_type="percentage", discount_value="10")
    response = client.patch(f"/api/v1/purchases/{data['id']}", headers=_headers(tenant), json=change)
    assert response.status_code == 422
    persisted = _read(client, tenant, data["id"])
    assert (persisted["discount_type"], persisted["discount_value"], persisted["discount_amount_ars"], persisted["amount_payable_ars"]) == ("percentage", "10.00", "100.00", "900.00")

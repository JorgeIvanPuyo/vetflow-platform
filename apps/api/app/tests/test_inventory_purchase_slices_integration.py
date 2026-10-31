"""Joint catalog, bulk-price and purchase-discount regression in isolated SQLite."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.tests.test_inventory import _create_item
from app.tests.test_purchase_discounts import _setup, _body, _receive, _read, _headers, _create

pytestmark = pytest.mark.usefixtures("allow_supplier_mutations")


def test_discounted_receipt_bulk_price_manual_reference_and_next_receipt(client, tenant, db_session):
    item, supplier = _setup(client, tenant)
    endpoint = f"/api/v1/inventory/items/{item['id']}"
    first_payload = _body(item, supplier, discount_type="percentage", discount_value="10")
    first_payload["items"][0].update(quantity="2", unit_price_without_tax_ars="1200")
    created = client.post("/api/v1/purchases", headers=_headers(tenant), json=first_payload)
    assert created.status_code == 201, created.text
    first_id = created.json()["data"]["id"]
    received = _receive(client, tenant, first_id)
    assert received.status_code == 200, received.text
    first_history = _read(client, tenant, first_id)
    assert (first_history["total_ars"], first_history["discount_amount_ars"], first_history["amount_payable_ars"]) == ("2400.00", "240.00", "2160.00")

    def catalog():
        response = client.get(endpoint, headers=_headers(tenant))
        assert response.status_code == 200
        product = response.json()["data"]
        assert product["sale_price_is_manual"] is False
        return tuple(Decimal(product[key]) for key in ("purchase_price_ars", "profit_margin_percentage", "sale_price_ars", "current_stock"))

    assert catalog() == (Decimal("1200"), Decimal("30"), Decimal("1560"), Decimal("2"))
    preview = client.post("/api/v1/inventory/bulk-operations/preview", headers=_headers(tenant), json={
        "selection": {"selection_mode": "selected", "selected_ids": [item["id"]]},
        "operation": {"operation_type": "increase_sale_price_percentage", "percentage": "10"},
    })
    assert preview.status_code == 201, preview.text
    operation = preview.json()["data"]
    assert operation["items"][0]["new_value_json"]["value"] == {"profit_margin_percentage": "43.00", "sale_price_ars": "1716.00"}
    confirmed = client.post(f"/api/v1/inventory/bulk-operations/{operation['id']}/confirm", headers=_headers(tenant), json={"confirm": True})
    assert confirmed.status_code == 200, confirmed.text
    assert catalog() == (Decimal("1200"), Decimal("43"), Decimal("1716"), Decimal("2"))
    edited = client.patch(endpoint, headers=_headers(tenant), json={"purchase_price_ars": "900"})
    assert edited.status_code == 200, edited.text
    assert catalog() == (Decimal("900"), Decimal("43"), Decimal("1287"), Decimal("2"))

    second_payload = _body(item, supplier)
    second_payload["items"][0]["unit_price_without_tax_ars"] = "950"
    second = client.post("/api/v1/purchases", headers=_headers(tenant), json=second_payload)
    assert second.status_code == 201, second.text
    assert _receive(client, tenant, second.json()["data"]["id"]).status_code == 200
    assert catalog() == (Decimal("950"), Decimal("43"), Decimal("1358.50"), Decimal("3"))
    assert _receive(client, tenant, first_id).status_code == 409
    assert _read(client, tenant, first_id) == first_history
    assert first_history["items"][0]["unit_price_without_tax_ars"] == "1200.00"
    movements = list(db_session.scalars(select(InventoryMovement).where(InventoryMovement.tenant_id == tenant.id, InventoryMovement.movement_type == "purchase")))
    assert len(movements) == 2 and sum(m.quantity for m in movements) == 3
    assert {m.unit_cost_ars for m in movements} == {Decimal("1200"), Decimal("950")}
    assert catalog()[-1] == 3


@pytest.mark.parametrize(("pending", "explicit_zero", "expected"), [(False, True, "0.00"), (True, False, None), (True, True, "0.00")])
def test_manual_exit_preserves_explicit_zero_and_does_not_use_pending_legacy_price(client, tenant, db_session, pending, explicit_zero, expected):
    item = _create_item(client, tenant, current_stock="2", purchase_price_ars=None if pending else "1000")
    if pending:
        legacy = db_session.get(InventoryItem, uuid.UUID(item["id"]))
        legacy.sale_price_ars = Decimal("999")
        legacy.sale_price_is_manual = True
        db_session.commit()
    payload = {"quantity": "1", "reason": "sale"}
    if explicit_zero:
        payload["unit_sale_price_ars"] = "0"
    response = client.post(f"/api/v1/inventory/items/{item['id']}/movements/exit", headers=_headers(tenant), json=payload)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["unit_sale_price_ars"] == expected and data["total_sale_price_ars"] == expected
    assert data["stock_after"] == "1.00"
    product = client.get(f"/api/v1/inventory/items/{item['id']}", headers=_headers(tenant)).json()["data"]
    assert product["sale_price_ars"] == ("999.00" if pending else "1350.00")


def test_zero_monetary_discount_keeps_automatic_return_available(client, tenant, db_session):
    item, supplier = _setup(client, tenant)
    purchase = _create(client, tenant, item, supplier, discount_type="percentage", discount_value="0")
    assert _receive(client, tenant, purchase["id"]).status_code == 200
    received = _read(client, tenant, purchase["id"])
    assert received["can_register_return"] is True
    created = client.post(f"/api/v1/purchases/{purchase['id']}/returns", headers=_headers(tenant), json={
        "return_date": "2026-10-30", "reason": "Regresión local de descuento cero",
        "items": [{"purchase_item_id": received["items"][0]["id"], "quantity": "1"}],
    })
    assert created.status_code == 201, created.text
    confirmed = client.post(f"/api/v1/purchase-returns/{created.json()['data']['id']}/confirm", headers=_headers(tenant), json={"confirm": True})
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["total_ars"] == "1000.00"
    product = db_session.get(InventoryItem, uuid.UUID(item["id"]))
    db_session.refresh(product)
    assert product.current_stock == 0 and product.purchase_price_ars == 1000 and product.sale_price_ars == 1300
    assert db_session.scalar(select(func.count()).select_from(InventoryMovement).where(InventoryMovement.tenant_id == tenant.id)) == 2

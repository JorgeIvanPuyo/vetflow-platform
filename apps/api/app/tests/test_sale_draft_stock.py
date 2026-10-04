"""Draft stock is advisory, live, tenant-scoped and read in a batch."""
import uuid

from sqlalchemy import event, select

from app.models.inventory_item import InventoryItem
from app.models.sale import SaleItem
from app.tests.test_sales import _add_stock, _create, _headers, _payload, _product, _owner


def test_draft_create_update_live_stock_and_confirmation(client, tenant):
    product = _product(client, tenant)
    _add_stock(client, tenant, product["id"], 2)
    sale = _create(client, tenant, product["id"])
    assert sale["items"][0]["current_stock"] == "2.00"
    assert sale["items"][1]["current_stock"] is None
    payload = _payload(product["id"], owner_id=_owner(client, tenant)["id"])
    payload["items"][0]["quantity"] = "5"
    url = f"/api/v1/sales/{sale['id']}"
    updated = client.patch(url, headers=_headers(tenant), json=payload)
    assert updated.status_code == 200
    assert updated.json()["data"]["items"][0]["current_stock"] == "2.00"
    rejected = client.post(url + "/confirm", headers=_headers(tenant), json={"confirm": True})
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "sale_insufficient_stock"
    paused = _create(client, tenant, product["id"])
    _add_stock(client, tenant, product["id"], 3)
    reopened = client.get(url, headers=_headers(tenant)).json()["data"]
    assert reopened["items"][0]["current_stock"] == "5.00"
    assert reopened["items"][0]["quantity"] == "5.00"
    confirmed = client.post(url + "/confirm", headers=_headers(tenant), json={"confirm": True})
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["status"] == "confirmed"
    reopened = client.get(f"/api/v1/sales/{paused['id']}", headers=_headers(tenant)).json()["data"]
    assert reopened["items"][0]["current_stock"] == "0.00"


def test_stock_read_is_one_batch_query(client, db_session, tenant):
    items = [_payload(_product(client, tenant, name=f"Producto {i}")["id"])["items"][0] for i in range(8)]
    sale = _create(client, tenant, items=items)
    statements = []
    def record(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)
    event.listen(db_session.bind, "before_cursor_execute", record)
    try:
        result = client.get(f"/api/v1/sales/{sale['id']}", headers=_headers(tenant))
    finally:
        event.remove(db_session.bind, "before_cursor_execute", record)
    assert result.status_code == 200
    assert all(item["current_stock"] == "0.00" for item in result.json()["data"]["items"])
    stock_queries = [s for s in statements if "inventory_items.current_stock" in s]
    assert len(stock_queries) == 1
    assert "inventory_items.tenant_id =" in stock_queries[0]


def test_foreign_stock_not_exposed_even_with_corrupt_reference(client, db_session, tenant, other_tenant):
    own = _product(client, tenant)
    foreign = _product(client, other_tenant)
    _add_stock(client, other_tenant, foreign["id"], 73)
    sale = _create(client, tenant, own["id"])
    line = db_session.scalar(select(SaleItem).where(SaleItem.id == uuid.UUID(sale["items"][0]["id"]), SaleItem.tenant_id == tenant.id))
    line.inventory_item_id = uuid.UUID(foreign["id"])
    db_session.commit()
    response = client.get(f"/api/v1/sales/{sale['id']}", headers=_headers(tenant))
    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["current_stock"] is None
    assert client.get(f"/api/v1/sales/{sale['id']}", headers=_headers(other_tenant)).status_code == 404


def test_stock_response_does_not_cache_inventory_before_confirmation(client, db_session, tenant):
    product = _product(client, tenant)
    _add_stock(client, tenant, product["id"], 5)
    sale = _create(client, tenant, product["id"])
    tenant_id = tenant.id
    headers = _headers(tenant)
    db_session.expunge_all()
    assert client.get(f"/api/v1/sales/{sale['id']}", headers=headers).status_code == 200
    loaded = [obj for obj in db_session.identity_map.values() if isinstance(obj, InventoryItem)]
    assert all("current_stock" not in obj.__dict__ for obj in loaded)
    db_session.execute(InventoryItem.__table__.update().where(InventoryItem.id == uuid.UUID(product["id"]), InventoryItem.tenant_id == tenant_id).values(current_stock=0))
    db_session.commit()
    rejected = client.post(f"/api/v1/sales/{sale['id']}/confirm", headers=headers, json={"confirm": True})
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "sale_insufficient_stock"

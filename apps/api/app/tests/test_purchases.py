import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.purchase import Purchase, PurchaseItem
from app.models.user import User


pytestmark = pytest.mark.usefixtures("allow_supplier_mutations")
def _headers(tenant) -> dict[str, str]:
    return {"X-Tenant-Id": str(tenant.id)}


def _auth_headers(email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {email}"}


def _setup_auth(monkeypatch) -> None:
    import app.core.tenant as tenant_core

    monkeypatch.setattr(tenant_core, "verify_id_token", lambda token: {"email": token})


def _create_user(db_session, tenant, email="buyer@example.com", full_name="Comprador") -> User:
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=email,
        full_name=full_name,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_inventory_item(client, tenant, *, name="Amoxicilina", category="medication", unit="box"):
    response = client.post(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        json={
            "name": name,
            "category": category,
            "unit": unit,
            "minimum_stock": "0",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_supplier(
    client,
    tenant,
    *,
    name="Proveedor Uno",
    tax_id="30-12345678-9",
    headers=None,
):
    response = client.post(
        "/api/v1/suppliers",
        headers=headers or _headers(tenant),
        json={"name": name, "tax_id": tax_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _payload(item_id: str, supplier_id: str, **overrides) -> dict:
    payload = {
        "supplier_id": supplier_id,
        "purchase_date": "2026-08-09",
        "document_type": "invoice",
        "document_number": "0001-00001234",
        "notes": "Compra semanal",
        "items": [
            {
                "inventory_item_id": item_id,
                "quantity": "10",
                "unit_price_without_tax_ars": "1000.00",
                "tax_rate_percentage": "21",
            }
        ],
    }
    payload.update(overrides)
    return payload


def _create_purchase(client, tenant, item_id: str, **overrides) -> dict:
    supplier_id = overrides.pop("supplier_id", None)
    if supplier_id is None:
        supplier_name = overrides.pop("supplier_name", "Proveedor Uno")
        supplier_tax_id = overrides.pop(
            "supplier_tax_id",
            "30-12345678-9" if supplier_name == "Proveedor Uno" else None,
        )
        supplier = _create_supplier(
            client,
            tenant,
            name=supplier_name,
            tax_id=supplier_tax_id,
        )
        supplier_id = supplier["id"]
    response = client.post(
        "/api/v1/purchases",
        headers=_headers(tenant),
        json=_payload(item_id, supplier_id, **overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_purchase_requires_authentication(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()

    response = client.get("/api/v1/purchases")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_auth_token"


def test_create_purchase_calculates_snapshots_traceability_and_does_not_touch_stock(
    client, db_session, tenant, monkeypatch
):
    _setup_auth(monkeypatch)
    user = _create_user(db_session, tenant)
    item = _create_inventory_item(client, tenant, name="Vacuna Triple", category="vaccine", unit="dose")
    supplier = _create_supplier(client, tenant, headers=_auth_headers(user.email))
    stock_before = db_session.get(InventoryItem, uuid.UUID(item["id"])).current_stock

    response = client.post(
        "/api/v1/purchases",
        headers=_auth_headers(user.email),
        json=_payload(item["id"], supplier["id"]),
    )

    assert response.status_code == 201
    purchase = response.json()["data"]
    assert purchase["tenant_id"] == str(tenant.id)
    assert purchase["status"] == "draft"
    assert purchase["currency"] == "USD"
    assert purchase["supplier_name"] == "Proveedor Uno"
    assert purchase["supplier_tax_id"] == "30-12345678-9"
    assert purchase["purchase_date"] == "2026-08-09"
    assert purchase["created_by_user_id"] == str(user.id)
    assert purchase["created_by_user_name"] == "Comprador"
    assert purchase["created_by_user_email"] == user.email
    assert purchase["subtotal_ars"] == "10000.00"
    assert purchase["tax_total_ars"] == "2100.00"
    assert purchase["total_ars"] == "12100.00"
    assert len(purchase["items"]) == 1
    line = purchase["items"][0]
    assert line["description_snapshot"] == "Vacuna Triple"
    assert line["internal_code_snapshot"] == item["internal_code"]
    assert line["unit"] == "dose"
    assert line["unit_price_with_tax_ars"] == "1210.00"
    assert line["line_subtotal_ars"] == "10000.00"
    assert line["line_tax_ars"] == "2100.00"
    assert line["line_total_ars"] == "12100.00"
    db_session.expire_all()
    assert db_session.get(InventoryItem, uuid.UUID(item["id"])).current_stock == stock_before
    assert db_session.scalar(select(func.count()).select_from(InventoryMovement)) == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"supplier_name": "No permitido"},
        {"items": []},
        {"items": [{"inventory_item_id": "00000000-0000-0000-0000-000000000001", "quantity": "0", "unit_price_without_tax_ars": "1"}]},
        {"items": [{"inventory_item_id": "00000000-0000-0000-0000-000000000001", "quantity": "-1", "unit_price_without_tax_ars": "1"}]},
        {"items": [{"inventory_item_id": "00000000-0000-0000-0000-000000000001", "quantity": "1.5", "unit_price_without_tax_ars": "1"}]},
        {"items": [{"inventory_item_id": "00000000-0000-0000-0000-000000000001", "quantity": "1", "unit_price_without_tax_ars": "-1"}]},
        {"items": [{"inventory_item_id": "00000000-0000-0000-0000-000000000001", "quantity": "1", "unit_price_without_tax_ars": "1", "tax_rate_percentage": "-1"}]},
        {"items": [{"inventory_item_id": "00000000-0000-0000-0000-000000000001", "quantity": "1", "unit_price_without_tax_ars": "1", "tax_rate_percentage": "101"}]},
        {"total_ars": "1"},
        {"status": "received"},
        {"currency": "USD"},
    ],
)
def test_rejects_invalid_or_server_owned_create_fields(client, tenant, overrides):
    item = _create_inventory_item(client, tenant)
    supplier = _create_supplier(client, tenant)
    payload = _payload(item["id"], supplier["id"])
    payload.update(overrides)
    if "items" in overrides:
        for line in payload["items"]:
            if line["inventory_item_id"] == "00000000-0000-0000-0000-000000000001":
                line["inventory_item_id"] = item["id"]

    response = client.post("/api/v1/purchases", headers=_headers(tenant), json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_rejects_duplicate_and_cross_tenant_products(client, tenant, other_tenant):
    item = _create_inventory_item(client, tenant)
    foreign_item = _create_inventory_item(client, other_tenant, name="Producto ajeno")
    supplier = _create_supplier(client, tenant)
    duplicate_line = _payload(item["id"], supplier["id"])["items"][0]

    duplicate_response = client.post(
        "/api/v1/purchases",
        headers=_headers(tenant),
        json=_payload(item["id"], supplier["id"], items=[duplicate_line, duplicate_line]),
    )
    foreign_response = client.post(
        "/api/v1/purchases",
        headers=_headers(tenant),
        json=_payload(foreign_item["id"], supplier["id"]),
    )

    assert duplicate_response.status_code == 422
    assert duplicate_response.json()["error"]["code"] == "duplicate_purchase_item"
    assert foreign_response.status_code == 404
    assert foreign_response.json()["error"]["code"] == "inventory_item_not_found"


def test_tax_default_zero_custom_and_rounding(client, tenant):
    first = _create_inventory_item(client, tenant, name="Producto 1")
    second = _create_inventory_item(client, tenant, name="Producto 2")
    third = _create_inventory_item(client, tenant, name="Producto 3")

    purchase = _create_purchase(
        client,
        tenant,
        first["id"],
        items=[
            {"inventory_item_id": first["id"], "quantity": "3", "unit_price_without_tax_ars": "0.05"},
            {"inventory_item_id": second["id"], "quantity": "2", "unit_price_without_tax_ars": "100", "tax_rate_percentage": "0"},
            {"inventory_item_id": third["id"], "quantity": "1", "unit_price_without_tax_ars": "100", "tax_rate_percentage": "10.5"},
        ],
    )

    assert purchase["items"][0]["tax_rate_percentage"] == "0.00"
    assert purchase["items"][0]["line_subtotal_ars"] == "0.15"
    assert purchase["items"][0]["line_tax_ars"] == "0.00"
    assert purchase["items"][1]["line_tax_ars"] == "0.00"
    assert purchase["items"][2]["line_subtotal_ars"] == "100.00"
    assert purchase["items"][2]["line_tax_ars"] == "10.50"
    assert purchase["subtotal_ars"] == "300.15"
    assert purchase["tax_total_ars"] == "10.50"
    assert purchase["total_ars"] == "310.65"


def test_product_snapshot_is_historical(client, db_session, tenant):
    item = _create_inventory_item(client, tenant, name="Nombre original", unit="vial")
    purchase = _create_purchase(client, tenant, item["id"])
    inventory_item = db_session.get(InventoryItem, uuid.UUID(item["id"]))
    inventory_item.name = "Nombre nuevo"
    inventory_item.unit = "box"
    db_session.commit()

    response = client.get(f"/api/v1/purchases/{purchase['id']}", headers=_headers(tenant))

    assert response.status_code == 200
    line = response.json()["data"]["items"][0]
    assert line["description_snapshot"] == "Nombre original"
    assert line["unit"] == "vial"


def test_update_draft_replaces_lines_recalculates_and_preserves_creator(
    client, db_session, tenant, monkeypatch
):
    _setup_auth(monkeypatch)
    creator = _create_user(db_session, tenant)
    first = _create_inventory_item(client, tenant, name="Primero")
    second = _create_inventory_item(client, tenant, name="Segundo")
    supplier = _create_supplier(client, tenant, headers=_auth_headers(creator.email))
    edited_supplier = _create_supplier(
        client,
        tenant,
        name="Proveedor Editado",
        tax_id="30-98765432-1",
        headers=_auth_headers(creator.email),
    )
    create_response = client.post(
        "/api/v1/purchases",
        headers=_auth_headers(creator.email),
        json=_payload(first["id"], supplier["id"]),
    )
    purchase = create_response.json()["data"]

    response = client.patch(
        f"/api/v1/purchases/{purchase['id']}",
        headers=_auth_headers(creator.email),
        json={
            "supplier_id": edited_supplier["id"],
            "items": [
                {
                    "inventory_item_id": second["id"],
                    "quantity": "2",
                    "unit_price_without_tax_ars": "50",
                    "tax_rate_percentage": "0",
                }
            ],
        },
    )

    assert response.status_code == 200
    updated = response.json()["data"]
    assert updated["supplier_name"] == "Proveedor Editado"
    assert updated["created_by_user_id"] == str(creator.id)
    assert [line["inventory_item_id"] for line in updated["items"]] == [second["id"]]
    assert updated["subtotal_ars"] == "100.00"
    assert updated["tax_total_ars"] == "0.00"
    assert updated["total_ars"] == "100.00"
    assert updated["updated_at"] >= purchase["updated_at"]
    assert db_session.scalar(select(func.count()).select_from(PurchaseItem)) == 1


@pytest.mark.parametrize("quantity", ["1", "2", "250"])
def test_purchase_accepts_positive_integer_quantities(client, tenant, quantity):
    item = _create_inventory_item(client, tenant, name=f"Producto {quantity}")
    supplier = _create_supplier(
        client,
        tenant,
        name=f"Proveedor {quantity}",
        tax_id=f"INTEGER-{quantity}",
    )

    response = client.post(
        "/api/v1/purchases",
        headers=_headers(tenant),
        json=_payload(
            item["id"],
            supplier["id"],
            items=[
                {
                    "inventory_item_id": item["id"],
                    "quantity": quantity,
                    "unit_price_without_tax_ars": "1",
                    "tax_rate_percentage": "21",
                }
            ],
        ),
    )

    assert response.status_code == 201
    assert response.json()["data"]["items"][0]["quantity"] == f"{quantity}.00"


def test_update_draft_rejects_fractional_quantity(client, tenant):
    item = _create_inventory_item(client, tenant)
    purchase = _create_purchase(client, tenant, item["id"])

    response = client.patch(
        f"/api/v1/purchases/{purchase['id']}",
        headers=_headers(tenant),
        json={
            "items": [
                {
                    "inventory_item_id": item["id"],
                    "quantity": "1.5",
                    "unit_price_without_tax_ars": "1000",
                    "tax_rate_percentage": "21",
                }
            ]
        },
    )

    assert response.status_code == 422
    detail = client.get(
        f"/api/v1/purchases/{purchase['id']}", headers=_headers(tenant)
    ).json()["data"]
    assert detail["status"] == "draft"
    assert detail["items"][0]["quantity"] == "10.00"


def test_cancel_is_audited_immutable_and_keeps_lines_without_stock_effects(
    client, db_session, tenant, monkeypatch
):
    _setup_auth(monkeypatch)
    user = _create_user(db_session, tenant)
    item = _create_inventory_item(client, tenant)
    supplier = _create_supplier(client, tenant, headers=_auth_headers(user.email))
    purchase = client.post(
        "/api/v1/purchases",
        headers=_auth_headers(user.email),
        json=_payload(item["id"], supplier["id"]),
    ).json()["data"]

    empty_reason = client.post(
        f"/api/v1/purchases/{purchase['id']}/cancel",
        headers=_auth_headers(user.email),
        json={"reason": "   "},
    )
    response = client.post(
        f"/api/v1/purchases/{purchase['id']}/cancel",
        headers=_auth_headers(user.email),
        json={"reason": "Carga duplicada"},
    )
    update_response = client.patch(
        f"/api/v1/purchases/{purchase['id']}",
        headers=_auth_headers(user.email),
        json={"notes": "No permitido"},
    )
    second_cancel = client.post(
        f"/api/v1/purchases/{purchase['id']}/cancel",
        headers=_auth_headers(user.email),
        json={"reason": "Otra vez"},
    )

    assert empty_reason.status_code == 422
    assert response.status_code == 200
    cancelled = response.json()["data"]
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancellation_reason"] == "Carga duplicada"
    assert cancelled["cancelled_by_user_id"] == str(user.id)
    assert cancelled["cancelled_by_user_name"] == "Comprador"
    assert cancelled["cancelled_at"] is not None
    assert len(cancelled["items"]) == 1
    assert update_response.status_code == 409
    assert second_cancel.status_code == 409
    assert db_session.scalar(select(func.count()).select_from(Purchase)) == 1
    assert db_session.scalar(select(func.count()).select_from(PurchaseItem)) == 1
    assert db_session.get(InventoryItem, uuid.UUID(item["id"])).current_stock == Decimal("0")
    assert db_session.scalar(select(func.count()).select_from(InventoryMovement)) == 0
    supplier_detail = client.get(
        f"/api/v1/suppliers/{supplier['id']}", headers=_auth_headers(user.email)
    )
    assert supplier_detail.status_code == 200
    assert supplier_detail.json()["data"]["is_active"] is True


def test_purchase_access_and_relations_are_tenant_scoped(client, tenant, other_tenant):
    item = _create_inventory_item(client, tenant)
    purchase = _create_purchase(client, tenant, item["id"])

    detail = client.get(f"/api/v1/purchases/{purchase['id']}", headers=_headers(other_tenant))
    update = client.patch(
        f"/api/v1/purchases/{purchase['id']}",
        headers=_headers(other_tenant),
        json={"notes": "Ataque"},
    )
    cancel = client.post(
        f"/api/v1/purchases/{purchase['id']}/cancel",
        headers=_headers(other_tenant),
        json={"reason": "Ataque"},
    )
    listing = client.get("/api/v1/purchases", headers=_headers(other_tenant))

    assert detail.status_code == 404
    assert update.status_code == 404
    assert cancel.status_code == 404
    assert listing.status_code == 200
    assert listing.json()["data"] == []


def test_list_purchases_filters_paginates_searches_and_omits_full_lines(client, tenant):
    first_item = _create_inventory_item(client, tenant, name="Primero")
    second_item = _create_inventory_item(client, tenant, name="Segundo")
    first = _create_purchase(
        client,
        tenant,
        first_item["id"],
        supplier_name="Laboratorio Norte",
        purchase_date="2026-08-01",
        document_type="invoice",
        document_number="FAC-001",
    )
    second = _create_purchase(
        client,
        tenant,
        second_item["id"],
        supplier_name="Distribuidora Sur",
        purchase_date="2026-08-05",
        document_type="ticket",
        document_number="TIC-999",
    )
    client.post(
        f"/api/v1/purchases/{first['id']}/cancel",
        headers=_headers(tenant),
        json={"reason": "Prueba"},
    )

    search = client.get("/api/v1/purchases", headers=_headers(tenant), params={"search": "TIC-9"})
    supplier = client.get(
        "/api/v1/purchases", headers=_headers(tenant), params={"supplier": "laboratorio norte"}
    )
    filtered = client.get(
        "/api/v1/purchases",
        headers=_headers(tenant),
        params={
            "status": "draft",
            "document_type": "ticket",
            "date_from": "2026-08-02",
            "date_to": "2026-08-06",
        },
    )
    paged = client.get(
        "/api/v1/purchases",
        headers=_headers(tenant),
        params={"page": 1, "page_size": 1, "sort_by": "supplier_name", "sort_direction": "asc"},
    )

    assert [row["id"] for row in search.json()["data"]] == [second["id"]]
    assert [row["id"] for row in supplier.json()["data"]] == [first["id"]]
    assert [row["id"] for row in filtered.json()["data"]] == [second["id"]]
    assert paged.json()["meta"] == {
        "page": 1,
        "page_size": 1,
        "total": 2,
        "total_pages": 2,
        "summary": {
            "purchase_count": 2,
            "subtotal_ars": "20000.00",
            "tax_total_ars": "4200.00",
            "total_ars": "24200.00",
        },
    }
    assert paged.json()["data"][0]["item_count"] == 1
    assert "items" not in paged.json()["data"][0]


def test_list_filters_by_creator_and_validates_date_range(client, db_session, tenant, monkeypatch):
    _setup_auth(monkeypatch)
    user = _create_user(db_session, tenant)
    item = _create_inventory_item(client, tenant)
    supplier = _create_supplier(client, tenant, headers=_auth_headers(user.email))
    created = client.post(
        "/api/v1/purchases",
        headers=_auth_headers(user.email),
        json=_payload(item["id"], supplier["id"]),
    ).json()["data"]

    filtered = client.get(
        "/api/v1/purchases",
        headers=_auth_headers(user.email),
        params={"created_by_user_id": str(user.id)},
    )
    invalid_range = client.get(
        "/api/v1/purchases",
        headers=_auth_headers(user.email),
        params={"date_from": date(2026, 8, 10).isoformat(), "date_to": date(2026, 8, 1).isoformat()},
    )

    assert [row["id"] for row in filtered.json()["data"]] == [created["id"]]
    assert invalid_range.status_code == 422
    assert invalid_range.json()["error"]["code"] == "validation_error"


def test_purchase_requires_active_supplier_from_same_tenant(client, tenant, other_tenant):
    item = _create_inventory_item(client, tenant)
    local = _create_supplier(client, tenant)
    foreign = _create_supplier(client, other_tenant)
    client.patch(
        f"/api/v1/suppliers/{local['id']}",
        headers=_headers(tenant),
        json={"is_active": False},
    )

    inactive = client.post(
        "/api/v1/purchases",
        headers=_headers(tenant),
        json=_payload(item["id"], local["id"]),
    )
    cross_tenant = client.post(
        "/api/v1/purchases",
        headers=_headers(tenant),
        json=_payload(item["id"], foreign["id"]),
    )
    free_text = client.post(
        "/api/v1/purchases",
        headers=_headers(tenant),
        json={**_payload(item["id"], local["id"]), "supplier_name": "Ataque"},
    )
    missing_supplier_payload = _payload(item["id"], local["id"])
    missing_supplier_payload.pop("supplier_id")
    missing_supplier = client.post(
        "/api/v1/purchases",
        headers=_headers(tenant),
        json=missing_supplier_payload,
    )

    assert inactive.status_code == 409
    assert inactive.json()["error"]["code"] == "supplier_inactive"
    assert cross_tenant.status_code == 404
    assert cross_tenant.json()["error"]["code"] == "supplier_not_found"
    assert free_text.status_code == 422
    assert missing_supplier.status_code == 422


def test_purchase_preserves_supplier_snapshot_and_returns_current_summary(client, tenant):
    item = _create_inventory_item(client, tenant)
    supplier = _create_supplier(client, tenant)
    purchase = _create_purchase(client, tenant, item["id"], supplier_id=supplier["id"])

    client.patch(
        f"/api/v1/suppliers/{supplier['id']}",
        headers=_headers(tenant),
        json={"name": "Proveedor Renombrado", "tax_id": "30-99999999-9"},
    )
    detail = client.get(
        f"/api/v1/purchases/{purchase['id']}", headers=_headers(tenant)
    ).json()["data"]
    listing = client.get("/api/v1/purchases", headers=_headers(tenant)).json()["data"]

    assert detail["supplier_id"] == supplier["id"]
    assert detail["supplier_name"] == "Proveedor Uno"
    assert detail["supplier_tax_id"] == "30-12345678-9"
    assert detail["supplier"]["name"] == "Proveedor Renombrado"
    assert detail["supplier"]["tax_id"] == "30-99999999-9"
    assert listing[0]["supplier_name"] == "Proveedor Uno"
    assert listing[0]["supplier_tax_id"] == "30-12345678-9"


def test_draft_can_keep_inactive_supplier_but_only_switch_to_active(client, tenant):
    item = _create_inventory_item(client, tenant)
    original = _create_supplier(client, tenant)
    inactive = _create_supplier(
        client, tenant, name="Proveedor Inactivo", tax_id="30-00000000-1"
    )
    active = _create_supplier(client, tenant, name="Proveedor Activo", tax_id="30-00000000-2")
    purchase = _create_purchase(client, tenant, item["id"], supplier_id=original["id"])
    for supplier in (original, inactive):
        client.patch(
            f"/api/v1/suppliers/{supplier['id']}",
            headers=_headers(tenant),
            json={"is_active": False},
        )

    unchanged = client.patch(
        f"/api/v1/purchases/{purchase['id']}",
        headers=_headers(tenant),
        json={"supplier_id": original["id"], "notes": "Conservado"},
    )
    rejected = client.patch(
        f"/api/v1/purchases/{purchase['id']}",
        headers=_headers(tenant),
        json={"supplier_id": inactive["id"]},
    )
    switched = client.patch(
        f"/api/v1/purchases/{purchase['id']}",
        headers=_headers(tenant),
        json={"supplier_id": active["id"]},
    )

    assert unchanged.status_code == 200
    assert unchanged.json()["data"]["supplier_name"] == "Proveedor Uno"
    assert rejected.status_code == 409
    assert switched.status_code == 200
    assert switched.json()["data"]["supplier_name"] == "Proveedor Activo"


def test_list_filters_by_supplier_id(client, tenant, other_tenant):
    item = _create_inventory_item(client, tenant)
    first_supplier = _create_supplier(client, tenant)
    second_supplier = _create_supplier(
        client, tenant, name="Segundo Proveedor", tax_id="30-10000000-1"
    )
    foreign_supplier = _create_supplier(client, other_tenant)
    first = _create_purchase(client, tenant, item["id"], supplier_id=first_supplier["id"])
    _create_purchase(client, tenant, item["id"], supplier_id=second_supplier["id"])

    filtered = client.get(
        "/api/v1/purchases",
        headers=_headers(tenant),
        params={"supplier_id": first_supplier["id"]},
    )
    foreign_filter = client.get(
        "/api/v1/purchases",
        headers=_headers(tenant),
        params={"supplier_id": foreign_supplier["id"]},
    )

    assert [row["id"] for row in filtered.json()["data"]] == [first["id"]]
    assert foreign_filter.json()["data"] == []

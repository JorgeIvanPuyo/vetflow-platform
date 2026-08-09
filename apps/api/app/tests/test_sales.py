import uuid
from decimal import Decimal

import pytest
from sqlalchemy import event, func, select

from app.core.config import get_settings
from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.owner import Owner
from app.models.patient import Patient
from app.models.user import User


def _headers(tenant): return {"X-Tenant-Id": str(tenant.id)}
def _auth_headers(email): return {"Authorization": f"Bearer {email}"}


def _setup_auth(monkeypatch):
    import app.core.tenant as tenant_core
    monkeypatch.setattr(tenant_core, "verify_id_token", lambda token: {"email": token})


def _user(db, tenant, email="seller@example.com"):
    user = User(id=uuid.uuid4(), tenant_id=tenant.id, email=email, full_name="Vendedor", is_active=True)
    db.add(user); db.commit(); db.refresh(user); return user


def _owner(client, tenant, name="Ana Cliente"):
    response = client.post("/api/v1/owners", headers=_headers(tenant), json={"full_name": name, "document_id": "DNI-123", "phone": "555", "email": "ana@example.com"})
    assert response.status_code == 201
    return response.json()["data"]


def _patient(client, tenant, owner_id, name="Firulais"):
    response = client.post("/api/v1/patients", headers=_headers(tenant), json={"owner_id": owner_id, "name": name, "species": "canine"})
    assert response.status_code == 201
    return response.json()["data"]


def _product(client, tenant, name="Alimento", price="100.00", active=True):
    response = client.post("/api/v1/inventory/items", headers=_headers(tenant), json={"name": name, "category": "food", "unit": "unit", "minimum_stock": "0", "sale_price_ars": price, "is_active": active})
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _payload(product_id=None, **overrides):
    items = [{"line_type": "service", "description": "Consulta general", "quantity": "1", "unit_price_ars": "50.00", "discount_percentage": "0"}]
    if product_id:
        items.insert(0, {"line_type": "product", "inventory_item_id": product_id, "quantity": "2", "unit_price_ars": "100.00", "discount_percentage": "10"})
    payload = {"owner_id": None, "patient_id": None, "sale_date": "2026-08-09", "notes": "Borrador", "items": items}
    payload.update(overrides)
    return payload


def _create(client, tenant, product_id=None, **overrides):
    response = client.post("/api/v1/sales", headers=_headers(tenant), json=_payload(product_id, **overrides))
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _add_stock(client, tenant, product_id, quantity):
    response = client.post(
        f"/api/v1/inventory/items/{product_id}/movements/entry",
        headers=_headers(tenant),
        json={"quantity": str(quantity)},
    )
    assert response.status_code == 201, response.text


def test_sales_require_authentication(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production"); get_settings.cache_clear()
    response = client.get("/api/v1/sales")
    assert response.status_code == 401


def test_create_storefront_sale_snapshots_calculates_actor_and_never_touches_inventory(client, db_session, tenant, monkeypatch):
    _setup_auth(monkeypatch); user = _user(db_session, tenant); product = _product(client, tenant)
    model = db_session.scalar(select(InventoryItem).where(InventoryItem.id == uuid.UUID(product["id"]), InventoryItem.tenant_id == tenant.id))
    stock_before = model.current_stock
    response = client.post("/api/v1/sales", headers=_auth_headers(user.email), json=_payload(product["id"]))
    assert response.status_code == 201
    sale = response.json()["data"]
    assert sale["tenant_id"] == str(tenant.id) and sale["status"] == "draft" and sale["currency"] == "ARS"
    assert sale["owner_id"] is None and sale["patient_id"] is None
    assert sale["created_by_user_id"] == str(user.id) and sale["created_by_user_name"] == "Vendedor"
    assert sale["subtotal_ars"] == "250.00" and sale["discount_total_ars"] == "20.00" and sale["total_ars"] == "230.00"
    assert sale["items"][0]["description_snapshot"] == "Alimento"
    assert sale["items"][0]["internal_code_snapshot"] == product["internal_code"]
    assert sale["items"][1]["service_id"] is None and sale["items"][1]["unit_snapshot"] == "service"
    db_session.expire_all()
    assert db_session.scalar(select(InventoryItem.current_stock).where(InventoryItem.id == model.id)) == stock_before
    assert db_session.scalar(select(func.count()).select_from(InventoryMovement)) == 0


def test_owner_patient_consistency_snapshots_and_cross_tenant_rejections(client, db_session, tenant, other_tenant):
    owner = _owner(client, tenant); patient = _patient(client, tenant, owner["id"])
    other_owner = _owner(client, tenant, "Otro"); other_patient = _patient(client, tenant, other_owner["id"], "Michi")
    foreign_owner = _owner(client, other_tenant, "Ajeno"); foreign_patient = _patient(client, other_tenant, foreign_owner["id"], "Ajeno")
    product = _product(client, tenant)
    sale = _create(client, tenant, product["id"], owner_id=owner["id"], patient_id=patient["id"])
    assert sale["owner_name_snapshot"] == "Ana Cliente" and sale["owner_document_snapshot"] == "DNI-123"
    assert sale["patient_name_snapshot"] == "Firulais" and sale["patient_species_snapshot"] == "canine"
    owner_model = db_session.get(Owner, uuid.UUID(owner["id"])); patient_model = db_session.get(Patient, uuid.UUID(patient["id"]))
    owner_model.full_name = "Nombre cambiado"; patient_model.name = "Paciente cambiado"; db_session.commit()
    historical = client.get(f"/api/v1/sales/{sale['id']}", headers=_headers(tenant)).json()["data"]
    assert historical["owner_name_snapshot"] == "Ana Cliente" and historical["patient_name_snapshot"] == "Firulais"
    mismatch = client.post("/api/v1/sales", headers=_headers(tenant), json=_payload(product["id"], owner_id=owner["id"], patient_id=other_patient["id"]))
    no_owner = client.post("/api/v1/sales", headers=_headers(tenant), json=_payload(product["id"], patient_id=patient["id"]))
    cross_owner = client.post("/api/v1/sales", headers=_headers(tenant), json=_payload(product["id"], owner_id=foreign_owner["id"]))
    cross_patient = client.post("/api/v1/sales", headers=_headers(tenant), json=_payload(product["id"], owner_id=owner["id"], patient_id=foreign_patient["id"]))
    assert mismatch.status_code == 422 and no_owner.status_code == 422
    assert cross_owner.status_code == 404 and cross_patient.status_code == 404


@pytest.mark.parametrize("mutation", [
    {"items": []},
    {"items": [{"line_type": "service", "description": "X", "quantity": "0", "unit_price_ars": "1"}]},
    {"items": [{"line_type": "service", "description": "X", "quantity": "1.5", "unit_price_ars": "1"}]},
    {"items": [{"line_type": "service", "description": "X", "quantity": "1", "unit_price_ars": "-1"}]},
    {"items": [{"line_type": "service", "description": "X", "quantity": "1", "unit_price_ars": "1", "discount_percentage": "101"}]},
    {"total_ars": "1"}, {"subtotal_ars": "1"}, {"status": "cancelled"}, {"currency": "USD"},
])
def test_rejects_invalid_and_server_owned_fields(client, tenant, mutation):
    payload = _payload(); payload.update(mutation)
    response = client.post("/api/v1/sales", headers=_headers(tenant), json=payload)
    assert response.status_code == 422


def test_product_duplicate_cross_tenant_inactive_and_default_price(client, tenant, other_tenant):
    product = _product(client, tenant, price="123.45"); foreign = _product(client, other_tenant); inactive = _product(client, tenant, "Inactivo", active=False)
    base = {"line_type": "product", "inventory_item_id": product["id"], "quantity": "1", "unit_price_ars": None}
    duplicate = client.post("/api/v1/sales", headers=_headers(tenant), json=_payload(items=[base, base]))
    cross = client.post("/api/v1/sales", headers=_headers(tenant), json=_payload(items=[{**base, "inventory_item_id": foreign["id"]}]))
    inactive_response = client.post("/api/v1/sales", headers=_headers(tenant), json=_payload(items=[{**base, "inventory_item_id": inactive["id"]}]))
    valid = client.post("/api/v1/sales", headers=_headers(tenant), json=_payload(items=[base]))
    assert duplicate.status_code == 422 and duplicate.json()["error"]["code"] == "duplicate_sale_product"
    assert cross.status_code == 404 and inactive_response.status_code == 409
    assert valid.status_code == 201 and valid.json()["data"]["items"][0]["unit_price_ars"] == "123.45"


def test_rounding_edit_replaces_lines_cancel_is_historical_and_immutable(client, db_session, tenant, monkeypatch):
    _setup_auth(monkeypatch); user = _user(db_session, tenant); product = _product(client, tenant)
    sale = _create(client, tenant, product["id"])
    update = client.patch(f"/api/v1/sales/{sale['id']}", headers=_headers(tenant), json={"notes": "Editada", "items": [{"line_type": "service", "description": "Corte", "quantity": "3", "unit_price_ars": "0.05", "discount_percentage": "10"}]})
    assert update.status_code == 200
    data = update.json()["data"]
    assert len(data["items"]) == 1 and data["items"][0]["line_subtotal_ars"] == "0.15"
    assert data["items"][0]["line_discount_ars"] == "0.02" and data["total_ars"] == "0.13"
    cancel = client.post(f"/api/v1/sales/{sale['id']}/cancel", headers=_auth_headers(user.email), json={"reason": "Carga duplicada"})
    assert cancel.status_code == 200 and cancel.json()["data"]["status"] == "cancelled"
    assert cancel.json()["data"]["cancelled_by_user_id"] == str(user.id)
    assert client.patch(f"/api/v1/sales/{sale['id']}", headers=_headers(tenant), json={"notes": "No"}).status_code == 409
    assert client.post(f"/api/v1/sales/{sale['id']}/cancel", headers=_headers(tenant), json={"reason": "Otra"}).status_code == 409
    assert db_session.scalar(select(func.count()).select_from(InventoryMovement)) == 0


def test_list_filters_pagination_stable_sort_detail_tenant_and_bounded_queries(client, db_session, tenant, other_tenant):
    owner = _owner(client, tenant); patient = _patient(client, tenant, owner["id"]); product = _product(client, tenant)
    first = _create(client, tenant, product["id"], owner_id=owner["id"], patient_id=patient["id"], sale_date="2026-08-08")
    second = _create(client, tenant, None, owner_id=owner["id"], patient_id=patient["id"], sale_date="2026-08-09")
    foreign = _create(client, other_tenant)
    queries = []
    event.listen(db_session.bind, "before_cursor_execute", lambda *args: queries.append(args[2]))
    response = client.get("/api/v1/sales", headers=_headers(tenant), params={"owner_id": owner["id"], "patient_id": patient["id"], "line_type": "service", "date_from": "2026-08-01", "date_to": "2026-08-31", "page": 1, "page_size": 1, "sort_by": "sale_date", "sort_direction": "desc"})
    assert response.status_code == 200 and response.json()["meta"]["total"] == 2
    assert response.json()["data"][0]["id"] == second["id"] and foreign["id"] not in response.text
    assert len(queries) <= 4
    assert client.get(f"/api/v1/sales/{first['id']}", headers=_headers(other_tenant)).status_code == 404
    search = client.get("/api/v1/sales", headers=_headers(tenant), params={"search": "Alimento"})
    assert [item["id"] for item in search.json()["data"]] == [first["id"]]


def test_confirm_mixed_sale_is_atomic_traceable_allows_inactive_and_closes_draft(
    client, db_session, tenant, monkeypatch
):
    _setup_auth(monkeypatch)
    user = _user(db_session, tenant)
    product = _product(client, tenant, price="123.45")
    _add_stock(client, tenant, product["id"], 5)
    sale = _create(client, tenant, product["id"])
    product_model = db_session.get(InventoryItem, uuid.UUID(product["id"]))
    product_model.is_active = False
    product_model.purchase_price_ars = Decimal("30.00")
    product_model.profit_margin_percentage = Decimal("40.00")
    db_session.commit()

    response = client.post(
        f"/api/v1/sales/{sale['id']}/confirm",
        headers=_auth_headers(user.email),
        json={"confirm": True},
    )

    assert response.status_code == 200, response.text
    confirmed = response.json()["data"]
    assert confirmed["status"] == "confirmed"
    assert confirmed["confirmed_at"] is not None
    assert confirmed["confirmed_by_user_id"] == str(user.id)
    assert confirmed["confirmed_by_user_name"] == "Vendedor"
    assert confirmed["inventory_operation_id"] is not None
    db_session.expire_all()
    product_model = db_session.get(InventoryItem, uuid.UUID(product["id"]))
    assert product_model.current_stock == Decimal("3.00")
    assert product_model.is_active is False
    assert product_model.sale_price_ars == Decimal("123.45")
    assert product_model.purchase_price_ars == Decimal("30.00")
    assert product_model.profit_margin_percentage == Decimal("40.00")

    movements = list(
        db_session.scalars(
            select(InventoryMovement).where(InventoryMovement.movement_type == "sale")
        ).all()
    )
    assert len(movements) == 1
    movement = movements[0]
    assert movement.operation_id == uuid.UUID(confirmed["inventory_operation_id"])
    assert movement.source_type == "sale" and movement.source_id == sale["id"]
    assert movement.quantity == Decimal("2.00")
    assert movement.stock_before == Decimal("5.00")
    assert movement.stock_after == Decimal("3.00")
    assert movement.unit_sale_price_ars == Decimal("100.00")
    assert movement.total_sale_price_ars == Decimal("180.00")
    assert movement.created_by_user_id == user.id

    assert client.patch(
        f"/api/v1/sales/{sale['id']}",
        headers=_headers(tenant),
        json={"notes": "No"},
    ).status_code == 409
    assert client.post(
        f"/api/v1/sales/{sale['id']}/cancel",
        headers=_headers(tenant),
        json={"reason": "No"},
    ).status_code == 409
    second = client.post(
        f"/api/v1/sales/{sale['id']}/confirm",
        headers=_headers(tenant),
        json={"confirm": True},
    )
    assert second.status_code == 409
    assert db_session.scalar(
        select(func.count()).select_from(InventoryMovement).where(
            InventoryMovement.movement_type == "sale"
        )
    ) == 1
    rows = client.get(
        "/api/v1/sales", headers=_headers(tenant), params={"status": "confirmed"}
    ).json()["data"]
    assert [row["id"] for row in rows] == [sale["id"]]


def test_confirm_rejects_payload_auth_states_tenant_and_rolls_back_insufficient_stock(
    client, db_session, tenant, other_tenant, monkeypatch
):
    first = _product(client, tenant, "Primero")
    second = _product(client, tenant, "Segundo")
    _add_stock(client, tenant, first["id"], 5)
    _add_stock(client, tenant, second["id"], 1)
    items = [
        {"line_type": "product", "inventory_item_id": first["id"], "quantity": "2", "unit_price_ars": "10", "discount_percentage": "0"},
        {"line_type": "product", "inventory_item_id": second["id"], "quantity": "2", "unit_price_ars": "20", "discount_percentage": "0"},
    ]
    sale = _create(client, tenant, items=items)

    assert client.post(
        f"/api/v1/sales/{sale['id']}/confirm",
        headers=_headers(other_tenant), json={"confirm": True}
    ).status_code == 404
    assert client.post(
        f"/api/v1/sales/{sale['id']}/confirm",
        headers=_headers(tenant), json={"confirm": False}
    ).status_code == 422
    assert client.post(
        f"/api/v1/sales/{sale['id']}/confirm",
        headers=_headers(tenant), json={"confirm": True, "stock": "999"}
    ).status_code == 422

    response = client.post(
        f"/api/v1/sales/{sale['id']}/confirm",
        headers=_headers(tenant), json={"confirm": True}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "sale_insufficient_stock"
    assert "Segundo" in response.json()["error"]["message"]
    assert "Disponible: 1.00" in response.json()["error"]["message"]
    db_session.expire_all()
    assert db_session.get(InventoryItem, uuid.UUID(first["id"])).current_stock == Decimal("5")
    assert db_session.get(InventoryItem, uuid.UUID(second["id"])).current_stock == Decimal("1")
    assert client.get(
        f"/api/v1/sales/{sale['id']}", headers=_headers(tenant)
    ).json()["data"]["status"] == "draft"
    assert db_session.scalar(
        select(func.count()).select_from(InventoryMovement).where(
            InventoryMovement.movement_type == "sale"
        )
    ) == 0

    cancelled = _create(client, tenant)
    client.post(
        f"/api/v1/sales/{cancelled['id']}/cancel",
        headers=_headers(tenant), json={"reason": "Cancelada"}
    )
    assert client.post(
        f"/api/v1/sales/{cancelled['id']}/confirm",
        headers=_headers(tenant), json={"confirm": True}
    ).status_code == 409

    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    assert client.post(
        f"/api/v1/sales/{sale['id']}/confirm", json={"confirm": True}
    ).status_code == 401


def test_confirm_rolls_back_all_products_when_movement_creation_fails(
    client, db_session, tenant, monkeypatch
):
    first = _product(client, tenant, "Primero")
    second = _product(client, tenant, "Segundo")
    _add_stock(client, tenant, first["id"], 3)
    _add_stock(client, tenant, second["id"], 3)
    sale = _create(client, tenant, items=[
        {"line_type": "product", "inventory_item_id": first["id"], "quantity": "2", "unit_price_ars": "10", "discount_percentage": "0"},
        {"line_type": "product", "inventory_item_id": second["id"], "quantity": "2", "unit_price_ars": "20", "discount_percentage": "0"},
    ])
    from app.services.inventory import InventoryService

    original = InventoryService.register_sale_movement
    calls = 0

    def fail_second(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated sale movement failure")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(InventoryService, "register_sale_movement", fail_second)
    with pytest.raises(RuntimeError, match="simulated sale movement failure"):
        client.post(
            f"/api/v1/sales/{sale['id']}/confirm",
            headers=_headers(tenant), json={"confirm": True}
        )

    db_session.expire_all()
    assert db_session.get(InventoryItem, uuid.UUID(first["id"])).current_stock == Decimal("3")
    assert db_session.get(InventoryItem, uuid.UUID(second["id"])).current_stock == Decimal("3")
    assert client.get(
        f"/api/v1/sales/{sale['id']}", headers=_headers(tenant)
    ).json()["data"]["status"] == "draft"
    assert db_session.scalar(
        select(func.count()).select_from(InventoryMovement).where(
            InventoryMovement.movement_type == "sale"
        )
    ) == 0


def test_service_only_sale_confirms_and_reverses_without_inventory_operations(
    client, db_session, tenant, monkeypatch
):
    _setup_auth(monkeypatch)
    user = _user(db_session, tenant)
    sale = _create(client, tenant)

    confirmed = client.post(
        f"/api/v1/sales/{sale['id']}/confirm",
        headers=_auth_headers(user.email), json={"confirm": True}
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["status"] == "confirmed"
    assert confirmed.json()["data"]["inventory_operation_id"] is None
    assert db_session.scalar(select(func.count()).select_from(InventoryMovement)) == 0

    reversed_response = client.post(
        f"/api/v1/sales/{sale['id']}/reverse",
        headers=_auth_headers(user.email), json={"reason": "Registro erróneo"}
    )
    assert reversed_response.status_code == 200
    reversed_sale = reversed_response.json()["data"]
    assert reversed_sale["status"] == "reversed"
    assert reversed_sale["reversed_at"] is not None
    assert reversed_sale["reversed_by_user_id"] == str(user.id)
    assert reversed_sale["reversal_reason"] == "Registro erróneo"
    assert reversed_sale["reversal_operation_id"] is None
    assert db_session.scalar(select(func.count()).select_from(InventoryMovement)) == 0


def test_reverse_sale_restores_stock_links_movements_and_rejects_invalid_reversals(
    client, db_session, tenant, other_tenant, monkeypatch
):
    _setup_auth(monkeypatch)
    user = _user(db_session, tenant)
    product = _product(client, tenant)
    _add_stock(client, tenant, product["id"], 2)
    sale = _create(client, tenant, product["id"])
    confirmed = client.post(
        f"/api/v1/sales/{sale['id']}/confirm",
        headers=_auth_headers(user.email), json={"confirm": True}
    ).json()["data"]
    original = db_session.scalar(
        select(InventoryMovement).where(InventoryMovement.movement_type == "sale")
    )

    generic = client.post(
        f"/api/v1/inventory/movements/{original.id}/reverse",
        headers=_headers(tenant), json={"reason": "other"}
    )
    assert generic.status_code == 409
    assert generic.json()["error"]["code"] == "sale_movement_requires_sale_reversal"
    assert client.post(
        f"/api/v1/sales/{sale['id']}/reverse",
        headers=_headers(other_tenant), json={"reason": "Ataque"}
    ).status_code == 404
    assert client.post(
        f"/api/v1/sales/{sale['id']}/reverse",
        headers=_headers(tenant), json={"reason": "   "}
    ).status_code == 422

    response = client.post(
        f"/api/v1/sales/{sale['id']}/reverse",
        headers=_auth_headers(user.email), json={"reason": "Venta duplicada"}
    )
    assert response.status_code == 200
    reversed_sale = response.json()["data"]
    assert reversed_sale["status"] == "reversed"
    assert reversed_sale["inventory_operation_id"] == confirmed["inventory_operation_id"]
    assert reversed_sale["reversal_operation_id"] is not None
    assert reversed_sale["reversal_operation_id"] != confirmed["inventory_operation_id"]
    assert reversed_sale["reversed_by_user_id"] == str(user.id)
    db_session.expire_all()
    assert db_session.get(InventoryItem, uuid.UUID(product["id"])).current_stock == Decimal("2")
    movements = list(
        db_session.scalars(
            select(InventoryMovement).where(
                InventoryMovement.movement_type.in_(["sale", "reversal"])
            )
        ).all()
    )
    assert len(movements) == 2
    original = next(item for item in movements if item.movement_type == "sale")
    reversal = next(item for item in movements if item.movement_type == "reversal")
    assert reversal.reverses_movement_id == original.id
    assert reversal.source_type == "sale_reversal"
    assert reversal.source_id == sale["id"]
    assert reversal.operation_id == uuid.UUID(reversed_sale["reversal_operation_id"])
    assert reversal.stock_before == Decimal("0")
    assert reversal.stock_after == Decimal("2")
    assert client.post(
        f"/api/v1/sales/{sale['id']}/reverse",
        headers=_headers(tenant), json={"reason": "Otra"}
    ).status_code == 409
    assert client.post(
        f"/api/v1/sales/{sale['id']}/confirm",
        headers=_headers(tenant), json={"confirm": True}
    ).status_code == 409
    rows = client.get(
        "/api/v1/sales", headers=_headers(tenant), params={"status": "reversed"}
    ).json()["data"]
    assert [row["id"] for row in rows] == [sale["id"]]

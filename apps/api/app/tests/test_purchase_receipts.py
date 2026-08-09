import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.purchase import Purchase, PurchaseItem
from app.models.user import User


def _headers(tenant) -> dict[str, str]:
    return {"X-Tenant-Id": str(tenant.id)}


def _auth_headers(email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {email}"}


def _setup_auth(monkeypatch) -> None:
    import app.core.tenant as tenant_core

    monkeypatch.setattr(tenant_core, "verify_id_token", lambda token: {"email": token})


def _create_user(db_session, tenant, email="receiver@example.com") -> User:
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=email,
        full_name="Responsable de compras",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_item(client, tenant, *, name="Producto", is_active=True):
    response = client.post(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        json={
            "name": name,
            "category": "supply",
            "unit": "box",
            "purchase_price_ars": "25.00",
            "purchase_tax_rate_percentage": "10.00",
            "profit_margin_percentage": "40.00",
            "sale_price_ars": "100.00",
            "is_active": is_active,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _create_supplier(client, tenant):
    suffix = uuid.uuid4().hex[:10]
    response = client.post(
        "/api/v1/suppliers",
        headers=_headers(tenant),
        json={"name": f"Proveedor Recepción {suffix}", "tax_id": None},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _create_purchase(client, tenant, items, *, headers=None):
    supplier = _create_supplier(client, tenant)
    response = client.post(
        "/api/v1/purchases",
        headers=headers or _headers(tenant),
        json={
            "supplier_id": supplier["id"],
            "purchase_date": "2026-08-09",
            "document_type": "invoice",
            "items": [
                {
                    "inventory_item_id": item["id"],
                    "quantity": quantity,
                    "unit_price_without_tax_ars": price,
                    "tax_rate_percentage": tax,
                }
                for item, quantity, price, tax in items
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _receive(client, tenant, purchase_id, *, headers=None, payload=None):
    return client.post(
        f"/api/v1/purchases/{purchase_id}/receive",
        headers=headers or _headers(tenant),
        json=payload if payload is not None else {"confirm": True},
    )


def test_receive_purchase_is_atomic_traceable_and_updates_stock_and_last_cost(
    client, db_session, tenant, monkeypatch
):
    _setup_auth(monkeypatch)
    user = _create_user(db_session, tenant)
    first = _create_item(client, tenant, name="Producto activo")
    second = _create_item(client, tenant, name="Producto inactivo", is_active=False)
    purchase = _create_purchase(
        client,
        tenant,
        [(first, "5", "50", "21"), (second, "3", "80", "0")],
        headers=_auth_headers(user.email),
    )

    response = _receive(
        client, tenant, purchase["id"], headers=_auth_headers(user.email)
    )

    assert response.status_code == 200
    received = response.json()["data"]
    assert received["status"] == "received"
    assert received["received_at"] is not None
    assert received["received_by_user_id"] == str(user.id)
    assert received["received_by_user_name"] == "Responsable de compras"
    assert received["inventory_operation_id"] is not None
    db_session.expire_all()
    first_model = db_session.get(InventoryItem, uuid.UUID(first["id"]))
    second_model = db_session.get(InventoryItem, uuid.UUID(second["id"]))
    assert first_model.current_stock == Decimal("5.00")
    assert second_model.current_stock == Decimal("3.00")
    assert first_model.purchase_price_ars == Decimal("50.00")
    assert first_model.purchase_tax_rate_percentage == Decimal("21.00")
    assert first_model.sale_price_ars == Decimal("100.00")
    assert first_model.profit_margin_percentage == Decimal("40.00")
    assert second_model.is_active is False

    movements = list(
        db_session.scalars(
            select(InventoryMovement).order_by(InventoryMovement.inventory_item_id)
        ).all()
    )
    assert len(movements) == 2
    assert {movement.movement_type for movement in movements} == {"purchase"}
    assert {movement.operation_id for movement in movements} == {
        uuid.UUID(received["inventory_operation_id"])
    }
    assert {movement.source_type for movement in movements} == {"purchase"}
    assert {movement.source_id for movement in movements} == {purchase["id"]}
    assert {movement.created_by_user_id for movement in movements} == {user.id}
    assert {(movement.stock_before, movement.stock_after) for movement in movements} == {
        (Decimal("0.00"), Decimal("5.00")),
        (Decimal("0.00"), Decimal("3.00")),
    }
    assert received["items"][0]["previous_purchase_price_ars"] == "25.00"
    assert received["items"][0]["previous_purchase_tax_rate_percentage"] == "10.00"


def test_receive_rejects_auth_payload_states_tenant_and_second_request(
    client, db_session, tenant, other_tenant, monkeypatch
):
    item = _create_item(client, tenant)
    draft = _create_purchase(client, tenant, [(item, "1", "10", "21")])
    cancelled = _create_purchase(
        client,
        tenant,
        [(_create_item(client, tenant, name="Cancelado"), "1", "10", "21")],
    )
    client.post(
        f"/api/v1/purchases/{cancelled['id']}/cancel",
        headers=_headers(tenant),
        json={"reason": "Cancelada"},
    )

    cross_tenant = _receive(client, other_tenant, draft["id"])
    cancelled_response = _receive(client, tenant, cancelled["id"])
    extra = _receive(
        client, tenant, draft["id"], payload={"confirm": True, "quantity": "999"}
    )
    false_confirm = _receive(client, tenant, draft["id"], payload={"confirm": False})
    first = _receive(client, tenant, draft["id"])
    second = _receive(client, tenant, draft["id"])
    edit = client.patch(
        f"/api/v1/purchases/{draft['id']}",
        headers=_headers(tenant),
        json={"notes": "No permitido"},
    )
    cancel_received = client.post(
        f"/api/v1/purchases/{draft['id']}/cancel",
        headers=_headers(tenant),
        json={"reason": "No permitido"},
    )

    assert cross_tenant.status_code == 404
    assert cancelled_response.status_code == 409
    assert extra.status_code == 422
    assert false_confirm.status_code == 422
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "purchase_not_receivable"
    assert edit.status_code == 409
    assert cancel_received.status_code == 409
    db_session.expire_all()
    assert db_session.get(InventoryItem, uuid.UUID(item["id"])).current_stock == Decimal("1")
    assert db_session.scalar(select(func.count()).select_from(InventoryMovement)) == 1

    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    unauthenticated = client.post(
        f"/api/v1/purchases/{draft['id']}/receive", json={"confirm": True}
    )
    assert unauthenticated.status_code == 401


def test_receive_rolls_back_every_line_when_movement_creation_fails(
    client, db_session, tenant, monkeypatch
):
    first = _create_item(client, tenant, name="Primero")
    second = _create_item(client, tenant, name="Segundo")
    purchase = _create_purchase(
        client,
        tenant,
        [(first, "2", "10", "21"), (second, "3", "20", "21")],
    )
    from app.services.inventory import InventoryService

    original = InventoryService.register_purchase_movement
    calls = 0

    def fail_second(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated movement failure")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(InventoryService, "register_purchase_movement", fail_second)
    with pytest.raises(RuntimeError, match="simulated movement failure"):
        _receive(client, tenant, purchase["id"])

    db_session.expire_all()
    assert db_session.get(Purchase, uuid.UUID(purchase["id"])).status == "draft"
    assert db_session.get(InventoryItem, uuid.UUID(first["id"])).current_stock == Decimal("0")
    assert db_session.get(InventoryItem, uuid.UUID(second["id"])).current_stock == Decimal("0")
    assert db_session.scalar(select(func.count()).select_from(InventoryMovement)) == 0


def test_receive_rejects_legacy_fractional_quantity_before_creating_movements(
    client, db_session, tenant, monkeypatch
):
    item = _create_item(client, tenant)
    purchase = _create_purchase(client, tenant, [(item, "2", "10", "21")])
    purchase_model = db_session.get(Purchase, uuid.UUID(purchase["id"]))
    purchase_model.items[0].quantity = Decimal("1.5")

    from app.repositories.purchase import PurchaseRepository

    monkeypatch.setattr(
        PurchaseRepository,
        "get_by_id",
        lambda self, tenant_id, purchase_id, for_update=False: purchase_model,
    )

    response = _receive(client, tenant, purchase["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "purchase_quantity_must_be_integer"
    db_session.expire_all()
    assert db_session.get(Purchase, uuid.UUID(purchase["id"])).status == "draft"
    assert db_session.get(InventoryItem, uuid.UUID(item["id"])).current_stock == Decimal("0")
    assert db_session.scalar(select(func.count()).select_from(InventoryMovement)) == 0


def test_reverse_receipt_is_atomic_keeps_originals_and_restores_safe_cost(
    client, db_session, tenant, monkeypatch
):
    _setup_auth(monkeypatch)
    user = _create_user(db_session, tenant)
    item = _create_item(client, tenant)
    purchase = _create_purchase(
        client,
        tenant,
        [(item, "4", "50", "21")],
        headers=_auth_headers(user.email),
    )
    received = _receive(
        client, tenant, purchase["id"], headers=_auth_headers(user.email)
    ).json()["data"]

    response = client.post(
        f"/api/v1/purchases/{purchase['id']}/reverse-receipt",
        headers=_auth_headers(user.email),
        json={"reason": "Recepción duplicada"},
    )

    assert response.status_code == 200
    reversed_purchase = response.json()["data"]
    assert reversed_purchase["status"] == "reversed"
    assert reversed_purchase["reversed_at"] is not None
    assert reversed_purchase["reversed_by_user_id"] == str(user.id)
    assert reversed_purchase["reversal_reason"] == "Recepción duplicada"
    assert reversed_purchase["reversal_operation_id"] is not None
    assert reversed_purchase["reversal_operation_id"] != received["inventory_operation_id"]
    assert reversed_purchase["reversal_warnings"] == []
    db_session.expire_all()
    item_model = db_session.get(InventoryItem, uuid.UUID(item["id"]))
    assert item_model.current_stock == Decimal("0")
    assert item_model.purchase_price_ars == Decimal("25.00")
    assert item_model.purchase_tax_rate_percentage == Decimal("10.00")
    assert item_model.sale_price_ars == Decimal("100.00")
    movements = list(db_session.scalars(select(InventoryMovement)).all())
    assert len(movements) == 2
    original = next(movement for movement in movements if movement.movement_type == "purchase")
    reversal = next(movement for movement in movements if movement.movement_type == "reversal")
    assert reversal.reverses_movement_id == original.id
    assert reversal.operation_id == uuid.UUID(reversed_purchase["reversal_operation_id"])
    assert reversal.source_type == "purchase_reversal"
    assert reversal.stock_before == Decimal("4")
    assert reversal.stock_after == Decimal("0")


def test_reverse_rejects_wrong_states_reason_tenant_and_second_request(
    client, tenant, other_tenant
):
    draft = _create_purchase(
        client, tenant, [(_create_item(client, tenant), "1", "10", "21")]
    )
    cancelled = _create_purchase(
        client,
        tenant,
        [(_create_item(client, tenant, name="Cancelado"), "1", "10", "21")],
    )
    client.post(
        f"/api/v1/purchases/{cancelled['id']}/cancel",
        headers=_headers(tenant),
        json={"reason": "Cancelada"},
    )
    received = _create_purchase(
        client,
        tenant,
        [(_create_item(client, tenant, name="Recibido"), "1", "10", "21")],
    )
    _receive(client, tenant, received["id"])

    assert client.post(
        f"/api/v1/purchases/{draft['id']}/reverse-receipt",
        headers=_headers(tenant), json={"reason": "No"}
    ).status_code == 409
    assert client.post(
        f"/api/v1/purchases/{cancelled['id']}/reverse-receipt",
        headers=_headers(tenant), json={"reason": "No"}
    ).status_code == 409
    assert client.post(
        f"/api/v1/purchases/{received['id']}/reverse-receipt",
        headers=_headers(other_tenant), json={"reason": "Ataque"}
    ).status_code == 404
    assert client.post(
        f"/api/v1/purchases/{received['id']}/reverse-receipt",
        headers=_headers(tenant), json={"reason": "   "}
    ).status_code == 422
    first = client.post(
        f"/api/v1/purchases/{received['id']}/reverse-receipt",
        headers=_headers(tenant), json={"reason": "Correcta"}
    )
    second = client.post(
        f"/api/v1/purchases/{received['id']}/reverse-receipt",
        headers=_headers(tenant), json={"reason": "Otra"}
    )
    assert first.status_code == 200
    assert second.status_code == 409


def test_reverse_fails_whole_operation_when_any_product_has_insufficient_stock(
    client, db_session, tenant
):
    first = _create_item(client, tenant, name="Primero")
    second = _create_item(client, tenant, name="Segundo")
    purchase = _create_purchase(
        client,
        tenant,
        [(first, "5", "10", "21"), (second, "5", "20", "21")],
    )
    received = _receive(client, tenant, purchase["id"]).json()["data"]
    exit_response = client.post(
        f"/api/v1/inventory/items/{first['id']}/movements/exit",
        headers=_headers(tenant),
        json={"quantity": "4", "reason": "other"},
    )
    assert exit_response.status_code == 201
    before = {
        first["id"]: Decimal("1"),
        second["id"]: Decimal("5"),
    }

    response = client.post(
        f"/api/v1/purchases/{purchase['id']}/reverse-receipt",
        headers=_headers(tenant),
        json={"reason": "No debe aplicar parcialmente"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_stock_for_reversal"
    db_session.expire_all()
    for item_id, expected in before.items():
        assert db_session.get(InventoryItem, uuid.UUID(item_id)).current_stock == expected
    assert db_session.get(Purchase, uuid.UUID(purchase["id"])).status == "received"
    assert db_session.scalar(
        select(func.count()).select_from(InventoryMovement).where(
            InventoryMovement.operation_id == uuid.UUID(received["inventory_operation_id"])
        )
    ) == 2
    assert db_session.scalar(
        select(func.count()).select_from(InventoryMovement).where(
            InventoryMovement.movement_type == "reversal"
        )
    ) == 0


def test_reverse_preserves_later_cost_and_serializes_warning(client, db_session, tenant):
    item = _create_item(client, tenant)
    purchase = _create_purchase(client, tenant, [(item, "2", "50", "21")])
    _receive(client, tenant, purchase["id"])
    item_model = db_session.get(InventoryItem, uuid.UUID(item["id"]))
    item_model.purchase_price_ars = Decimal("999.00")
    item_model.purchase_tax_rate_percentage = Decimal("5.00")
    db_session.commit()

    response = client.post(
        f"/api/v1/purchases/{purchase['id']}/reverse-receipt",
        headers=_headers(tenant),
        json={"reason": "Con costo posterior"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["reversal_warnings"]
    db_session.expire_all()
    item_model = db_session.get(InventoryItem, uuid.UUID(item["id"]))
    assert item_model.current_stock == Decimal("0")
    assert item_model.purchase_price_ars == Decimal("999.00")
    assert item_model.purchase_tax_rate_percentage == Decimal("5.00")


def test_purchase_movements_require_purchase_level_reversal(client, tenant):
    item = _create_item(client, tenant)
    purchase = _create_purchase(client, tenant, [(item, "1", "10", "21")])
    received = _receive(client, tenant, purchase["id"]).json()["data"]
    movements = client.get(
        "/api/v1/inventory/movements",
        headers=_headers(tenant),
        params={"operation_id": received["inventory_operation_id"]},
    ).json()["data"]
    detail = client.get(
        f"/api/v1/inventory/movements/{movements[0]['id']}", headers=_headers(tenant)
    )
    generic_reverse = client.post(
        f"/api/v1/inventory/movements/{movements[0]['id']}/reverse",
        headers=_headers(tenant),
        json={"reason": "other"},
    )

    assert detail.json()["data"]["can_be_reversed"] is False
    assert detail.json()["data"]["reversal_block_reason"] == (
        "purchase_movement_requires_purchase_reversal"
    )
    assert generic_reverse.status_code == 409
    assert generic_reverse.json()["error"]["code"] == (
        "purchase_movement_requires_purchase_reversal"
    )


def test_reverse_rejects_missing_or_inconsistent_receipt_movements(
    client, db_session, tenant
):
    item = _create_item(client, tenant)
    purchase = _create_purchase(client, tenant, [(item, "2", "10", "21")])
    received = _receive(client, tenant, purchase["id"]).json()["data"]
    movement = db_session.scalar(
        select(InventoryMovement).where(
            InventoryMovement.operation_id == uuid.UUID(
                received["inventory_operation_id"]
            )
        )
    )
    movement.operation_id = uuid.uuid4()
    db_session.commit()

    response = client.post(
        f"/api/v1/purchases/{purchase['id']}/reverse-receipt",
        headers=_headers(tenant),
        json={"reason": "Operación inconsistente"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == (
        "purchase_receipt_movements_inconsistent"
    )
    db_session.expire_all()
    assert db_session.get(Purchase, uuid.UUID(purchase["id"])).status == "received"
    assert db_session.get(InventoryItem, uuid.UUID(item["id"])).current_stock == Decimal("2")


def test_purchase_list_filters_received_and_reversed(client, tenant):
    received = _create_purchase(
        client, tenant, [(_create_item(client, tenant, name="Recibida"), "1", "10", "21")]
    )
    reversed_purchase = _create_purchase(
        client, tenant, [(_create_item(client, tenant, name="Revertida"), "1", "10", "21")]
    )
    _receive(client, tenant, received["id"])
    _receive(client, tenant, reversed_purchase["id"])
    client.post(
        f"/api/v1/purchases/{reversed_purchase['id']}/reverse-receipt",
        headers=_headers(tenant),
        json={"reason": "Prueba"},
    )

    received_rows = client.get(
        "/api/v1/purchases", headers=_headers(tenant), params={"status": "received"}
    ).json()["data"]
    reversed_rows = client.get(
        "/api/v1/purchases", headers=_headers(tenant), params={"status": "reversed"}
    ).json()["data"]

    assert [row["id"] for row in received_rows] == [received["id"]]
    assert [row["id"] for row in reversed_rows] == [reversed_purchase["id"]]

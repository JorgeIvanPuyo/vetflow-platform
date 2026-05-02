import uuid
from datetime import UTC, date, datetime, timedelta
from time import sleep

from app.models.consultation import Consultation
from app.models.user import User


def _headers(tenant) -> dict[str, str]:
    return {"X-Tenant-Id": str(tenant.id)}


def _auth_headers(email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {email}"}


def _setup_auth(monkeypatch) -> None:
    import app.core.tenant as tenant_core

    monkeypatch.setattr(
        tenant_core,
        "verify_id_token",
        lambda token: {"email": token},
    )


def _create_user(db_session, tenant, email: str, full_name: str) -> User:
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


def _create_owner(client, tenant, full_name: str = "Inventory Owner") -> dict:
    response = client.post(
        "/api/v1/owners",
        headers=_headers(tenant),
        json={"full_name": full_name, "phone": "555-1000"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_patient(client, tenant, owner_id: str, name: str = "Luna") -> dict:
    response = client.post(
        "/api/v1/patients",
        headers=_headers(tenant),
        json={"owner_id": owner_id, "name": name, "species": "Canine"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_consultation(db_session, tenant, patient_id: str) -> Consultation:
    consultation = Consultation(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        patient_id=uuid.UUID(patient_id),
        visit_date=datetime.now(UTC),
        reason="Uso de inventario",
        status="completed",
    )
    db_session.add(consultation)
    db_session.commit()
    db_session.refresh(consultation)
    return consultation


def _item_payload(**overrides) -> dict:
    payload = {
        "name": "Amoxicilina 50mg",
        "category": "medication",
        "unit": "tablet",
        "current_stock": "10",
        "minimum_stock": "3",
        "purchase_price_ars": "1000",
        "profit_margin_percentage": "35",
        "round_sale_price": False,
        "notes": "Uso general",
    }
    payload.update(overrides)
    return payload


def _create_item(client, tenant, **overrides) -> dict:
    response = client.post(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        json=_item_payload(**overrides),
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_create_inventory_item(client, tenant):
    response = client.post(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        json=_item_payload(),
    )

    assert response.status_code == 201
    item = response.json()["data"]
    assert item["tenant_id"] == str(tenant.id)
    assert item["name"] == "Amoxicilina 50mg"
    assert item["sale_price_ars"] == "1350.00"
    assert item["is_low_stock"] is False
    assert item["created_at"] is not None
    assert item["updated_at"] is not None


def test_list_inventory_items_paginated(client, tenant):
    _create_item(client, tenant, name="Item A")
    _create_item(client, tenant, name="Item B")
    _create_item(client, tenant, name="Item C")

    response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"page": 1, "page_size": 2, "sort_by": "name", "sort_order": "asc"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["name"] for item in payload["data"]] == ["Item A", "Item B"]
    assert payload["meta"] == {"page": 1, "page_size": 2, "total": 3, "total_pages": 2}


def test_search_inventory_items_by_q(client, tenant):
    _create_item(client, tenant, name="Amoxicilina 50mg")
    _create_item(client, tenant, name="Jeringa 5ml", category="supply", unit="syringe")

    response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"q": "amoxi"},
    )

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["data"]] == ["Amoxicilina 50mg"]


def test_filter_low_stock(client, tenant):
    _create_item(client, tenant, name="Bajo stock", current_stock="2", minimum_stock="3")
    _create_item(client, tenant, name="Stock sano", current_stock="8", minimum_stock="3")

    response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"status": "low_stock"},
    )

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["data"]] == ["Bajo stock"]


def test_filter_expiring_soon(client, tenant):
    soon_date = (date.today() + timedelta(days=10)).isoformat()
    far_date = (date.today() + timedelta(days=60)).isoformat()
    _create_item(client, tenant, name="Vence pronto", expiration_date=soon_date)
    _create_item(client, tenant, name="Vence lejos", expiration_date=far_date)

    response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"status": "expiring_soon"},
    )

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["data"]] == ["Vence pronto"]


def test_filter_expired(client, tenant):
    expired_date = (date.today() - timedelta(days=5)).isoformat()
    future_date = (date.today() + timedelta(days=20)).isoformat()
    _create_item(client, tenant, name="Vencido", expiration_date=expired_date)
    _create_item(client, tenant, name="Vigente", expiration_date=future_date)

    response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"status": "expired"},
    )

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["data"]] == ["Vencido"]


def test_inventory_summary_counts(client, tenant):
    _create_item(client, tenant, name="Bajo stock", current_stock="1", minimum_stock="3")
    _create_item(
        client,
        tenant,
        name="Vence pronto",
        expiration_date=(date.today() + timedelta(days=12)).isoformat(),
    )
    _create_item(
        client,
        tenant,
        name="Vencido",
        expiration_date=(date.today() - timedelta(days=7)).isoformat(),
    )

    response = client.get("/api/v1/inventory/summary", headers=_headers(tenant))

    assert response.status_code == 200
    assert response.json()["data"] == {
        "total_items": 3,
        "low_stock_count": 1,
        "expiring_soon_count": 1,
        "expired_count": 1,
    }


def test_get_item_detail(client, tenant):
    item = _create_item(client, tenant)

    response = client.get(f"/api/v1/inventory/items/{item['id']}", headers=_headers(tenant))

    assert response.status_code == 200
    assert response.json()["data"]["id"] == item["id"]


def test_update_item_and_recalculate_sale_price(client, tenant):
    item = _create_item(client, tenant)
    original_updated_at = item["updated_at"]

    sleep(1)

    response = client.patch(
        f"/api/v1/inventory/items/{item['id']}",
        headers=_headers(tenant),
        json={"purchase_price_ars": "2000", "profit_margin_percentage": "50"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["purchase_price_ars"] == "2000.00"
    assert data["sale_price_ars"] == "3000.00"
    assert data["updated_at"] >= original_updated_at
    assert data["updated_at"] != original_updated_at


def test_round_sale_price_to_nearest_10(client, tenant):
    response = client.post(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        json=_item_payload(purchase_price_ars="1013", profit_margin_percentage="35", round_sale_price=True),
    )

    assert response.status_code == 201
    assert response.json()["data"]["sale_price_ars"] == "1370.00"


def test_soft_delete_item(client, tenant):
    item = _create_item(client, tenant)

    delete_response = client.delete(
        f"/api/v1/inventory/items/{item['id']}",
        headers=_headers(tenant),
    )
    assert delete_response.status_code == 204

    list_response = client.get("/api/v1/inventory/items", headers=_headers(tenant))
    assert list_response.status_code == 200
    assert list_response.json()["data"] == []

    inactive_response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"status": "inactive"},
    )
    assert inactive_response.status_code == 200
    assert inactive_response.json()["data"][0]["is_active"] is False


def test_register_entry_movement_increases_stock(client, tenant):
    item = _create_item(client, tenant, current_stock="10")

    response = client.post(
        f"/api/v1/inventory/items/{item['id']}/movements/entry",
        headers=_headers(tenant),
        json={"quantity": "5", "total_cost_ars": "5000", "supplier": "Proveedor Uno"},
    )

    assert response.status_code == 201
    movement = response.json()["data"]
    assert movement["movement_type"] == "entry"
    assert movement["unit_cost_ars"] == "1000.00"
    assert movement["created_at"] is not None

    item_response = client.get(f"/api/v1/inventory/items/{item['id']}", headers=_headers(tenant))
    assert item_response.json()["data"]["current_stock"] == "15.00"


def test_register_exit_movement_decreases_stock(client, db_session, tenant):
    item = _create_item(client, tenant, current_stock="10", sale_price_ars="2000")
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])
    consultation = _create_consultation(db_session, tenant, patient["id"])

    response = client.post(
        f"/api/v1/inventory/items/{item['id']}/movements/exit",
        headers=_headers(tenant),
        json={
            "quantity": "4",
            "reason": "consultation_use",
            "related_patient_id": patient["id"],
            "related_consultation_id": str(consultation.id),
        },
    )

    assert response.status_code == 201
    movement = response.json()["data"]
    assert movement["movement_type"] == "exit"
    assert movement["total_sale_price_ars"] == "8000.00"

    item_response = client.get(f"/api/v1/inventory/items/{item['id']}", headers=_headers(tenant))
    assert item_response.json()["data"]["current_stock"] == "6.00"


def test_reject_exit_when_insufficient_stock(client, tenant):
    item = _create_item(client, tenant, current_stock="2")

    response = client.post(
        f"/api/v1/inventory/items/{item['id']}/movements/exit",
        headers=_headers(tenant),
        json={"quantity": "5", "reason": "sale"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_stock"


def test_list_item_movements_paginated(client, tenant):
    item = _create_item(client, tenant)
    client.post(
        f"/api/v1/inventory/items/{item['id']}/movements/entry",
        headers=_headers(tenant),
        json={"quantity": "2"},
    )
    client.post(
        f"/api/v1/inventory/items/{item['id']}/movements/exit",
        headers=_headers(tenant),
        json={"quantity": "1", "reason": "sale"},
    )

    response = client.get(
        f"/api/v1/inventory/items/{item['id']}/movements",
        headers=_headers(tenant),
        params={"page": 1, "page_size": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["data"]) == 1
    assert payload["meta"] == {"page": 1, "page_size": 1, "total": 2, "total_pages": 2}


def test_prevent_cross_tenant_item_read_update_delete(client, tenant, other_tenant):
    item = _create_item(client, other_tenant)

    get_response = client.get(f"/api/v1/inventory/items/{item['id']}", headers=_headers(tenant))
    patch_response = client.patch(
        f"/api/v1/inventory/items/{item['id']}",
        headers=_headers(tenant),
        json={"name": "Cambio ilegal"},
    )
    delete_response = client.delete(
        f"/api/v1/inventory/items/{item['id']}",
        headers=_headers(tenant),
    )

    assert get_response.status_code == 404
    assert patch_response.status_code == 404
    assert delete_response.status_code == 404


def test_prevent_cross_tenant_movement_creation(client, tenant, other_tenant):
    item = _create_item(client, other_tenant)

    response = client.post(
        f"/api/v1/inventory/items/{item['id']}/movements/entry",
        headers=_headers(tenant),
        json={"quantity": "3"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "inventory_item_not_found"


def test_prevent_cross_tenant_related_patient_in_exit_movement(
    client,
    tenant,
    other_tenant,
):
    item = _create_item(client, tenant)
    foreign_owner = _create_owner(client, other_tenant, "Foreign Owner")
    foreign_patient = _create_patient(client, other_tenant, foreign_owner["id"], "Nina")

    response = client.post(
        f"/api/v1/inventory/items/{item['id']}/movements/exit",
        headers=_headers(tenant),
        json={
            "quantity": "1",
            "reason": "consultation_use",
            "related_patient_id": foreign_patient["id"],
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_cross_tenant_access"


def test_response_includes_computed_flags(client, tenant):
    response = client.post(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        json=_item_payload(
            current_stock="1",
            minimum_stock="3",
            expiration_date=(date.today() + timedelta(days=14)).isoformat(),
        ),
    )

    assert response.status_code == 201
    item = response.json()["data"]
    assert item["is_low_stock"] is True
    assert item["is_expiring_soon"] is True
    assert item["is_expired"] is False


def test_response_includes_created_by_display_fields_when_available(
    client,
    db_session,
    tenant,
    monkeypatch,
):
    _setup_auth(monkeypatch)
    user = _create_user(db_session, tenant, "inventory@example.com", "Inventory Vet")

    response = client.post(
        "/api/v1/inventory/items",
        headers=_auth_headers(user.email),
        json=_item_payload(),
    )

    assert response.status_code == 201
    item = response.json()["data"]
    assert item["created_by_user_id"] == str(user.id)
    assert item["created_by_user_name"] == "Inventory Vet"
    assert item["created_by_user_email"] == "inventory@example.com"

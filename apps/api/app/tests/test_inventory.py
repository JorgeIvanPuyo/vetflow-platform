import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from time import sleep

import pytest

from app.models.consultation import Consultation
from app.models.inventory_item import InventoryItem
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
        "minimum_stock": "3",
        "purchase_price_ars": "1000",
        "profit_margin_percentage": "35",
        "round_sale_price": False,
        "notes": "Uso general",
    }
    payload.update(overrides)
    return payload


def _create_item(client, tenant, **overrides) -> dict:
    initial_stock = overrides.pop("current_stock", None)
    response = client.post(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        json=_item_payload(**overrides),
    )
    assert response.status_code == 201
    item = response.json()["data"]
    if initial_stock is None or Decimal(str(initial_stock)) == Decimal("0"):
        return item

    movement_response = client.post(
        f"/api/v1/inventory/items/{item['id']}/movements/entry",
        headers=_headers(tenant),
        json={"quantity": str(initial_stock)},
    )
    assert movement_response.status_code == 201

    item_response = client.get(
        f"/api/v1/inventory/items/{item['id']}",
        headers=_headers(tenant),
    )
    assert item_response.status_code == 200
    return item_response.json()["data"]


def _set_item_stock(db_session, item_id: str, current_stock: str) -> None:
    item = db_session.get(InventoryItem, uuid.UUID(item_id))
    assert item is not None
    item.current_stock = Decimal(current_stock)
    db_session.add(item)
    db_session.commit()


def _create_raw_item(db_session, tenant, **overrides) -> InventoryItem:
    item = InventoryItem(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        internal_code=overrides.pop("internal_code", f"RAW-{uuid.uuid4().hex[:8]}"),
        name=overrides.pop("name", "Item histórico"),
        category=overrides.pop("category", "medication"),
        unit=overrides.pop("unit", "unit"),
        **overrides,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


def test_create_inventory_item(client, tenant):
    response = client.post(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        json=_item_payload(),
    )

    assert response.status_code == 201
    item = response.json()["data"]
    assert item["tenant_id"] == str(tenant.id)
    assert item["internal_code"] == "MED-00001"
    assert item["name"] == "Amoxicilina 50mg"
    assert item["brand"] is None
    assert item["current_stock"] == "0.00"
    assert item["purchase_tax_rate_percentage"] == "21.00"
    assert item["sale_tax_rate_percentage"] == "0.00"
    assert item["purchase_tax_amount_ars"] == "210.00"
    assert item["purchase_price_with_tax_ars"] == "1210.00"
    assert item["sale_price_ars"] == "1633.50"
    assert item["sale_tax_amount_ars"] == "0.00"
    assert item["sale_price_with_tax_ars"] == "1633.50"
    assert item["is_low_stock"] is True
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
    assert {
        "purchase_tax_rate_percentage",
        "sale_tax_rate_percentage",
        "purchase_tax_amount_ars",
        "purchase_price_with_tax_ars",
        "sale_tax_amount_ars",
        "sale_price_with_tax_ars",
    } <= payload["data"][0].keys()
    assert payload["meta"] == {"page": 1, "page_size": 2, "total": 3, "total_pages": 2}


def test_inventory_internal_codes_are_sequential_by_tenant_and_category(
    client,
    tenant,
    other_tenant,
):
    first_medication = _create_item(client, tenant, name="Medicamento A")
    second_medication = _create_item(client, tenant, name="Medicamento B")
    supply = _create_item(client, tenant, name="Insumo A", category="supply", unit="syringe")
    other_tenant_medication = _create_item(client, other_tenant, name="Medicamento C")

    assert first_medication["internal_code"] == "MED-00001"
    assert second_medication["internal_code"] == "MED-00002"
    assert supply["internal_code"] == "INS-00001"
    assert other_tenant_medication["internal_code"] == "MED-00001"


def test_update_category_does_not_change_internal_code(client, tenant):
    item = _create_item(client, tenant)

    response = client.patch(
        f"/api/v1/inventory/items/{item['id']}",
        headers=_headers(tenant),
        json={"category": "food"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["category"] == "food"
    assert data["internal_code"] == item["internal_code"]


def test_reject_internal_code_patch(client, tenant):
    item = _create_item(client, tenant)

    response = client.patch(
        f"/api/v1/inventory/items/{item['id']}",
        headers=_headers(tenant),
        json={"internal_code": "MED-99999"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_brand_is_normalized_saved_and_returned(client, tenant):
    item = _create_item(client, tenant, brand="  Laboratorio Norte  ")

    assert item["brand"] == "Laboratorio Norte"

    response = client.patch(
        f"/api/v1/inventory/items/{item['id']}",
        headers=_headers(tenant),
        json={"brand": "   "},
    )

    assert response.status_code == 200
    assert response.json()["data"]["brand"] is None


def test_accessory_is_valid_category(client, tenant):
    item = _create_item(client, tenant, category="accessory", name="Collar", unit="unit")

    assert item["category"] == "accessory"
    assert item["internal_code"] == "ACC-00001"


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


def test_search_inventory_items_by_name_and_code(client, tenant):
    amoxi = _create_item(client, tenant, name="Amoxicilina Forte")
    _create_item(client, tenant, name="Jeringa 5ml")

    name_response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"search": "moxi"},
    )
    case_response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"search": "AMOXI"},
    )
    code_response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"search": amoxi["internal_code"].lower()},
    )
    fragment_response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"search": amoxi["internal_code"][-5:]},
    )

    assert name_response.status_code == 200
    assert case_response.status_code == 200
    assert code_response.status_code == 200
    assert fragment_response.status_code == 200
    assert [item["name"] for item in name_response.json()["data"]] == ["Amoxicilina Forte"]
    assert [item["name"] for item in case_response.json()["data"]] == ["Amoxicilina Forte"]
    assert [item["name"] for item in code_response.json()["data"]] == ["Amoxicilina Forte"]
    assert [item["name"] for item in fragment_response.json()["data"]] == [
        "Amoxicilina Forte"
    ]


def test_search_does_not_match_supplier_or_subcategory(client, tenant):
    _create_item(client, tenant, name="Antiparasitario", supplier="Distrivet")
    _create_item(client, tenant, name="Collar azul", category="accessory", subcategory="Distrivet")

    response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"search": "distrivet"},
    )

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_filter_inventory_items_by_category_brand_supplier_and_active_state(client, tenant):
    _create_item(
        client,
        tenant,
        name="Alimento adulto",
        category="food",
        brand="Purina",
        supplier="Distribuidora Norte",
    )
    _create_item(
        client,
        tenant,
        name="Alimento cachorro",
        category="food",
        brand="Otra marca",
        supplier="Distribuidora Norte",
    )
    _create_item(
        client,
        tenant,
        name="Vacuna triple",
        category="vaccine",
        brand="Purina",
        supplier="Distribuidora Sur",
    )
    _create_item(client, tenant, name="Producto inactivo", is_active=False)

    response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={
            "category": "food",
            "brand": "purina",
            "supplier": "distribuidora norte",
        },
    )
    inactive_response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"is_active": False},
    )

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["data"]] == ["Alimento adulto"]
    assert inactive_response.status_code == 200
    assert [item["name"] for item in inactive_response.json()["data"]] == ["Producto inactivo"]


def test_inventory_filter_options_are_distinct_active_and_tenant_scoped(
    client,
    tenant,
    other_tenant,
):
    _create_item(client, tenant, name="A", brand="VetLab", supplier="Proveedor Uno")
    _create_item(client, tenant, name="B", brand="VetLab", supplier="Proveedor Uno")
    _create_item(client, tenant, name="C", brand="Zeta", supplier="Proveedor Dos")
    _create_item(client, tenant, name="D", brand="   ", supplier="   ")
    _create_item(client, tenant, name="E", brand="Inactiva", supplier="Inactivo SA", is_active=False)
    _create_item(client, other_tenant, name="F", brand="Ajena", supplier="Ajeno SA")

    response = client.get("/api/v1/inventory/filter-options", headers=_headers(tenant))

    assert response.status_code == 200
    assert response.json()["data"] == {
        "brands": ["VetLab", "Zeta"],
        "suppliers": ["Proveedor Dos", "Proveedor Uno"],
    }


def test_inventory_filter_options_trim_and_dedupe_historical_text_values(
    client,
    db_session,
    tenant,
):
    _create_raw_item(
        db_session,
        tenant,
        name="Histórico A",
        brand="  VetLab  ",
        supplier="  Proveedor Uno  ",
    )
    _create_raw_item(
        db_session,
        tenant,
        name="Histórico B",
        brand="vetlab",
        supplier="proveedor uno",
    )
    _create_raw_item(
        db_session,
        tenant,
        name="Histórico C",
        brand=None,
        supplier=None,
    )
    _create_raw_item(
        db_session,
        tenant,
        name="Histórico D",
        brand="   ",
        supplier="   ",
    )

    response = client.get("/api/v1/inventory/filter-options", headers=_headers(tenant))

    assert response.status_code == 200
    options = response.json()["data"]
    assert len(options["brands"]) == 1
    assert len(options["suppliers"]) == 1
    assert options["brands"][0] == options["brands"][0].strip()
    assert options["suppliers"][0] == options["suppliers"][0].strip()
    assert options["brands"][0].lower() == "vetlab"
    assert options["suppliers"][0].lower() == "proveedor uno"


def test_filter_by_returned_brand_and_supplier_options_matches_trimmed_values(
    client,
    db_session,
    tenant,
):
    raw_item = _create_raw_item(
        db_session,
        tenant,
        name="Producto histórico",
        brand="  VetLab  ",
        supplier="  Proveedor Uno  ",
    )

    options_response = client.get("/api/v1/inventory/filter-options", headers=_headers(tenant))
    options = options_response.json()["data"]
    list_by_brand = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"brand": options["brands"][0]},
    )
    list_by_supplier = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"supplier": options["suppliers"][0]},
    )

    assert options_response.status_code == 200
    assert list_by_brand.status_code == 200
    assert list_by_supplier.status_code == 200
    assert [item["id"] for item in list_by_brand.json()["data"]] == [str(raw_item.id)]
    assert [item["id"] for item in list_by_supplier.json()["data"]] == [str(raw_item.id)]


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


def test_filter_stock_statuses_are_mutually_exclusive(client, db_session, tenant):
    _create_item(client, tenant, name="Disponible", current_stock="6", minimum_stock="3")
    _create_item(client, tenant, name="Igual al mínimo", current_stock="3", minimum_stock="3")
    _create_item(client, tenant, name="Bajo stock", current_stock="1", minimum_stock="3")
    _create_item(client, tenant, name="Agotado", current_stock="0", minimum_stock="3")
    negative = _create_item(client, tenant, name="Negativo", minimum_stock="3")
    _set_item_stock(db_session, negative["id"], "-1")

    expected_by_status = {
        "in_stock": ["Disponible"],
        "low_stock": ["Bajo stock", "Igual al mínimo"],
        "out_of_stock": ["Agotado"],
        "negative": ["Negativo"],
    }

    seen_names = []
    for stock_status, expected_names in expected_by_status.items():
        response = client.get(
            "/api/v1/inventory/items",
            headers=_headers(tenant),
            params={"stock_status": stock_status, "sort_by": "name", "sort_direction": "asc"},
        )

        assert response.status_code == 200
        names = [item["name"] for item in response.json()["data"]]
        assert names == expected_names
        seen_names.extend(names)

    assert sorted(seen_names) == [
        "Agotado",
        "Bajo stock",
        "Disponible",
        "Igual al mínimo",
        "Negativo",
    ]


@pytest.mark.parametrize(
    ("sort_by", "sort_direction", "expected_names"),
    [
        ("current_stock", "asc", ["Stock 1", "Stock 5", "Stock 9"]),
        ("current_stock", "desc", ["Stock 9", "Stock 5", "Stock 1"]),
        ("sale_price_ars", "asc", ["Stock 9", "Stock 1", "Stock 5"]),
        ("sale_price_ars", "desc", ["Stock 5", "Stock 1", "Stock 9"]),
        ("name", "asc", ["Stock 1", "Stock 5", "Stock 9"]),
        ("internal_code", "asc", ["Stock 1", "Stock 5", "Stock 9"]),
    ],
)
def test_inventory_sorting(client, tenant, sort_by, sort_direction, expected_names):
    _create_item(client, tenant, name="Stock 1", current_stock="1", sale_price_ars="200")
    _create_item(client, tenant, name="Stock 5", current_stock="5", sale_price_ars="300")
    _create_item(client, tenant, name="Stock 9", current_stock="9", sale_price_ars="100")

    response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"sort_by": sort_by, "sort_direction": sort_direction},
    )

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["data"]] == expected_names


def test_inventory_sorting_accepts_legacy_sort_order_alias(client, tenant):
    _create_item(client, tenant, name="A", current_stock="1")
    _create_item(client, tenant, name="B", current_stock="5")

    response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"sort_by": "current_stock", "sort_order": "desc"},
    )

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["data"]] == ["B", "A"]


def test_inventory_sorting_has_stable_secondary_order(client, tenant):
    first = _create_item(client, tenant, name="Mismo stock A", current_stock="4")
    second = _create_item(client, tenant, name="Mismo stock B", current_stock="4")

    response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"sort_by": "current_stock", "sort_direction": "asc"},
    )

    assert response.status_code == 200
    items = response.json()["data"]
    expected_ids = sorted([first["id"], second["id"]], key=uuid.UUID)
    assert [item["id"] for item in items] == expected_ids


def test_inventory_combines_search_and_filters(client, tenant):
    _create_item(
        client,
        tenant,
        name="Alimento renal adulto",
        category="food",
        brand="Royal Canin",
        supplier="Distribuidora Norte",
        current_stock="2",
        minimum_stock="5",
    )
    _create_item(
        client,
        tenant,
        name="Alimento renal cachorro",
        category="food",
        brand="Royal Canin",
        supplier="Distribuidora Sur",
        current_stock="2",
        minimum_stock="5",
    )
    _create_item(
        client,
        tenant,
        name="Alimento adulto",
        category="food",
        brand="Purina",
        supplier="Distribuidora Norte",
        current_stock="8",
        minimum_stock="3",
    )

    response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={
            "search": "renal",
            "category": "food",
            "brand": "royal canin",
            "supplier": "distribuidora norte",
            "stock_status": "low_stock",
        },
    )

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["data"]] == ["Alimento renal adulto"]


def test_inventory_combines_search_with_brand(client, tenant):
    _create_item(client, tenant, name="Alimento renal adulto", brand="Royal Canin")
    _create_item(client, tenant, name="Alimento renal cachorro", brand="Purina")

    response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"search": "renal", "brand": "royal canin"},
    )

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["data"]] == ["Alimento renal adulto"]


def test_inventory_combines_search_with_supplier(client, tenant):
    _create_item(client, tenant, name="Alimento renal adulto", supplier="Distribuidora Norte")
    _create_item(client, tenant, name="Alimento renal cachorro", supplier="Distribuidora Sur")

    response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"search": "renal", "supplier": "distribuidora norte"},
    )

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["data"]] == ["Alimento renal adulto"]


def test_inventory_search_precedes_legacy_q(client, tenant):
    _create_item(client, tenant, name="Amoxicilina")
    _create_item(client, tenant, name="Jeringa")

    response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"search": "amoxi", "q": "jeringa"},
    )

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["data"]] == ["Amoxicilina"]


def test_inventory_empty_legacy_params_do_not_override_current_params(client, tenant):
    _create_item(client, tenant, name="A", current_stock="1")
    _create_item(client, tenant, name="B", current_stock="5")

    response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={
            "search": "b",
            "q": "",
            "sort_by": "current_stock",
            "sort_direction": "desc",
            "sort_order": "",
        },
    )

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["data"]] == ["B"]


def test_inventory_pagination_and_page_size_limit(client, tenant):
    for index in range(3):
        _create_item(client, tenant, name=f"Item {index}")

    response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"page": 2, "page_size": 2, "sort_by": "name", "sort_direction": "asc"},
    )
    max_response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"page_size": 100},
    )
    over_max_response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"page_size": 101},
    )

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["data"]] == ["Item 2"]
    assert response.json()["meta"] == {"page": 2, "page_size": 2, "total": 3, "total_pages": 2}
    assert max_response.status_code == 200
    assert max_response.json()["meta"]["page_size"] == 100
    assert over_max_response.status_code == 422
    assert over_max_response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize(
    "params",
    [
        {"category": "invalid"},
        {"stock_status": "expired"},
        {"sort_by": "created_at"},
        {"sort_direction": "sideways"},
    ],
)
def test_inventory_list_rejects_invalid_filter_values(client, tenant, params):
    response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params=params,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_inventory_list_and_options_exclude_other_tenants(client, tenant, other_tenant):
    _create_item(client, tenant, name="Item propio", brand="Propia", supplier="Proveedor propio")
    _create_item(client, other_tenant, name="Item ajeno", brand="Ajena", supplier="Proveedor ajeno")

    list_response = client.get(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        params={"search": "item", "sort_by": "name", "sort_direction": "asc"},
    )
    options_response = client.get("/api/v1/inventory/filter-options", headers=_headers(tenant))

    assert list_response.status_code == 200
    assert [item["name"] for item in list_response.json()["data"]] == ["Item propio"]
    assert options_response.status_code == 200
    assert options_response.json()["data"] == {
        "brands": ["Propia"],
        "suppliers": ["Proveedor propio"],
    }


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
        current_stock="8",
        expiration_date=(date.today() + timedelta(days=12)).isoformat(),
    )
    _create_item(
        client,
        tenant,
        name="Vencido",
        current_stock="8",
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
    data = response.json()["data"]
    assert data["id"] == item["id"]
    assert {
        "purchase_tax_rate_percentage",
        "sale_tax_rate_percentage",
        "purchase_tax_amount_ars",
        "purchase_price_with_tax_ars",
        "sale_tax_amount_ars",
        "sale_price_with_tax_ars",
    } <= data.keys()


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
    assert data["sale_price_ars"] == "3630.00"
    assert data["updated_at"] >= original_updated_at
    assert data["updated_at"] != original_updated_at


def test_reject_current_stock_in_create_payload(client, tenant):
    payload = _item_payload()
    payload["current_stock"] = "10"

    response = client.post(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_reject_current_stock_in_update_payload(client, tenant):
    item = _create_item(client, tenant, current_stock="5")

    response = client.patch(
        f"/api/v1/inventory/items/{item['id']}",
        headers=_headers(tenant),
        json={"current_stock": "99"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"

    item_response = client.get(f"/api/v1/inventory/items/{item['id']}", headers=_headers(tenant))
    assert item_response.json()["data"]["current_stock"] == "5.00"


def test_round_sale_price_to_nearest_10(client, tenant):
    response = client.post(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        json=_item_payload(purchase_price_ars="1013", profit_margin_percentage="35", round_sale_price=True),
    )

    assert response.status_code == 201
    assert response.json()["data"]["sale_price_ars"] == "1650.00"


def test_create_item_calculates_purchase_and_sale_tax(client, tenant):
    item = _create_item(
        client,
        tenant,
        purchase_price_ars="1000",
        purchase_tax_rate_percentage="21",
        profit_margin_percentage="80",
        sale_tax_rate_percentage="21",
        round_sale_price=False,
    )

    assert item["purchase_tax_amount_ars"] == "210.00"
    assert item["purchase_price_with_tax_ars"] == "1210.00"
    assert item["sale_price_ars"] == "2178.00"
    assert item["sale_tax_amount_ars"] == "457.38"
    assert item["sale_price_with_tax_ars"] == "2635.38"


def test_create_item_preserves_manual_sale_price_and_calculates_tax(client, tenant):
    item = _create_item(
        client,
        tenant,
        purchase_price_ars="1000",
        purchase_tax_rate_percentage="21",
        profit_margin_percentage="80",
        sale_price_ars="3874",
        sale_tax_rate_percentage="21",
    )

    assert item["sale_price_ars"] == "3874.00"
    assert item["sale_tax_amount_ars"] == "813.54"
    assert item["sale_price_with_tax_ars"] == "4687.54"


def test_round_sale_price_before_calculating_sale_tax(client, tenant):
    item = _create_item(
        client,
        tenant,
        purchase_price_ars="1000",
        purchase_tax_rate_percentage="21",
        profit_margin_percentage="80",
        sale_tax_rate_percentage="21",
        round_sale_price=True,
    )

    assert item["sale_price_ars"] == "2180.00"
    assert item["sale_tax_amount_ars"] == "457.80"
    assert item["sale_price_with_tax_ars"] == "2637.80"


def test_update_purchase_tax_recalculates_automatic_sale_price(client, tenant):
    item = _create_item(client, tenant)

    response = client.patch(
        f"/api/v1/inventory/items/{item['id']}",
        headers=_headers(tenant),
        json={"purchase_tax_rate_percentage": "21"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["purchase_tax_rate_percentage"] == "21.00"
    assert data["purchase_price_with_tax_ars"] == "1210.00"
    assert data["sale_price_ars"] == "1633.50"


def test_explicit_zero_purchase_tax_is_preserved(client, tenant):
    item = _create_item(client, tenant, purchase_tax_rate_percentage="0")

    assert item["purchase_tax_rate_percentage"] == "0.00"
    assert item["purchase_price_with_tax_ars"] == "1000.00"
    assert item["sale_price_ars"] == "1350.00"


def test_custom_purchase_tax_is_preserved(client, tenant):
    item = _create_item(client, tenant, purchase_tax_rate_percentage="10.50")

    assert item["purchase_tax_rate_percentage"] == "10.50"
    assert item["purchase_tax_amount_ars"] == "105.00"
    assert item["purchase_price_with_tax_ars"] == "1105.00"
    assert item["sale_price_ars"] == "1491.75"


def test_update_sale_tax_changes_totals_without_changing_sale_price(client, tenant):
    item = _create_item(client, tenant)

    response = client.patch(
        f"/api/v1/inventory/items/{item['id']}",
        headers=_headers(tenant),
        json={"sale_tax_rate_percentage": "21"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["sale_price_ars"] == "1633.50"
    assert data["sale_tax_amount_ars"] == "343.04"
    assert data["sale_price_with_tax_ars"] == "1976.54"


def test_update_manual_sale_price_preserves_value_and_calculates_tax(client, tenant):
    item = _create_item(client, tenant, sale_tax_rate_percentage="21")

    response = client.patch(
        f"/api/v1/inventory/items/{item['id']}",
        headers=_headers(tenant),
        json={"sale_price_ars": "3874"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["sale_price_ars"] == "3874.00"
    assert data["sale_tax_amount_ars"] == "813.54"
    assert data["sale_price_with_tax_ars"] == "4687.54"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("purchase_tax_rate_percentage", "-0.01"),
        ("purchase_tax_rate_percentage", "100.01"),
        ("sale_tax_rate_percentage", "-0.01"),
        ("sale_tax_rate_percentage", "100.01"),
    ],
)
def test_reject_invalid_inventory_tax_rates(client, tenant, field, value):
    response = client.post(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        json=_item_payload(**{field: value}),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_tax_totals_are_null_when_prices_are_null(client, tenant):
    item = _create_item(client, tenant, purchase_price_ars=None)

    assert item["purchase_tax_amount_ars"] is None
    assert item["purchase_price_with_tax_ars"] is None
    assert item["sale_price_ars"] is None
    assert item["sale_tax_amount_ars"] is None
    assert item["sale_price_with_tax_ars"] is None


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
    assert movement["movement_type"] == "manual_entry"
    assert movement["unit_cost_ars"] == "1000.00"
    assert movement["stock_before"] == "10.00"
    assert movement["stock_after"] == "15.00"
    assert movement["unit"] == "tablet"
    assert movement["source_type"] == "manual"
    assert movement["operation_id"] is not None
    assert movement["reversal_status"] == "active"
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
    assert movement["movement_type"] == "manual_exit"
    assert movement["total_sale_price_ars"] == "8000.00"
    assert movement["stock_before"] == "10.00"
    assert movement["stock_after"] == "6.00"
    assert movement["source_type"] == "manual"

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
    assert {"stock_before", "stock_after", "operation_id", "reversal_status"} <= payload["data"][0].keys()


def test_global_movement_list_filters_and_searches_with_tenant_scope(client, tenant, other_tenant):
    own_item = _create_item(client, tenant, name="Antiparasitario trazable")
    other_item = _create_item(client, other_tenant, name="Antiparasitario ajeno")
    own_entry = client.post(
        f"/api/v1/inventory/items/{own_item['id']}/movements/entry",
        headers=_headers(tenant),
        json={"quantity": "3", "notes": "Compra trazable"},
    ).json()["data"]
    client.post(
        f"/api/v1/inventory/items/{other_item['id']}/movements/entry",
        headers=_headers(other_tenant),
        json={"quantity": "2"},
    )

    response = client.get(
        "/api/v1/inventory/movements",
        headers=_headers(tenant),
        params={
            "search": "trazable",
            "inventory_item_id": own_item["id"],
            "movement_type": "manual_entry",
            "source_type": "manual",
            "operation_id": own_entry["operation_id"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [movement["id"] for movement in payload["data"]] == [own_entry["id"]]
    assert payload["data"][0]["inventory_item_name"] == "Antiparasitario trazable"
    assert payload["data"][0]["inventory_item_internal_code"] == own_item["internal_code"]


def test_global_movement_list_filters_by_created_by_and_date(client, db_session, tenant, monkeypatch):
    _setup_auth(monkeypatch)
    user = _create_user(db_session, tenant, "movements@example.com", "Movement Vet")
    item_response = client.post(
        "/api/v1/inventory/items",
        headers=_auth_headers(user.email),
        json=_item_payload(name="Producto con usuario"),
    )
    item = item_response.json()["data"]
    client.post(
        f"/api/v1/inventory/items/{item['id']}/movements/entry",
        headers=_auth_headers(user.email),
        json={"quantity": "4"},
    )

    response = client.get(
        "/api/v1/inventory/movements",
        headers=_headers(tenant),
        params={
            "created_by_user_id": str(user.id),
            "date_from": date.today().isoformat(),
            "date_to": date.today().isoformat(),
        },
    )

    assert response.status_code == 200
    movements = response.json()["data"]
    assert len(movements) == 1
    assert movements[0]["created_by_user_name"] == "Movement Vet"


def test_reject_invalid_movement_date_range(client, tenant):
    response = client.get(
        "/api/v1/inventory/movements",
        headers=_headers(tenant),
        params={"date_from": "2026-08-03", "date_to": "2026-08-02"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_date_range"


def test_reverse_movement_creates_reversal_and_updates_original_status(client, tenant):
    item = _create_item(client, tenant, current_stock="10")
    entry_response = client.post(
        f"/api/v1/inventory/items/{item['id']}/movements/entry",
        headers=_headers(tenant),
        json={"quantity": "5"},
    )
    original = entry_response.json()["data"]

    reverse_response = client.post(
        f"/api/v1/inventory/movements/{original['id']}/reverse",
        headers=_headers(tenant),
        json={"reason": "error_operativo", "notes": "Se anula entrada duplicada"},
    )

    assert reverse_response.status_code == 201
    reversal = reverse_response.json()["data"]
    assert reversal["movement_type"] == "reversal"
    assert reversal["quantity"] == "5.00"
    assert reversal["stock_before"] == "15.00"
    assert reversal["stock_after"] == "10.00"
    assert reversal["reverses_movement_id"] == original["id"]
    assert reversal["source_type"] == "reversal"
    assert reversal["source_id"] == original["id"]

    item_response = client.get(f"/api/v1/inventory/items/{item['id']}", headers=_headers(tenant))
    assert item_response.json()["data"]["current_stock"] == "10.00"

    detail_response = client.get(
        f"/api/v1/inventory/movements/{original['id']}",
        headers=_headers(tenant),
    )
    detail = detail_response.json()["data"]
    assert detail["reversal_status"] == "reversed"
    assert detail["reversed_by_movement_id"] == reversal["id"]
    assert detail["can_be_reversed"] is False
    assert detail["reversal_block_reason"] == "movement_already_reversed"


def test_prevent_double_reversal_and_reversal_of_reversal(client, tenant):
    item = _create_item(client, tenant, current_stock="4")
    original = client.post(
        f"/api/v1/inventory/items/{item['id']}/movements/exit",
        headers=_headers(tenant),
        json={"quantity": "1", "reason": "sale"},
    ).json()["data"]
    reversal = client.post(
        f"/api/v1/inventory/movements/{original['id']}/reverse",
        headers=_headers(tenant),
        json={"reason": "venta_cancelada"},
    ).json()["data"]

    second_response = client.post(
        f"/api/v1/inventory/movements/{original['id']}/reverse",
        headers=_headers(tenant),
        json={"reason": "duplicada"},
    )
    reversal_response = client.post(
        f"/api/v1/inventory/movements/{reversal['id']}/reverse",
        headers=_headers(tenant),
        json={"reason": "no_permitido"},
    )

    assert second_response.status_code == 409
    assert second_response.json()["error"]["code"] == "movement_already_reversed"
    assert reversal_response.status_code == 409
    assert reversal_response.json()["error"]["code"] == "reversal_not_allowed"


def test_reversing_entry_is_blocked_when_current_stock_is_too_low(client, tenant):
    item = _create_item(client, tenant, current_stock="5")
    original = client.get(
        f"/api/v1/inventory/items/{item['id']}/movements",
        headers=_headers(tenant),
    ).json()["data"][0]
    exit_response = client.post(
        f"/api/v1/inventory/items/{item['id']}/movements/exit",
        headers=_headers(tenant),
        json={"quantity": "4", "reason": "sale"},
    )
    assert exit_response.status_code == 201

    response = client.post(
        f"/api/v1/inventory/movements/{original['id']}/reverse",
        headers=_headers(tenant),
        json={"reason": "stock_insuficiente"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_stock_for_reversal"


def test_reversal_status_filter_classifies_movements(client, tenant):
    item = _create_item(client, tenant, current_stock="5")
    original = client.post(
        f"/api/v1/inventory/items/{item['id']}/movements/exit",
        headers=_headers(tenant),
        json={"quantity": "2", "reason": "sale"},
    ).json()["data"]
    reversal = client.post(
        f"/api/v1/inventory/movements/{original['id']}/reverse",
        headers=_headers(tenant),
        json={"reason": "venta_cancelada"},
    ).json()["data"]

    reversed_response = client.get(
        "/api/v1/inventory/movements",
        headers=_headers(tenant),
        params={"reversal_status": "reversed"},
    )
    reversal_response = client.get(
        "/api/v1/inventory/movements",
        headers=_headers(tenant),
        params={"reversal_status": "reversal"},
    )

    assert reversed_response.status_code == 200
    assert original["id"] in [movement["id"] for movement in reversed_response.json()["data"]]
    assert reversal_response.status_code == 200
    assert [movement["id"] for movement in reversal_response.json()["data"]] == [reversal["id"]]


def test_prevent_cross_tenant_movement_read_and_reversal(client, tenant, other_tenant):
    item = _create_item(client, other_tenant, current_stock="3")
    foreign_movement = client.get(
        f"/api/v1/inventory/items/{item['id']}/movements",
        headers=_headers(other_tenant),
    ).json()["data"][0]

    detail_response = client.get(
        f"/api/v1/inventory/movements/{foreign_movement['id']}",
        headers=_headers(tenant),
    )
    reverse_response = client.post(
        f"/api/v1/inventory/movements/{foreign_movement['id']}/reverse",
        headers=_headers(tenant),
        json={"reason": "intento_cross_tenant"},
    )

    assert detail_response.status_code == 404
    assert reverse_response.status_code == 404


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
    item = _create_item(
        client,
        tenant,
        current_stock="1",
        minimum_stock="3",
        expiration_date=(date.today() + timedelta(days=14)).isoformat(),
    )

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

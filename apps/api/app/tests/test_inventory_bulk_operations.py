import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.inventory_bulk_operation import InventoryBulkOperation
from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.user import User
from app.models.supplier import Supplier
from app.repositories.inventory import InventoryRepository


def _headers(tenant) -> dict[str, str]:
    return {"X-Tenant-Id": str(tenant.id)}


def _user_headers(email: str) -> dict[str, str]:
    return {"X-User-Email": email}


def _create_user(db_session, tenant, email="bulk@vetflow.local") -> User:
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=email,
        full_name="Bulk User",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_item(db_session, tenant, **overrides) -> InventoryItem:
    item = InventoryItem(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        internal_code=overrides.pop("internal_code", f"MED-{uuid.uuid4().hex[:5]}"),
        name=overrides.pop("name", "Producto"),
        category=overrides.pop("category", "medication"),
        brand=overrides.pop("brand", "Marca"),
        supplier=overrides.pop("supplier", "Proveedor"),
        unit=overrides.pop("unit", "tablet"),
        current_stock=Decimal(str(overrides.pop("current_stock", "5"))),
        minimum_stock=Decimal(str(overrides.pop("minimum_stock", "2"))),
        purchase_price_ars=overrides.pop("purchase_price_ars", Decimal("100")),
        purchase_tax_rate_percentage=Decimal(str(overrides.pop("purchase_tax_rate_percentage", "21"))),
        profit_margin_percentage=Decimal(str(overrides.pop("profit_margin_percentage", "35"))),
        sale_price_ars=overrides.pop("sale_price_ars", Decimal("163.35")),
        sale_tax_rate_percentage=Decimal(str(overrides.pop("sale_tax_rate_percentage", "0"))),
        round_sale_price=overrides.pop("round_sale_price", False),
        is_active=overrides.pop("is_active", True),
        notes=overrides.pop("notes", None),
        **overrides,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


def _supplier(db_session, tenant, name="Proveedor existente", *, active=True):
    supplier = Supplier(tenant_id=tenant.id, name=name, normalized_name=name.casefold(), is_active=active)
    db_session.add(supplier)
    db_session.commit()
    return supplier


def _registered_supplier_operation(db_session, tenant, operation):
    if operation["operation_type"] != "set_supplier":
        return operation
    supplier = _supplier(db_session, tenant, operation["supplier"])
    return {"operation_type": "set_supplier", "supplier_id": str(supplier.id)}


def _payload(item_ids, operation=None, excluded_ids=None):
    return {
        "selection": {
            "selection_mode": "selected",
            "selected_ids": [str(item_id) for item_id in item_ids],
            "excluded_ids": [str(item_id) for item_id in (excluded_ids or [])],
        },
        "operation": operation or {
            "operation_type": "increase_sale_price_percentage",
            "percentage": "10",
        },
    }


def _filtered_payload(filters, operation=None, excluded_ids=None):
    return {
        "selection": {
            "selection_mode": "filtered",
            "filters": filters,
            "excluded_ids": [str(item_id) for item_id in (excluded_ids or [])],
        },
        "operation": operation or {
            "operation_type": "set_brand",
            "brand": "Nueva",
        },
    }


def _preview(client, tenant, payload, headers=None):
    merged_headers = _headers(tenant)
    if headers:
        merged_headers.update(headers)
    return client.post(
        "/api/v1/inventory/bulk-operations/preview",
        headers=merged_headers,
        json=payload,
    )


def _confirm(client, tenant, operation_id, headers=None):
    merged_headers = _headers(tenant)
    if headers:
        merged_headers.update(headers)
    return client.post(
        f"/api/v1/inventory/bulk-operations/{operation_id}/confirm",
        headers=merged_headers,
        json={"confirm": True},
    )


def _reverse(client, tenant, operation_id, reason="Corrección", headers=None):
    merged_headers = _headers(tenant)
    if headers:
        merged_headers.update(headers)
    return client.post(
        f"/api/v1/inventory/bulk-operations/{operation_id}/reverse",
        headers=merged_headers,
        json={"reason": reason},
    )


def test_bulk_preview_requires_tenant_context(client):
    response = client.post(
        "/api/v1/inventory/bulk-operations/preview",
        json={"selection": {"selection_mode": "selected", "selected_ids": []}, "operation": {"operation_type": "activate"}},
    )

    assert response.status_code == 400


def test_bulk_preview_manual_selection_persists_and_deduplicates(client, tenant, db_session):
    item = _create_item(db_session, tenant)

    response = _preview(client, tenant, _payload([item.id, item.id]))

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["status"] == "preview"
    assert data["selected_count"] == 1
    assert len(data["items"]) == 1
    assert db_session.get(InventoryBulkOperation, uuid.UUID(data["id"])) is not None


def test_bulk_preview_filtered_selection_and_exclusions(client, tenant, db_session):
    first = _create_item(db_session, tenant, name="Amoxi A", brand="A")
    second = _create_item(db_session, tenant, name="Amoxi B", brand="A")
    _create_item(db_session, tenant, name="Otro", brand="B")

    response = _preview(
        client,
        tenant,
        _filtered_payload({"search": "amoxi", "brand": "A"}, excluded_ids=[second.id]),
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["selected_count"] == 2
    assert data["excluded_count"] == 1
    assert data["items"][0]["inventory_item_id"] == str(first.id)


def test_bulk_preview_rejects_other_tenant_selected_id(client, tenant, other_tenant, db_session):
    other_item = _create_item(db_session, other_tenant)

    response = _preview(client, tenant, _payload([other_item.id]))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "inventory_item_not_found"


def test_bulk_preview_rejects_too_many_selected_ids(client, tenant):
    response = _preview(client, tenant, _payload([uuid.uuid4() for _ in range(501)]))

    assert response.status_code == 422


def test_bulk_preview_rejects_too_many_filtered_products(client, tenant, monkeypatch):
    def fake_bulk_filter(self, *args, **kwargs):
        return [], 2001

    monkeypatch.setattr(InventoryRepository, "list_items_for_bulk_filter", fake_bulk_filter)

    response = _preview(client, tenant, _filtered_payload({}))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "inventory_bulk_operation_too_large"


def test_bulk_preview_does_not_modify_products_or_stock(client, tenant, db_session):
    item = _create_item(db_session, tenant, sale_price_ars=Decimal("100"), current_stock="9")

    response = _preview(client, tenant, _payload([item.id]))

    assert response.status_code == 201
    db_session.refresh(item)
    assert item.sale_price_ars == Decimal("100.00")
    assert item.current_stock == Decimal("9.00")
    assert db_session.scalar(select(InventoryMovement)) is None


@pytest.mark.parametrize(
    ("operation", "field", "expected"),
    [
        ({"operation_type": "increase_sale_price_percentage", "percentage": "10"}, "sale_price_ars", "110.00"),
        ({"operation_type": "decrease_sale_price_percentage", "percentage": "10"}, "sale_price_ars", "90.00"),
        ({"operation_type": "set_sale_price", "sale_price_ars": "150"}, "sale_price_ars", "150.00"),
        ({"operation_type": "set_minimum_stock", "minimum_stock": "4.5"}, "minimum_stock", "4.5"),
        ({"operation_type": "set_brand", "brand": "Nueva marca"}, "brand", "Nueva marca"),
        ({"operation_type": "set_supplier", "supplier": "Nuevo proveedor"}, "supplier", "Nuevo proveedor"),
        ({"operation_type": "activate"}, "is_active", True),
        ({"operation_type": "deactivate"}, "is_active", False),
    ],
)
def test_bulk_preview_calculates_supported_operations(client, tenant, db_session, operation, field, expected):
    operation = _registered_supplier_operation(db_session, tenant, operation)
    item = _create_item(db_session, tenant, purchase_price_ars=Decimal("50"), purchase_tax_rate_percentage="0", profit_margin_percentage="100", sale_price_ars=Decimal("100"), is_active=True)

    response = _preview(client, tenant, _payload([item.id], operation=operation))

    assert response.status_code == 201
    row = response.json()["data"]["items"][0]
    assert row["field_name"] == field
    value = row["new_value_json"]["value"]
    if field == "sale_price_ars":
        assert Decimal(value["sale_price_ars"]) == Decimal(expected)
        assert row["status"] == "pending"
    elif field == "supplier":
        assert value == {"supplier": expected, "supplier_id": operation["supplier_id"]}
    else:
        assert value == expected


@pytest.mark.parametrize(
    "operation",
    [
        {"operation_type": "increase_sale_price_percentage", "percentage": "0"},
        {"operation_type": "increase_sale_price_percentage", "percentage": "-1"},
        {"operation_type": "set_sale_price", "sale_price_ars": "-1"},
        {"operation_type": "set_minimum_stock", "minimum_stock": "-1"},
        {"operation_type": "set_brand", "brand": ""},
        {"operation_type": "set_supplier", "supplier": ""},
    ],
)
def test_bulk_preview_rejects_invalid_operation_values(client, tenant, db_session, operation):
    item = _create_item(db_session, tenant)

    response = _preview(client, tenant, _payload([item.id], operation=operation))

    assert response.status_code == 422


def test_bulk_preview_marks_no_change(client, tenant, db_session):
    item = _create_item(db_session, tenant, brand="Misma")

    response = _preview(
        client,
        tenant,
        _payload([item.id], operation={"operation_type": "set_brand", "brand": "Misma"}),
    )

    assert response.status_code == 201
    assert response.json()["data"]["items"][0]["status"] == "unchanged"


def test_bulk_preview_set_margin_recalculates_sale_price(client, tenant, db_session):
    item = _create_item(db_session, tenant, purchase_price_ars=Decimal("100"), purchase_tax_rate_percentage="21")

    response = _preview(
        client,
        tenant,
        _payload([item.id], operation={"operation_type": "set_profit_margin_percentage", "profit_margin_percentage": "50"}),
    )

    assert response.status_code == 201
    row = response.json()["data"]["items"][0]
    assert row["new_value_json"]["value"]["profit_margin_percentage"] == "50"
    assert row["new_value_json"]["value"]["sale_price_ars"] == "181.50"


def test_bulk_preview_handles_null_historical_sale_price_as_invalid(client, tenant, db_session):
    item = _create_item(db_session, tenant, sale_price_ars=None)

    response = _preview(client, tenant, _payload([item.id]))

    assert response.status_code == 201
    row = response.json()["data"]["items"][0]
    assert row["status"] == "invalid"
    assert row["error_message"] == "sale_price_missing"


def test_bulk_confirm_applies_changes_and_records_user(client, tenant, db_session):
    user = _create_user(db_session, tenant)
    item = _create_item(db_session, tenant, brand="Antes")
    preview = _preview(
        client,
        tenant,
        _payload([item.id], operation={"operation_type": "set_brand", "brand": "Después"}),
        headers=_user_headers(user.email),
    ).json()["data"]

    response = _confirm(client, tenant, preview["id"])

    assert response.status_code == 200
    data = response.json()["data"]
    db_session.refresh(item)
    assert item.brand == "Después"
    assert data["status"] == "confirmed"
    assert data["created_by_user_id"] == str(user.id)
    assert data["created_by_user_name"] == "Bulk User"
    assert data["created_by_user_email"] == user.email
    assert data["confirmed_at"] is not None
    assert data["reversed_by_user_id"] is None
    assert data["reversed_by_user_name"] is None
    assert data["reversed_by_user_email"] is None
    assert data["reversed_at"] is None
    assert data["reversal_reason"] is None
    assert data["affected_count"] == 1


def test_bulk_confirm_rejects_double_confirm(client, tenant, db_session):
    item = _create_item(db_session, tenant)
    preview = _preview(client, tenant, _payload([item.id])).json()["data"]
    assert _confirm(client, tenant, preview["id"]).status_code == 200

    response = _confirm(client, tenant, preview["id"])

    assert response.status_code == 409


def test_bulk_confirm_rejects_expired_preview(client, tenant, db_session):
    item = _create_item(db_session, tenant)
    preview = _preview(client, tenant, _payload([item.id])).json()["data"]
    operation = db_session.get(InventoryBulkOperation, uuid.UUID(preview["id"]))
    operation.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.add(operation)
    db_session.commit()

    response = _confirm(client, tenant, preview["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "inventory_bulk_operation_expired"


def test_bulk_confirm_detects_conflict_and_rolls_back(client, tenant, db_session):
    first = _create_item(db_session, tenant, brand="Antes")
    second = _create_item(db_session, tenant, brand="Antes")
    preview = _preview(
        client,
        tenant,
        _payload([first.id, second.id], operation={"operation_type": "set_brand", "brand": "Después"}),
    ).json()["data"]
    second.updated_at = second.updated_at + timedelta(seconds=5)
    db_session.add(second)
    db_session.commit()

    response = _confirm(client, tenant, preview["id"])

    db_session.refresh(first)
    db_session.refresh(second)
    assert response.status_code == 409
    assert first.brand == "Antes"
    assert second.brand == "Antes"


def test_bulk_history_detail_and_tenant_scope(client, tenant, other_tenant, db_session):
    user = _create_user(db_session, tenant)
    item = _create_item(db_session, tenant)
    preview = _preview(client, tenant, _payload([item.id]), headers=_user_headers(user.email)).json()["data"]
    assert _confirm(client, tenant, preview["id"]).status_code == 200

    history = client.get("/api/v1/inventory/bulk-operations", headers=_headers(tenant))
    detail = client.get(f"/api/v1/inventory/bulk-operations/{preview['id']}", headers=_headers(tenant))
    foreign_detail = client.get(f"/api/v1/inventory/bulk-operations/{preview['id']}", headers=_headers(other_tenant))

    assert history.status_code == 200
    history_item = history.json()["data"][0]
    assert history_item["id"] == preview["id"]
    assert history_item["created_by_user_name"] == "Bulk User"
    assert history_item["created_by_user_email"] == user.email
    assert history_item["confirmed_at"] is not None
    assert detail.status_code == 200
    detail_data = detail.json()["data"]
    assert detail_data["created_by_user_name"] == "Bulk User"
    assert detail_data["created_by_user_email"] == user.email
    assert detail_data["items"][0]["old_value_json"] is not None
    assert foreign_detail.status_code == 404


def test_bulk_history_hides_cross_tenant_user_summary(client, tenant, other_tenant, db_session):
    foreign_user = _create_user(db_session, other_tenant, email="foreign@vetflow.local")
    item = _create_item(db_session, tenant)
    preview = _preview(client, tenant, _payload([item.id])).json()["data"]
    operation = db_session.get(InventoryBulkOperation, uuid.UUID(preview["id"]))
    operation.created_by_user_id = foreign_user.id
    db_session.add(operation)
    db_session.commit()

    history = client.get("/api/v1/inventory/bulk-operations", headers=_headers(tenant))
    detail = client.get(f"/api/v1/inventory/bulk-operations/{preview['id']}", headers=_headers(tenant))

    assert history.status_code == 200
    assert history.json()["data"][0]["created_by_user_name"] is None
    assert history.json()["data"][0]["created_by_user_email"] is None
    assert detail.status_code == 200
    assert detail.json()["data"]["created_by_user_id"] is None
    assert detail.json()["data"]["created_by_user_name"] is None
    assert detail.json()["data"]["created_by_user_email"] is None


@pytest.mark.parametrize(
    "operation",
    [
        {"operation_type": "set_brand", "brand": "Nueva"},
        {"operation_type": "set_supplier", "supplier": "Nuevo"},
        {"operation_type": "set_minimum_stock", "minimum_stock": "9"},
        {"operation_type": "activate"},
        {"operation_type": "deactivate"},
        {"operation_type": "set_sale_price", "sale_price_ars": "321"},
    ],
)
def test_bulk_reverse_reverts_supported_operations(client, tenant, db_session, operation):
    operation = _registered_supplier_operation(db_session, tenant, operation)
    item = _create_item(
        db_session,
        tenant,
        brand="Antes",
        supplier="Prov",
        minimum_stock="1",
        is_active=operation["operation_type"] != "activate",
        sale_price_ars=Decimal("100"),
    )
    preview = _preview(client, tenant, _payload([item.id], operation=operation)).json()["data"]
    assert _confirm(client, tenant, preview["id"]).status_code == 200

    response = _reverse(client, tenant, preview["id"])

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "reversed"
    assert response.json()["data"]["reversed_count"] == 1


def test_bulk_reverse_requires_reason(client, tenant, db_session):
    item = _create_item(db_session, tenant)
    preview = _preview(client, tenant, _payload([item.id])).json()["data"]
    assert _confirm(client, tenant, preview["id"]).status_code == 200

    response = _reverse(client, tenant, preview["id"], reason="")

    assert response.status_code == 422


def test_bulk_reverse_records_reversal_user_date_and_reason(client, tenant, db_session):
    creator = _create_user(db_session, tenant, email="creator@vetflow.local")
    reverser = _create_user(db_session, tenant, email="reverser@vetflow.local")
    item = _create_item(db_session, tenant, brand="Antes")
    preview = _preview(
        client,
        tenant,
        _payload([item.id], operation={"operation_type": "set_brand", "brand": "Después"}),
        headers=_user_headers(creator.email),
    ).json()["data"]
    assert _confirm(client, tenant, preview["id"]).status_code == 200

    response = _reverse(
        client,
        tenant,
        preview["id"],
        reason="Volver a marca anterior",
        headers=_user_headers(reverser.email),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "reversed"
    assert data["reversed_by_user_id"] == str(reverser.id)
    assert data["reversed_by_user_name"] == "Bulk User"
    assert data["reversed_by_user_email"] == reverser.email
    assert data["reversed_at"] is not None
    assert data["reversal_reason"] == "Volver a marca anterior"

    history = client.get("/api/v1/inventory/bulk-operations", headers=_headers(tenant))
    assert history.status_code == 200
    history_item = history.json()["data"][0]
    assert history_item["reversed_by_user_name"] == "Bulk User"
    assert history_item["reversed_by_user_email"] == reverser.email
    assert history_item["reversed_at"] is not None


def test_bulk_reverse_partial_conflict_does_not_overwrite_changed_product(client, tenant, db_session):
    first = _create_item(db_session, tenant, brand="Antes")
    second = _create_item(db_session, tenant, brand="Antes")
    preview = _preview(
        client,
        tenant,
        _payload([first.id, second.id], operation={"operation_type": "set_brand", "brand": "Después"}),
    ).json()["data"]
    assert _confirm(client, tenant, preview["id"]).status_code == 200
    second.brand = "Cambio posterior"
    db_session.add(second)
    db_session.commit()

    response = _reverse(client, tenant, preview["id"])

    db_session.refresh(first)
    db_session.refresh(second)
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "partially_reversed"
    assert first.brand == "Antes"
    assert second.brand == "Cambio posterior"


def test_bulk_reverse_rejects_second_reversal(client, tenant, db_session):
    item = _create_item(db_session, tenant)
    preview = _preview(client, tenant, _payload([item.id])).json()["data"]
    assert _confirm(client, tenant, preview["id"]).status_code == 200
    assert _reverse(client, tenant, preview["id"]).status_code == 200

    response = _reverse(client, tenant, preview["id"])

    assert response.status_code == 409


def test_filtered_selection_reuses_category_supplier_stock_and_active(client, tenant, db_session):
    matching = _create_item(db_session, tenant, category="supply", supplier="Central", current_stock="0", is_active=False, unit="unit")
    _create_item(db_session, tenant, category="supply", supplier="Central", current_stock="5", is_active=False)
    _create_item(db_session, tenant, category="medication", supplier="Central", current_stock="0", is_active=False)

    response = _preview(
        client,
        tenant,
        _filtered_payload(
            {
                "category": "supply",
                "supplier": "Central",
                "stock_status": "out_of_stock",
                "is_active": False,
            }
        ),
    )

    assert response.status_code == 201
    assert response.json()["data"]["items"][0]["inventory_item_id"] == str(matching.id)


@pytest.mark.parametrize(
    ("operation", "initial_manual", "expected_manual"),
    [
        ({"operation_type": "set_sale_price", "sale_price_ars": "321"}, False, False),
        ({"operation_type": "increase_sale_price_percentage", "percentage": "10"}, False, False),
        (
            {"operation_type": "set_profit_margin_percentage", "profit_margin_percentage": "50"},
            True,
            False,
        ),
    ],
)
def test_bulk_price_operations_set_and_reverse_sale_price_mode(
    client, tenant, db_session, operation, initial_manual, expected_manual
):
    item = _create_item(db_session, tenant, sale_price_is_manual=initial_manual)
    preview = _preview(client, tenant, _payload([item.id], operation=operation)).json()["data"]

    assert _confirm(client, tenant, preview["id"]).status_code == 200
    db_session.refresh(item)
    assert item.sale_price_is_manual is expected_manual

    reversed_response = _reverse(client, tenant, preview["id"])
    assert reversed_response.status_code == 200
    assert reversed_response.json()["data"]["status"] == "reversed"
    db_session.refresh(item)
    assert item.sale_price_is_manual is False
    assert item.sale_price_ars == Decimal("163.35")




def _priced_item(db, tenant, **overrides):
    values = dict(purchase_price_ars=Decimal("1000"), purchase_tax_rate_percentage="0",
                  profit_margin_percentage="30", sale_price_ars=Decimal("1300"))
    values.update(overrides)
    return _create_item(db, tenant, **values)


@pytest.mark.parametrize(("operation", "margin", "price"), [
    ({"operation_type": "increase_sale_price_percentage", "percentage": "10"}, "43", "1430"),
    ({"operation_type": "decrease_sale_price_percentage", "percentage": "10"}, "17", "1170"),
    ({"operation_type": "set_profit_margin_percentage", "profit_margin_percentage": "40"}, "40", "1400"),
    ({"operation_type": "set_sale_price", "sale_price_ars": "1500"}, "50", "1500"),
])
def test_price_targets_match_preview_confirmation_and_readback(client, tenant, db_session, operation, margin, price):
    item = _priced_item(db_session, tenant)
    preview = _preview(client, tenant, _payload([item.id], operation)).json()["data"]
    row = preview["items"][0]
    assert row["status"] == "pending"
    assert Decimal(row["new_value_json"]["value"]["profit_margin_percentage"]) == Decimal(margin)
    assert Decimal(row["new_value_json"]["value"]["sale_price_ars"]) == Decimal(price)
    response = _confirm(client, tenant, preview["id"])
    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["new_value_json"] == row["new_value_json"]
    read = client.get(f"/api/v1/inventory/items/{item.id}", headers=_headers(tenant)).json()["data"]
    assert Decimal(read["profit_margin_percentage"]) == Decimal(margin)
    assert Decimal(read["sale_price_ars"]) == Decimal(price)
    assert read["sale_price_is_manual"] is False
    assert read["purchase_price_ars"] == "1000.00" and read["current_stock"] == "5.00"
    assert _confirm(client, tenant, preview["id"]).status_code == 409
    assert db_session.scalar(select(InventoryMovement)) is None
    assert _reverse(client, tenant, preview["id"]).status_code == 200
    db_session.refresh(item)
    assert item.profit_margin_percentage == Decimal("30") and item.sale_price_ars == Decimal("1300")
    assert item.sale_price_is_manual is False


def test_price_target_uses_purchase_tax_base_and_distinguishes_sale_tax(client, tenant, db_session):
    item = _priced_item(db_session, tenant, purchase_tax_rate_percentage="21", sale_tax_rate_percentage="21", sale_price_ars=Decimal("1573"))
    preview = _preview(client, tenant, _payload([item.id])).json()["data"]
    box = preview["items"][0]["new_value_json"]
    assert box["value"] == {"profit_margin_percentage": "43.00", "sale_price_ars": "1730.30"}
    assert box["sale_price_with_tax_ars"] == "2093.66"
    assert _confirm(client, tenant, preview["id"]).status_code == 200
    db_session.refresh(item)
    assert item.purchase_price_ars == 1000 and item.purchase_tax_rate_percentage == 21
    assert item.sale_price_ars == Decimal("1730.30") and item.sale_tax_rate_percentage == 21


@pytest.mark.parametrize(("overrides", "target", "error"), [
    ({}, "1300.01", "catalog_target_not_representable"),
    ({"round_sale_price": True}, "1431", "catalog_target_not_representable"),
    ({}, "900", "catalog_target_requires_negative_margin"),
    ({}, "11001", "catalog_target_margin_out_of_range"),
    ({"purchase_price_ars": Decimal("0"), "sale_price_ars": Decimal("0")}, "1", "catalog_zero_cost_target"),
    ({"purchase_price_ars": None}, "1300", "catalog_pricing_incomplete"),
])
def test_unrepresentable_target_is_invalid_before_confirmation(client, tenant, db_session, overrides, target, error):
    item = _priced_item(db_session, tenant, **overrides)
    before = (item.purchase_price_ars, item.profit_margin_percentage, item.sale_price_ars, item.current_stock)
    preview = _preview(client, tenant, _payload([item.id], {"operation_type": "set_sale_price", "sale_price_ars": target})).json()["data"]
    assert preview["items"][0]["status"] == "invalid"
    assert preview["items"][0]["error_message"] == error
    assert preview["affected_count"] == 0
    assert _confirm(client, tenant, preview["id"]).status_code == 200
    db_session.refresh(item)
    assert (item.purchase_price_ars, item.profit_margin_percentage, item.sale_price_ars, item.current_stock) == before


@pytest.mark.parametrize("operation", [
    {"operation_type": "increase_sale_price_percentage", "percentage": "10"},
    {"operation_type": "decrease_sale_price_percentage", "percentage": "100"},
    {"operation_type": "set_sale_price", "sale_price_ars": "0"},
    {"operation_type": "set_profit_margin_percentage", "profit_margin_percentage": "0"},
])
def test_zero_cost_and_zero_sale_do_not_mean_missing(client, tenant, db_session, operation):
    item = _priced_item(db_session, tenant, purchase_price_ars=Decimal("0"), profit_margin_percentage="0", sale_price_ars=Decimal("0"))
    preview = _preview(client, tenant, _payload([item.id], operation)).json()["data"]
    assert preview["items"][0]["status"] == "unchanged"
    assert preview["invalid_count"] == 0


def test_margin_only_change_is_applied_even_if_rounded_sale_is_unchanged(client, tenant, db_session):
    item = _priced_item(db_session, tenant, purchase_price_ars=Decimal("1"), profit_margin_percentage="30", sale_price_ars=Decimal("0"), round_sale_price=True)
    preview = _preview(client, tenant, _payload([item.id], {"operation_type": "set_profit_margin_percentage", "profit_margin_percentage": "40"})).json()["data"]
    assert preview["affected_count"] == 1
    assert _confirm(client, tenant, preview["id"]).status_code == 200
    db_session.refresh(item)
    assert item.sale_price_ars == 0 and item.profit_margin_percentage == 40


@pytest.mark.parametrize("operation", [
    {"operation_type": "set_brand", "brand": "Nueva"},
    {"operation_type": "set_supplier", "supplier": "Nuevo"},
    {"operation_type": "set_minimum_stock", "minimum_stock": "7"},
    {"operation_type": "activate"}, {"operation_type": "deactivate"},
])
@pytest.mark.parametrize("pending", [False, True])
def test_non_price_operations_preserve_all_pricing_and_available_stock(client, tenant, db_session, operation, pending):
    operation = _registered_supplier_operation(db_session, tenant, operation)
    item = _priced_item(db_session, tenant, purchase_price_ars=None if pending else Decimal("1000"),
                        sale_price_is_manual=pending, is_active=operation["operation_type"] != "activate")
    before = (item.purchase_price_ars, item.purchase_tax_rate_percentage, item.profit_margin_percentage,
              item.sale_price_ars, item.sale_tax_rate_percentage, item.round_sale_price, item.sale_price_is_manual, item.current_stock)
    preview = _preview(client, tenant, _payload([item.id], {**operation, "sale_price_ars": None})).json()["data"]
    assert preview["invalid_count"] == 0
    assert _confirm(client, tenant, preview["id"]).status_code == 200
    db_session.refresh(item)
    assert (item.purchase_price_ars, item.purchase_tax_rate_percentage, item.profit_margin_percentage,
            item.sale_price_ars, item.sale_tax_rate_percentage, item.round_sale_price, item.sale_price_is_manual, item.current_stock) == before


def test_invalid_rows_are_explicitly_skipped_without_losing_valid_rows(client, tenant, db_session):
    good = _priced_item(db_session, tenant)
    pending = _priced_item(db_session, tenant, purchase_price_ars=None)
    preview = _preview(client, tenant, _payload([good.id, pending.id])).json()["data"]
    assert (preview["affected_count"], preview["invalid_count"]) == (1, 1)
    assert _confirm(client, tenant, preview["id"]).status_code == 200
    db_session.refresh(good); db_session.refresh(pending)
    assert good.sale_price_ars == 1430 and pending.sale_price_ars == 1300
    assert pending.purchase_price_ars is None


def test_rounding_preference_change_conflicts_even_without_item_timestamp_change(client, tenant, db_session):
    from app.models.tenant_preference import TenantPreference
    item = _priced_item(db_session, tenant, round_sale_price=True)
    preview = _preview(client, tenant, _payload([item.id], {"operation_type": "set_sale_price", "sale_price_ars": "1430"})).json()["data"]
    prefs = db_session.scalar(select(TenantPreference).where(TenantPreference.tenant_id == tenant.id))
    prefs.money_rounding_increment = Decimal("25")
    db_session.commit()
    response = _confirm(client, tenant, preview["id"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "inventory_bulk_operation_conflict"
    db_session.refresh(item)
    assert item.sale_price_ars == 1300 and item.profit_margin_percentage == 30


def test_reversal_detects_cost_change_even_when_sale_did_not_change(client, tenant, db_session):
    item = _priced_item(db_session, tenant)
    preview = _preview(client, tenant, _payload([item.id])).json()["data"]
    assert _confirm(client, tenant, preview["id"]).status_code == 200
    item.purchase_price_ars = Decimal("900")
    db_session.commit()
    response = _reverse(client, tenant, preview["id"])
    assert response.status_code == 200
    assert response.json()["data"]["conflict_count"] == 1
    db_session.refresh(item)
    assert item.purchase_price_ars == 900 and item.sale_price_ars == 1430


def test_historical_fixed_price_snapshots_reverse_to_derived_price_without_rewriting_evidence(client, tenant, db_session):
    from app.models.inventory_bulk_operation import InventoryBulkOperationItem
    item = _priced_item(db_session, tenant)
    preview = _preview(client, tenant, _payload([item.id], {"operation_type": "set_sale_price", "sale_price_ars": "1500"})).json()["data"]
    assert _confirm(client, tenant, preview["id"]).status_code == 200
    row = db_session.scalar(select(InventoryBulkOperationItem).where(InventoryBulkOperationItem.operation_id == uuid.UUID(preview["id"])))
    old = {"value": "1300", "type": "decimal", "sale_price_is_manual": True}
    new = {"value": "1500", "type": "decimal"}
    row.old_value_json, row.new_value_json = old, new
    db_session.commit()
    assert _reverse(client, tenant, preview["id"]).status_code == 200
    db_session.refresh(item); db_session.refresh(row)
    assert item.sale_price_ars == 1300 and item.profit_margin_percentage == 30
    assert item.sale_price_is_manual is False
    assert row.old_value_json == old and row.new_value_json == new


def test_filtered_selection_uses_all_pages_status_exclusions_and_tenant(client, tenant, other_tenant, db_session):
    items = [_priced_item(db_session, tenant, name=f"Pendiente {i}", brand="A", category="food", purchase_price_ars=None, is_active=i % 2 == 0) for i in range(105)]
    foreign = _priced_item(db_session, other_tenant, brand="A", category="food", purchase_price_ars=None)
    _priced_item(db_session, tenant, brand="B", category="food", purchase_price_ars=None)
    _priced_item(db_session, tenant, brand="A", category="food")
    preview = _preview(client, tenant, _filtered_payload({"brand": "A", "category": "food", "status": "pricing_pending"}, excluded_ids=[items[0].id])).json()["data"]
    assert preview["affected_count"] == 104 and preview["excluded_count"] == 1
    assert len(preview["items"]) == 100
    page2 = client.get(f"/api/v1/inventory/bulk-operations/{preview['id']}?page=2", headers=_headers(tenant)).json()
    assert len(page2["data"]["items"]) == 4 and page2["meta"]["total"] == 104
    assert _confirm(client, tenant, preview["id"]).status_code == 200
    for item in items[1:]:
        db_session.refresh(item)
        assert item.brand == "Nueva" and item.purchase_price_ars is None
    db_session.refresh(items[0]); db_session.refresh(foreign)
    assert items[0].brand == "A" and foreign.brand == "A"
    assert _confirm(client, other_tenant, preview["id"]).status_code == 404
    assert _reverse(client, other_tenant, preview["id"]).status_code == 404


@pytest.mark.parametrize("operation", [
    {"operation_type": "set_profit_margin_percentage", "profit_margin_percentage": "30.001"},
    {"operation_type": "set_profit_margin_percentage", "profit_margin_percentage": "1000.01"},
    {"operation_type": "set_sale_price", "sale_price_ars": "1300.001"},
    {"operation_type": "set_supplier", "supplier": None},
    {"operation_type": "set_supplier", "supplier": "Otro", "supplier_id": str(uuid.uuid4())},
])
def test_bulk_payload_precision_limits_and_null_do_not_silently_change_inputs(client, tenant, db_session, operation):
    item = _priced_item(db_session, tenant)
    assert _preview(client, tenant, _payload([item.id], operation)).status_code == 422


@pytest.mark.parametrize(("operation", "field"), [
    ({"operation_type": "set_brand", "brand": "", "confirm_clear": True}, "brand"),
    ({"operation_type": "set_supplier", "supplier": "", "confirm_clear": True}, "supplier"),
])
def test_explicit_clear_preserves_pricing_and_can_be_reversed(client, tenant, db_session, operation, field):
    item = _priced_item(db_session, tenant, purchase_price_ars=None)
    original = getattr(item, field)
    preview = _preview(client, tenant, _payload([item.id], operation)).json()["data"]
    assert _confirm(client, tenant, preview["id"]).status_code == 200
    db_session.refresh(item)
    assert getattr(item, field) is None
    assert item.purchase_price_ars is None and item.sale_price_ars == 1300
    assert _reverse(client, tenant, preview["id"]).status_code == 200
    db_session.refresh(item)
    assert getattr(item, field) == original


@pytest.mark.parametrize(("action", "adjustment", "cost", "tax", "margin", "increment"), [
    ("increase_sale_price_percentage", "10", "1000", "21", "30", "50"),
    ("decrease_sale_price_percentage", "10", "1000", "21", "30", "50"),
    ("increase_sale_price_percentage", "0.01", "5000", "21", "35", "100"),
    ("decrease_sale_price_percentage", "0.01", "5000", "21", "35", "100"),
    ("increase_sale_price_percentage", "10", "1234.56", "0", "32.17", "0.01"),
])
def test_relative_adjustment_uses_nearest_calculated_rounded_price(client, tenant, db_session, action, adjustment, cost, tax, margin, increment):
    from app.core.inventory_pricing import calculate_catalog_sale_price
    from app.models.tenant_preference import TenantPreference
    prefs = TenantPreference(tenant_id=tenant.id, money_rounding_increment=Decimal(increment))
    db_session.add(prefs)
    db_session.commit()
    inputs = dict(purchase_price_ars=Decimal(cost), purchase_tax_rate_percentage=Decimal(tax), round_sale_price=True, rounding_increment=Decimal(increment))
    original_price = calculate_catalog_sale_price(**inputs, profit_margin_percentage=Decimal(margin))
    item = _priced_item(db_session, tenant, **{key: val for key, val in inputs.items() if key != "rounding_increment"}, profit_margin_percentage=Decimal(margin), sale_price_ars=original_price, sale_tax_rate_percentage="21")
    original = (item.purchase_price_ars, item.current_stock, item.purchase_tax_rate_percentage, item.sale_tax_rate_percentage, item.brand, item.supplier, item.minimum_stock)
    preview = _preview(client, tenant, _payload([item.id], {"operation_type": action, "percentage": adjustment})).json()["data"]
    assert preview["invalid_count"] == 0
    box = preview["items"][0]["new_value_json"]
    price = Decimal(box["value"]["sale_price_ars"])
    new_margin = Decimal(box["value"]["profit_margin_percentage"])
    target = (original_price * (1 + (1 if action.startswith("increase") else -1) * Decimal(adjustment) / 100)).quantize(Decimal("0.01"))
    assert Decimal(box["requested_sale_price_ars"]) == target
    assert Decimal(box["price_difference_ars"]) == price - target
    assert price == calculate_catalog_sale_price(**inputs, profit_margin_percentage=new_margin)
    assert price >= original_price if action.startswith("increase") else price <= original_price
    # Neighbour percentages cannot produce a closer allowed monetary result.
    for candidate in (new_margin - Decimal("0.01"), new_margin + Decimal("0.01")):
        if 0 <= candidate <= 1000:
            alternative = calculate_catalog_sale_price(**inputs, profit_margin_percentage=candidate)
            assert abs(price - target) <= abs(alternative - target)
    assert _confirm(client, tenant, preview["id"]).status_code == 200
    detail = client.get(f"/api/v1/inventory/items/{item.id}", headers=_headers(tenant)).json()["data"]
    assert Decimal(detail["sale_price_ars"]) == price and Decimal(detail["profit_margin_percentage"]) == new_margin
    db_session.refresh(item)
    assert (item.purchase_price_ars, item.current_stock, item.purchase_tax_rate_percentage, item.sale_tax_rate_percentage, item.brand, item.supplier, item.minimum_stock) == original
    assert item.sale_price_is_manual is False
    assert _confirm(client, tenant, preview["id"]).status_code == 409
    assert _reverse(client, tenant, preview["id"]).status_code == 200
    db_session.refresh(item)
    assert item.sale_price_ars == original_price and item.profit_margin_percentage == Decimal(margin)


def test_rounded_adjustment_distinguishes_percentage_change_from_no_change(client, tenant, db_session):
    from app.models.tenant_preference import TenantPreference
    db_session.add(TenantPreference(tenant_id=tenant.id, money_rounding_increment=Decimal("100")))
    item = _priced_item(db_session, tenant, round_sale_price=True)
    preview = _preview(client, tenant, _payload([item.id], {"operation_type": "increase_sale_price_percentage", "percentage": "1"})).json()["data"]
    assert preview["affected_count"] == 1 and preview["unchanged_count"] == 0
    box = preview["items"][0]["new_value_json"]
    assert box["sale_price_unchanged"] is True
    assert box["value"] == {"profit_margin_percentage": "31.30", "sale_price_ars": "1300.00"}
    zero = _priced_item(db_session, tenant, purchase_price_ars=Decimal("0"), sale_price_ars=Decimal("0"), round_sale_price=True)
    unchanged = _preview(client, tenant, _payload([zero.id])).json()["data"]
    assert unchanged["unchanged_count"] == 1 and unchanged["affected_count"] == 0


def test_bulk_supplier_uses_existing_record_preserves_other_fields_and_reverses(client, tenant, db_session):
    previous = _supplier(db_session, tenant, "Anterior")
    selected = _supplier(db_session, tenant, "Seleccionado")
    item = _priced_item(db_session, tenant, purchase_price_ars=None, supplier=previous.name, supplier_id=previous.id)
    for supplier_id, clear in [(selected.id, False), (None, True)]:
        operation = {"operation_type": "set_supplier", "supplier_id": str(supplier_id) if supplier_id else None, "confirm_clear": clear}
        preview = _preview(client, tenant, _payload([item.id], operation)).json()["data"]
        assert _confirm(client, tenant, preview["id"]).status_code == 200
        read = client.get(f"/api/v1/inventory/items/{item.id}", headers=_headers(tenant)).json()["data"]
        assert read["supplier_id"] == (str(supplier_id) if supplier_id else None)
        assert read["supplier"] == (selected.name if supplier_id else None)
        assert read["purchase_price_ars"] is None and read["sale_price_ars"] == "1300.00"
        assert read["current_stock"] == "5.00"
        assert _reverse(client, tenant, preview["id"]).status_code == 200
        db_session.refresh(item)
        assert item.supplier_id == previous.id and item.supplier == previous.name


def test_bulk_supplier_rejects_unknown_foreign_inactive_and_stale_records(client, tenant, other_tenant, db_session):
    item = _priced_item(db_session, tenant)
    foreign = _supplier(db_session, other_tenant)
    inactive = _supplier(db_session, tenant, "Inactivo", active=False)
    for supplier_id, status in [(uuid.uuid4(), 404), (foreign.id, 404), (inactive.id, 409)]:
        response = _preview(client, tenant, _payload([item.id], {"operation_type": "set_supplier", "supplier_id": str(supplier_id)}))
        assert response.status_code == status
    assert _preview(client, tenant, _payload([item.id], {"operation_type": "set_supplier", "supplier": "Texto arbitrario"})).status_code == 422
    selected = _supplier(db_session, tenant, "Vigente")
    preview = _preview(client, tenant, _payload([item.id], {"operation_type": "set_supplier", "supplier_id": str(selected.id)})).json()["data"]
    selected.is_active = False
    db_session.commit()
    assert _confirm(client, tenant, preview["id"]).status_code == 409
    db_session.refresh(item)
    assert item.supplier_id is None and item.supplier == "Proveedor"

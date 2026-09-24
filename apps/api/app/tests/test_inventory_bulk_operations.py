import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.inventory_bulk_operation import InventoryBulkOperation
from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.user import User
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
        sale_tax_rate_percentage=Decimal("0"),
        round_sale_price=False,
        is_active=overrides.pop("is_active", True),
        notes=overrides.pop("notes", None),
        **overrides,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


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
        ({"operation_type": "set_sale_price", "sale_price_ars": "0"}, "sale_price_ars", "0"),
        ({"operation_type": "set_minimum_stock", "minimum_stock": "4.5"}, "minimum_stock", "4.5"),
        ({"operation_type": "set_brand", "brand": "Nueva marca"}, "brand", "Nueva marca"),
        ({"operation_type": "set_supplier", "supplier": "Nuevo proveedor"}, "supplier", "Nuevo proveedor"),
        ({"operation_type": "activate"}, "is_active", True),
        ({"operation_type": "deactivate"}, "is_active", False),
    ],
)
def test_bulk_preview_calculates_supported_operations(client, tenant, db_session, operation, field, expected):
    item = _create_item(db_session, tenant, sale_price_ars=Decimal("100"), is_active=True)

    response = _preview(client, tenant, _payload([item.id], operation=operation))

    assert response.status_code == 201
    row = response.json()["data"]["items"][0]
    assert row["field_name"] == field
    assert row["new_value_json"]["value"] == expected


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

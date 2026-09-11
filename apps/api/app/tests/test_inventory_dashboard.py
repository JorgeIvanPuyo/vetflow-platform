import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.inventory_bulk_operation import InventoryBulkOperation
from app.models.inventory_import import InventoryImport
from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.user import User


def _headers(tenant) -> dict[str, str]:
    return {"X-Tenant-Id": str(tenant.id)}


def _create_user(db_session, tenant, email="dashboard@vetflow.local") -> User:
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=email,
        full_name="Dashboard User",
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
        unit=overrides.pop("unit", "unit"),
        current_stock=Decimal(str(overrides.pop("current_stock", "5"))),
        minimum_stock=Decimal(str(overrides.pop("minimum_stock", "2"))),
        purchase_price_ars=overrides.pop("purchase_price_ars", Decimal("100")),
        purchase_tax_rate_percentage=Decimal(str(overrides.pop("purchase_tax_rate_percentage", "21"))),
        profit_margin_percentage=Decimal(str(overrides.pop("profit_margin_percentage", "35"))),
        sale_price_ars=overrides.pop("sale_price_ars", Decimal("200")),
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


def _create_movement(db_session, tenant, item, **overrides) -> InventoryMovement:
    movement_data = {
        "id": uuid.uuid4(),
        "tenant_id": tenant.id,
        "inventory_item_id": item.id,
        "movement_type": overrides.pop("movement_type", "manual_entry"),
        "reason": overrides.pop("reason", "manual_entry"),
        "quantity": Decimal(str(overrides.pop("quantity", "1"))),
        "stock_before": Decimal(str(overrides.pop("stock_before", "0"))),
        "stock_after": Decimal(str(overrides.pop("stock_after", "1"))),
        "unit": item.unit,
        "source_type": overrides.pop("source_type", "manual"),
        "source_id": overrides.pop("source_id", None),
        "created_by_user_id": overrides.pop("created_by_user_id", None),
        **overrides,
    }
    created_at = movement_data.pop("created_at", None)
    if created_at is not None:
        movement_data["created_at"] = created_at
    movement = InventoryMovement(**movement_data)
    db_session.add(movement)
    db_session.commit()
    db_session.refresh(movement)
    return movement


def _create_import(db_session, tenant, user, **overrides) -> InventoryImport:
    import_data = {
        "id": uuid.uuid4(),
        "tenant_id": tenant.id,
        "created_by_user_id": user.id if user else None,
        "mode": overrides.pop("mode", "initial_load"),
        "status": overrides.pop("status", "confirmed"),
        "original_filename": overrides.pop("original_filename", "inventario.xlsx"),
        "file_hash": uuid.uuid4().hex,
        "row_count": overrides.pop("row_count", 3),
        "valid_count": overrides.pop("valid_count", 3),
        "warning_count": overrides.pop("warning_count", 0),
        "error_count": overrides.pop("error_count", 0),
        "expires_at": datetime.now(UTC) + timedelta(days=1),
        "confirmed_at": overrides.pop("confirmed_at", datetime.now(UTC)),
        **overrides,
    }
    created_at = import_data.pop("created_at", None)
    if created_at is not None:
        import_data["created_at"] = created_at
    inventory_import = InventoryImport(**import_data)
    db_session.add(inventory_import)
    db_session.commit()
    db_session.refresh(inventory_import)
    return inventory_import


def _create_bulk_operation(db_session, tenant, user, **overrides) -> InventoryBulkOperation:
    operation_data = {
        "id": uuid.uuid4(),
        "tenant_id": tenant.id,
        "created_by_user_id": user.id if user else None,
        "operation_type": overrides.pop("operation_type", "set_brand"),
        "selection_mode": overrides.pop("selection_mode", "selected"),
        "filters_json": overrides.pop("filters_json", None),
        "request_json": overrides.pop("request_json", {"operation": {"operation_type": "set_brand"}}),
        "status": overrides.pop("status", "confirmed"),
        "selected_count": overrides.pop("selected_count", 1),
        "affected_count": overrides.pop("affected_count", 1),
        "unchanged_count": overrides.pop("unchanged_count", 0),
        "invalid_count": overrides.pop("invalid_count", 0),
        "excluded_count": overrides.pop("excluded_count", 0),
        "reversed_count": overrides.pop("reversed_count", 0),
        "conflict_count": overrides.pop("conflict_count", 0),
        "expires_at": datetime.now(UTC) + timedelta(days=1),
        "confirmed_at": overrides.pop("confirmed_at", datetime.now(UTC)),
        **overrides,
    }
    created_at = operation_data.pop("created_at", None)
    if created_at is not None:
        operation_data["created_at"] = created_at
    operation = InventoryBulkOperation(**operation_data)
    db_session.add(operation)
    db_session.commit()
    db_session.refresh(operation)
    return operation


def _dashboard(client, tenant, query=""):
    return client.get(f"/api/v1/inventory/dashboard{query}", headers=_headers(tenant))


def test_inventory_dashboard_requires_tenant_context(client):
    response = client.get("/api/v1/inventory/dashboard")

    assert response.status_code == 400


def test_inventory_dashboard_is_tenant_aware(client, tenant, other_tenant, db_session):
    _create_item(db_session, tenant, name="Propio", current_stock="5")
    _create_item(db_session, other_tenant, name="Ajeno", current_stock="-9")

    response = _dashboard(client, tenant)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["indicators"]["total_products"] == 1
    assert data["indicators"]["negative_stock_products"] == 0
    assert "tenant_id" not in data


def test_inventory_dashboard_counts_stock_states_and_uses_minimum_stock(client, tenant, db_session):
    _create_item(db_session, tenant, name="Disponible", current_stock="10", minimum_stock="5", is_active=True)
    _create_item(db_session, tenant, name="Bajo", current_stock="3", minimum_stock="5", is_active=True)
    _create_item(db_session, tenant, name="Agotado", current_stock="0", minimum_stock="5", is_active=True)
    _create_item(db_session, tenant, name="Negativo", current_stock="-1", minimum_stock="5", is_active=False)

    response = _dashboard(client, tenant)

    assert response.status_code == 200
    indicators = response.json()["data"]["indicators"]
    assert indicators == {
        "total_products": 4,
        "active_products": 3,
        "inactive_products": 1,
        "in_stock_products": 1,
        "low_stock_products": 1,
        "out_of_stock_products": 1,
        "negative_stock_products": 1,
    }


def test_inventory_dashboard_filters_catalog_fields(client, tenant, db_session):
    _create_item(db_session, tenant, category="medication", brand=" Zoetis ", supplier="Central", is_active=True)
    _create_item(db_session, tenant, category="supply", brand="Otra", supplier="Central", is_active=True)
    _create_item(db_session, tenant, category="medication", brand="Zoetis", supplier="Sur", is_active=False)

    response = _dashboard(
        client,
        tenant,
        "?category=medication&brand=zoetis&supplier=central&is_active=true",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["filters"]["brand"] == "zoetis"
    assert data["indicators"]["total_products"] == 1
    assert data["indicators"]["active_products"] == 1


def test_inventory_dashboard_rejects_invalid_filters_and_date_ranges(client, tenant):
    assert _dashboard(client, tenant, "?category=invalid").status_code == 422
    assert _dashboard(client, tenant, "?date_from=2026-02-10&date_to=2026-02-01").status_code == 422
    assert _dashboard(client, tenant, "?date_from=2024-01-01&date_to=2026-01-01").status_code == 422


def test_inventory_dashboard_valuation_includes_purchase_tax_and_negative_stock(client, tenant, db_session):
    _create_item(
        db_session,
        tenant,
        current_stock="2",
        purchase_price_ars=Decimal("100"),
        purchase_tax_rate_percentage="21",
        sale_price_ars=Decimal("200"),
    )
    _create_item(
        db_session,
        tenant,
        current_stock="-1",
        purchase_price_ars=Decimal("50"),
        purchase_tax_rate_percentage="10",
        sale_price_ars=Decimal("80"),
    )
    _create_item(db_session, tenant, current_stock="5", purchase_price_ars=None, sale_price_ars=None)

    response = _dashboard(client, tenant)

    assert response.status_code == 200
    valuation = response.json()["data"]["valuation"]
    assert valuation["estimated_cost_value_ars"] == "187.00"
    assert valuation["estimated_sale_value_ars"] == "320.00"
    assert valuation["includes_negative_stock"] is True
    assert "contable" in valuation["disclaimer"]


def test_inventory_dashboard_alerts_priorities_and_attention_limit(client, tenant, db_session):
    _create_item(db_session, tenant, name="Negativo", current_stock="-1")
    _create_item(db_session, tenant, name="Agotado", current_stock="0")
    _create_item(db_session, tenant, name="Bajo", current_stock="1", minimum_stock="3")
    _create_item(db_session, tenant, name="Inactivo con stock", current_stock="4", is_active=False)
    _create_item(db_session, tenant, name="Sin costo", purchase_price_ars=None)
    _create_item(db_session, tenant, name="Sin precio", sale_price_ars=None)
    _create_item(db_session, tenant, name="Sin marca", brand="")
    _create_item(db_session, tenant, name="Sin proveedor", supplier="")
    for index in range(12):
        _create_item(db_session, tenant, name=f"Falta {index}", brand="")

    response = _dashboard(client, tenant)

    assert response.status_code == 200
    data = response.json()["data"]
    alerts = {alert["alert_type"]: alert for alert in data["alerts"]}
    assert alerts["negative_stock"]["priority"] == "critical"
    assert alerts["out_of_stock"]["priority"] == "high"
    assert alerts["missing_purchase_cost"]["priority"] == "high"
    assert alerts["missing_sale_price"]["priority"] == "high"
    assert alerts["low_stock"]["priority"] == "medium"
    assert alerts["inactive_with_stock"]["priority"] == "medium"
    assert alerts["missing_brand"]["priority"] == "info"
    assert alerts["missing_supplier"]["priority"] == "info"
    assert len(data["attention_items"]) == 10
    assert data["attention_items"][0]["priority"] == "critical"


def test_inventory_dashboard_recent_activity_and_date_range_are_tenant_scoped(client, tenant, other_tenant, db_session):
    user = _create_user(db_session, tenant)
    other_user = _create_user(db_session, other_tenant, email="other-dashboard@vetflow.local")
    item = _create_item(db_session, tenant)
    other_item = _create_item(db_session, other_tenant)
    inside = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
    outside = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

    _create_movement(db_session, tenant, item, movement_type="manual_entry", created_by_user_id=user.id, created_at=inside)
    _create_movement(db_session, tenant, item, movement_type="manual_exit", created_by_user_id=user.id, created_at=inside + timedelta(minutes=1))
    _create_movement(db_session, tenant, item, movement_type="adjustment_in", created_at=inside + timedelta(minutes=2))
    _create_movement(db_session, tenant, item, movement_type="reversal", created_at=inside + timedelta(minutes=3))
    _create_movement(db_session, tenant, item, movement_type="clinical_consumption", created_at=inside + timedelta(minutes=4))
    _create_movement(db_session, tenant, item, movement_type="manual_entry", created_at=outside)
    _create_movement(db_session, other_tenant, other_item, movement_type="manual_entry", created_by_user_id=other_user.id, created_at=inside)
    _create_import(db_session, tenant, user, created_at=inside)
    _create_import(db_session, tenant, user, created_at=outside, original_filename="viejo.xlsx")
    _create_import(db_session, other_tenant, other_user, created_at=inside, original_filename="ajeno.xlsx")
    _create_bulk_operation(db_session, tenant, user, created_at=inside)
    _create_bulk_operation(db_session, other_tenant, other_user, created_at=inside)

    response = _dashboard(client, tenant, "?date_from=2026-08-03&date_to=2026-08-03")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["movement_metrics"] == {
        "total_movements": 5,
        "entry_movements": 2,
        "exit_movements": 2,
        "adjustment_movements": 1,
        "reversal_movements": 1,
        "clinical_consumption_movements": 1,
    }
    assert len(data["activity"]["recent_movements"]) == 5
    assert data["activity"]["recent_movements"][0]["created_by_user_name"] is None
    assert data["activity"]["recent_movements"][-1]["created_by_user_name"] == "Dashboard User"
    assert len(data["activity"]["recent_imports"]) == 1
    assert data["activity"]["recent_imports"][0]["original_filename"] == "inventario.xlsx"
    assert len(data["activity"]["recent_bulk_operations"]) == 1


def test_inventory_dashboard_empty_state(client, tenant):
    response = _dashboard(client, tenant)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["indicators"]["total_products"] == 0
    assert data["valuation"]["estimated_cost_value_ars"] == "0.00"
    assert data["attention_items"] == []
    assert data["activity"]["recent_movements"] == []

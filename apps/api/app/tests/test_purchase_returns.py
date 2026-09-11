import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.purchase import Purchase
from app.models.purchase_return import PurchaseReturn, PurchaseReturnAttachment
from app.models.user import User
from app.services.storage import get_purchase_attachment_storage_service


PDF = b"%PDF-1.7\npurchase return document"
PNG = b"\x89PNG\r\n\x1a\npurchase return image"


class FakeStorage:
    bucket_name = "purchase-return-test-bucket"

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def upload_clinical_file(self, *, object_path, content, content_type) -> None:
        del content_type
        self.objects[object_path] = content

    def delete_clinical_file(self, *, bucket_name, object_path) -> None:
        assert bucket_name == self.bucket_name
        self.objects.pop(object_path, None)

    def download_object_bytes(self, *, bucket_name, object_path) -> bytes:
        assert bucket_name == self.bucket_name
        return self.objects[object_path]


pytestmark = pytest.mark.usefixtures("allow_supplier_mutations")
def _headers(tenant) -> dict[str, str]:
    return {"X-Tenant-Id": str(tenant.id)}


def _auth_headers(email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {email}"}


def _setup_auth(monkeypatch) -> None:
    import app.core.tenant as tenant_core

    monkeypatch.setattr(tenant_core, "verify_id_token", lambda token: {"email": token})


def _create_user(db_session, tenant, email="returns@example.com") -> User:
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=email,
        full_name="Responsable de devoluciones",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_item(
    client,
    tenant,
    *,
    name="Producto retornable",
    purchase_price="25.00",
    sale_price="100.00",
) -> dict:
    response = client.post(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        json={
            "name": name,
            "category": "supply",
            "unit": "box",
            "purchase_price_ars": purchase_price,
            "purchase_tax_rate_percentage": "10.00",
            "profit_margin_percentage": "40.00",
            "sale_price_ars": sale_price,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _create_supplier(client, tenant, name="Proveedor devoluciones") -> dict:
    response = client.post(
        "/api/v1/suppliers",
        headers=_headers(tenant),
        json={"name": f"{name} {uuid.uuid4().hex[:8]}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _create_purchase(
    client,
    tenant,
    lines,
    *,
    receive=True,
    headers=None,
) -> dict:
    supplier = _create_supplier(client, tenant)
    response = client.post(
        "/api/v1/purchases",
        headers=headers or _headers(tenant),
        json={
            "supplier_id": supplier["id"],
            "purchase_date": "2026-08-09",
            "document_type": "invoice",
            "document_number": "FAC-RETURN",
            "items": [
                {
                    "inventory_item_id": item["id"],
                    "quantity": quantity,
                    "unit_price_without_tax_ars": price,
                    "tax_rate_percentage": tax,
                }
                for item, quantity, price, tax in lines
            ],
        },
    )
    assert response.status_code == 201, response.text
    purchase = response.json()["data"]
    if receive:
        received = client.post(
            f"/api/v1/purchases/{purchase['id']}/receive",
            headers=headers or _headers(tenant),
            json={"confirm": True},
        )
        assert received.status_code == 200, received.text
        purchase = received.json()["data"]
    return purchase


def _return_payload(purchase, quantities, **overrides) -> dict:
    payload = {
        "return_date": "2026-08-09",
        "reason": "Productos vencidos",
        "document_type": "credit_note",
        "document_number": "NC-0001",
        "items": [
            {"purchase_item_id": purchase["items"][index]["id"], "quantity": quantity}
            for index, quantity in quantities
        ],
    }
    payload.update(overrides)
    return payload


def _create_return(client, tenant, purchase, quantities, *, headers=None, **overrides):
    return client.post(
        f"/api/v1/purchases/{purchase['id']}/returns",
        headers=headers or _headers(tenant),
        json=_return_payload(purchase, quantities, **overrides),
    )


def _confirm(client, tenant, return_id, *, headers=None):
    return client.post(
        f"/api/v1/purchase-returns/{return_id}/confirm",
        headers=headers or _headers(tenant),
        json={"confirm": True},
    )


def _storage(client) -> FakeStorage:
    storage = FakeStorage()
    client.app.dependency_overrides[get_purchase_attachment_storage_service] = (
        lambda: storage
    )
    return storage


def test_purchase_return_requires_authentication(client, tenant, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()

    response = client.get("/api/v1/purchase-returns")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_auth_token"


def test_create_draft_uses_historical_snapshots_totals_user_and_no_stock(
    client, db_session, tenant, monkeypatch
):
    _setup_auth(monkeypatch)
    user = _create_user(db_session, tenant)
    item = _create_item(client, tenant, name="Vacuna histórica")
    purchase = _create_purchase(
        client,
        tenant,
        [(item, "10", "100.00", "21.00")],
        headers=_auth_headers(user.email),
    )
    stock_before = db_session.get(InventoryItem, uuid.UUID(item["id"])).current_stock

    response = _create_return(
        client,
        tenant,
        purchase,
        [(0, "2")],
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["status"] == "draft"
    assert data["supplier_name"] == purchase["supplier_name"]
    assert data["created_by_user_id"] == str(user.id)
    assert data["subtotal_ars"] == "200.00"
    assert data["tax_total_ars"] == "42.00"
    assert data["total_ars"] == "242.00"
    assert data["attachment_status"] == "pending"
    assert data["items"][0]["description_snapshot"] == "Vacuna histórica"
    assert data["items"][0]["internal_code_snapshot"] == item["internal_code"]
    assert data["items"][0]["unit_price_without_tax_ars"] == "100.00"
    db_session.expire_all()
    assert db_session.get(InventoryItem, uuid.UUID(item["id"])).current_stock == stock_before
    assert (
        db_session.scalar(
            select(func.count()).select_from(InventoryMovement).where(
                InventoryMovement.movement_type == "purchase_return"
            )
        )
        == 0
    )


@pytest.mark.parametrize("quantity", ["0", "-1", "1.5"])
def test_create_rejects_non_positive_or_fractional_quantity(
    client, tenant, quantity
):
    item = _create_item(client, tenant)
    purchase = _create_purchase(client, tenant, [(item, "2", "10", "21")])

    response = _create_return(client, tenant, purchase, [(0, quantity)])

    assert response.status_code == 422


def test_only_received_purchase_and_own_purchase_items_are_eligible(
    client, db_session, tenant, other_tenant
):
    item = _create_item(client, tenant, name="Compra uno")
    draft = _create_purchase(client, tenant, [(item, "2", "10", "21")], receive=False)
    other_item = _create_item(client, tenant, name="Compra dos")
    other_purchase = _create_purchase(
        client, tenant, [(other_item, "2", "10", "21")]
    )
    received = _create_purchase(client, tenant, [(item, "2", "10", "21")])
    foreign_item = _create_item(client, other_tenant, name="Ajeno")
    foreign = _create_purchase(
        client, other_tenant, [(foreign_item, "2", "10", "21")]
    )
    cancelled = _create_purchase(
        client,
        tenant,
        [(_create_item(client, tenant, name="Cancelada"), "1", "10", "21")],
        receive=False,
    )
    client.post(
        f"/api/v1/purchases/{cancelled['id']}/cancel",
        headers=_headers(tenant),
        json={"reason": "Cancelada"},
    )
    received_model = db_session.get(Purchase, uuid.UUID(received["id"]))
    received_model.status = "reversed"
    db_session.commit()

    draft_response = _create_return(client, tenant, draft, [(0, "1")])
    cancelled_response = _create_return(client, tenant, cancelled, [(0, "1")])
    reversed_response = _create_return(client, tenant, received, [(0, "1")])
    wrong_line = client.post(
        f"/api/v1/purchases/{other_purchase['id']}/returns",
        headers=_headers(tenant),
        json=_return_payload(
            other_purchase,
            [(0, "1")],
            items=[
                {
                    "purchase_item_id": draft["items"][0]["id"],
                    "quantity": "1",
                }
            ],
        ),
    )
    cross_tenant = _create_return(client, tenant, foreign, [(0, "1")])

    assert draft_response.status_code == 409
    assert cancelled_response.status_code == 409
    assert reversed_response.status_code == 409
    assert wrong_line.status_code == 404
    assert cross_tenant.status_code == 404


def test_confirm_partial_return_creates_traceable_movements_and_preserves_prices(
    client, db_session, tenant, monkeypatch
):
    _setup_auth(monkeypatch)
    user = _create_user(db_session, tenant)
    item = _create_item(
        client,
        tenant,
        purchase_price="25.00",
        sale_price="100.00",
    )
    purchase = _create_purchase(
        client,
        tenant,
        [(item, "10", "50", "21")],
        headers=_auth_headers(user.email),
    )
    created = _create_return(
        client,
        tenant,
        purchase,
        [(0, "3")],
        headers=_auth_headers(user.email),
    ).json()["data"]

    response = _confirm(
        client, tenant, created["id"], headers=_auth_headers(user.email)
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "confirmed"
    assert data["confirmed_at"] is not None
    assert data["confirmed_by_user_id"] == str(user.id)
    assert data["inventory_operation_id"] is not None
    db_session.expire_all()
    inventory_item = db_session.get(InventoryItem, uuid.UUID(item["id"]))
    assert inventory_item.current_stock == Decimal("7.00")
    assert inventory_item.purchase_price_ars == Decimal("50.00")
    assert inventory_item.purchase_tax_rate_percentage == Decimal("21.00")
    assert inventory_item.sale_price_ars == Decimal("100.00")
    assert inventory_item.profit_margin_percentage == Decimal("40.00")
    movement = db_session.scalar(
        select(InventoryMovement).where(
            InventoryMovement.movement_type == "purchase_return"
        )
    )
    assert movement.quantity == Decimal("3.00")
    assert movement.stock_before == Decimal("10.00")
    assert movement.stock_after == Decimal("7.00")
    assert movement.operation_id == uuid.UUID(data["inventory_operation_id"])
    assert movement.source_type == "purchase_return"
    assert movement.source_id == data["id"]
    assert movement.created_by_user_id == user.id
    detail = client.get(
        f"/api/v1/purchases/{purchase['id']}", headers=_headers(tenant)
    ).json()["data"]
    assert detail["status"] == "received"
    assert detail["return_status"] == "partial"
    assert detail["confirmed_return_count"] == 1
    assert detail["returned_total_ars"] == "181.50"
    assert detail["items"][0]["confirmed_returned_quantity"] == "3.00"
    assert detail["items"][0]["returnable_quantity"] == "7.00"


def test_multiple_returns_use_confirmed_balance_and_derive_full_status(
    client, tenant
):
    item = _create_item(client, tenant)
    purchase = _create_purchase(client, tenant, [(item, "10", "10", "0")])
    first = _create_return(client, tenant, purchase, [(0, "3")]).json()["data"]
    assert _confirm(client, tenant, first["id"]).status_code == 200
    reverse = client.post(
        f"/api/v1/purchases/{purchase['id']}/reverse-receipt",
        headers=_headers(tenant),
        json={"reason": "No corresponde después de una devolución"},
    )
    assert reverse.status_code == 409
    assert reverse.json()["error"]["code"] == "purchase_receipt_has_confirmed_returns"
    draft = _create_return(client, tenant, purchase, [(0, "7")]).json()["data"]
    competing = _create_return(client, tenant, purchase, [(0, "7")]).json()["data"]
    cancelled = client.post(
        f"/api/v1/purchase-returns/{draft['id']}/cancel",
        headers=_headers(tenant),
        json={"reason": "No se enviará"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert _confirm(client, tenant, competing["id"]).status_code == 200
    over = _create_return(client, tenant, purchase, [(0, "1")])

    assert over.status_code == 409
    detail = client.get(
        f"/api/v1/purchases/{purchase['id']}", headers=_headers(tenant)
    ).json()["data"]
    assert detail["return_status"] == "full"
    assert detail["can_register_return"] is False
    assert detail["items"][0]["returnable_quantity"] == "0.00"


def test_competing_drafts_are_recalculated_on_confirm_and_double_confirm_rejected(
    client, db_session, tenant
):
    item = _create_item(client, tenant)
    purchase = _create_purchase(client, tenant, [(item, "5", "10", "0")])
    first = _create_return(client, tenant, purchase, [(0, "4")]).json()["data"]
    second = _create_return(client, tenant, purchase, [(0, "4")]).json()["data"]

    first_confirm = _confirm(client, tenant, first["id"])
    second_confirm = _confirm(client, tenant, second["id"])
    duplicate = _confirm(client, tenant, first["id"])

    assert first_confirm.status_code == 200
    assert second_confirm.status_code == 409
    assert second_confirm.json()["error"]["code"] == "purchase_return_quantity_exceeded"
    assert duplicate.status_code == 409
    db_session.expire_all()
    assert db_session.get(InventoryItem, uuid.UUID(item["id"])).current_stock == Decimal("1")


def test_stock_conflict_and_line_failure_roll_back_entire_confirmation(
    client, db_session, tenant, monkeypatch
):
    first_item = _create_item(client, tenant, name="Primero")
    second_item = _create_item(client, tenant, name="Segundo")
    purchase = _create_purchase(
        client,
        tenant,
        [(first_item, "4", "10", "0"), (second_item, "3", "20", "0")],
    )
    created = _create_return(
        client, tenant, purchase, [(0, "2"), (1, "2")]
    ).json()["data"]
    second_model = db_session.get(InventoryItem, uuid.UUID(second_item["id"]))
    second_model.current_stock = Decimal("1")
    db_session.commit()

    insufficient = _confirm(client, tenant, created["id"])

    assert insufficient.status_code == 409
    assert insufficient.json()["error"]["code"] == "purchase_return_insufficient_stock"
    db_session.expire_all()
    assert db_session.get(InventoryItem, uuid.UUID(first_item["id"])).current_stock == Decimal("4")
    assert db_session.get(PurchaseReturn, uuid.UUID(created["id"])).status == "draft"

    second_model = db_session.get(InventoryItem, uuid.UUID(second_item["id"]))
    second_model.current_stock = Decimal("3")
    db_session.commit()
    from app.services.inventory import InventoryService

    original = InventoryService.register_purchase_return_movement
    calls = 0

    def fail_second(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated return movement failure")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(
        InventoryService, "register_purchase_return_movement", fail_second
    )
    with pytest.raises(RuntimeError, match="simulated return movement failure"):
        _confirm(client, tenant, created["id"])

    db_session.expire_all()
    assert db_session.get(InventoryItem, uuid.UUID(first_item["id"])).current_stock == Decimal("4")
    assert db_session.get(InventoryItem, uuid.UUID(second_item["id"])).current_stock == Decimal("3")
    assert db_session.get(PurchaseReturn, uuid.UUID(created["id"])).status == "draft"
    assert (
        db_session.scalar(
            select(func.count()).select_from(InventoryMovement).where(
                InventoryMovement.movement_type == "purchase_return"
            )
        )
        == 0
    )


def test_update_cancel_and_confirmed_immutability(client, db_session, tenant):
    item = _create_item(client, tenant)
    purchase = _create_purchase(client, tenant, [(item, "5", "10", "21")])
    created = _create_return(client, tenant, purchase, [(0, "1")]).json()["data"]
    stock_before = db_session.get(InventoryItem, uuid.UUID(item["id"])).current_stock

    updated = client.patch(
        f"/api/v1/purchase-returns/{created['id']}",
        headers=_headers(tenant),
        json={"reason": "Motivo corregido", "items": [{"purchase_item_id": purchase["items"][0]["id"], "quantity": "2"}]},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["reason"] == "Motivo corregido"
    assert updated.json()["data"]["total_ars"] == "24.20"
    cancelled = client.post(
        f"/api/v1/purchase-returns/{created['id']}/cancel",
        headers=_headers(tenant),
        json={"reason": "Duplicada"},
    )
    assert cancelled.status_code == 200
    db_session.expire_all()
    assert db_session.get(InventoryItem, uuid.UUID(item["id"])).current_stock == stock_before
    assert _confirm(client, tenant, created["id"]).status_code == 409

    confirmed = _create_return(client, tenant, purchase, [(0, "1")]).json()["data"]
    assert _confirm(client, tenant, confirmed["id"]).status_code == 200
    edit_confirmed = client.patch(
        f"/api/v1/purchase-returns/{confirmed['id']}",
        headers=_headers(tenant),
        json={"reason": "No permitido"},
    )
    cancel_confirmed = client.post(
        f"/api/v1/purchase-returns/{confirmed['id']}/cancel",
        headers=_headers(tenant),
        json={"reason": "No permitido"},
    )
    assert edit_confirmed.status_code == 409
    assert cancel_confirmed.status_code == 409


def test_return_attachment_upload_replace_download_tenant_and_stock_isolation(
    client, db_session, tenant, other_tenant
):
    storage = _storage(client)
    item = _create_item(client, tenant)
    purchase = _create_purchase(client, tenant, [(item, "2", "10", "21")])
    created = _create_return(client, tenant, purchase, [(0, "1")]).json()["data"]
    stock_before = db_session.get(InventoryItem, uuid.UUID(item["id"])).current_stock

    first = client.post(
        f"/api/v1/purchase-returns/{created['id']}/attachment",
        headers=_headers(tenant),
        files={"file": ("nota.pdf", PDF, "application/pdf")},
    )
    replacement = client.post(
        f"/api/v1/purchase-returns/{created['id']}/attachment",
        headers=_headers(tenant),
        files={"file": ("reemplazo.png", PNG, "image/png")},
    )
    inline = client.get(
        f"/api/v1/purchase-returns/{created['id']}/attachment",
        headers=_headers(tenant),
    )
    cross = client.get(
        f"/api/v1/purchase-returns/{created['id']}/attachment",
        headers=_headers(other_tenant),
    )

    assert first.status_code == 200, first.text
    assert replacement.status_code == 200, replacement.text
    assert inline.status_code == 200
    assert inline.content == PNG
    assert cross.status_code == 404
    detail = client.get(
        f"/api/v1/purchase-returns/{created['id']}", headers=_headers(tenant)
    ).json()["data"]
    assert detail["attachment_status"] == "attached"
    assert detail["attachment"]["original_filename"] == "reemplazo.png"
    assert len(detail["attachment_history"]) == 1
    row = db_session.get(
        PurchaseReturnAttachment, uuid.UUID(replacement.json()["data"]["id"])
    )
    assert row.storage_key.startswith(
        f"tenants/{tenant.id}/purchase-returns/{created['id']}/attachments/"
    )
    assert storage.objects[row.storage_key] == PNG
    db_session.expire_all()
    assert db_session.get(InventoryItem, uuid.UUID(item["id"])).current_stock == stock_before


def test_return_list_and_dashboard_are_tenant_scoped_and_net_received(
    client, tenant, other_tenant
):
    own_item = _create_item(client, tenant, name="Propio")
    own_purchase = _create_purchase(
        client, tenant, [(own_item, "5", "100", "0")]
    )
    own_return = _create_return(
        client, tenant, own_purchase, [(0, "2")]
    ).json()["data"]
    assert _confirm(client, tenant, own_return["id"]).status_code == 200

    foreign_item = _create_item(client, other_tenant, name="Ajeno")
    foreign_purchase = _create_purchase(
        client, other_tenant, [(foreign_item, "5", "999", "0")]
    )
    foreign_return = _create_return(
        client, other_tenant, foreign_purchase, [(0, "5")]
    ).json()["data"]
    assert _confirm(client, other_tenant, foreign_return["id"]).status_code == 200

    listing = client.get(
        "/api/v1/purchase-returns",
        headers=_headers(tenant),
        params={
            "purchase_id": own_purchase["id"],
            "status": "confirmed",
            "attachment_status": "pending",
        },
    )
    dashboard = client.get(
        "/api/v1/purchases/dashboard",
        headers=_headers(tenant),
        params={"date_from": "2026-08-01", "date_to": "2026-08-31"},
    )

    assert listing.status_code == 200
    assert [row["id"] for row in listing.json()["data"]] == [own_return["id"]]
    assert listing.json()["meta"]["total"] == 1
    summary = dashboard.json()["data"]["summary"]
    assert summary["received_total_ars"] == "500.00"
    assert summary["returned_total_ars"] == "200.00"
    assert summary["net_received_total_ars"] == "300.00"
    assert summary["confirmed_return_count"] == 1
    assert foreign_return["id"] not in listing.text


def test_purchase_return_movement_cannot_use_generic_reversal(
    client, db_session, tenant
):
    item = _create_item(client, tenant)
    purchase = _create_purchase(client, tenant, [(item, "2", "10", "0")])
    created = _create_return(client, tenant, purchase, [(0, "1")]).json()["data"]
    _confirm(client, tenant, created["id"])
    movement = db_session.scalar(
        select(InventoryMovement).where(
            InventoryMovement.movement_type == "purchase_return"
        )
    )

    response = client.post(
        f"/api/v1/inventory/movements/{movement.id}/reverse",
        headers=_headers(tenant),
        json={"reason": "No permitido"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "purchase_return_movement_not_reversible"

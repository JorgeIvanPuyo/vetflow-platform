import uuid

import pytest

from app.core.config import get_settings


def _headers(tenant):
    return {"X-Tenant-Id": str(tenant.id)}


def _create(client, tenant, **overrides):
    payload = {"label": "Efectivo", "type": "cash", "is_active": True, "sort_order": 10, **overrides}
    return client.post("/api/v1/payment-methods", headers=_headers(tenant), json=payload)


def test_payment_methods_require_authentication(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    assert client.get("/api/v1/payment-methods").status_code == 401
    assert client.post("/api/v1/payment-methods", json={}).status_code == 401


@pytest.mark.parametrize("method_type", ["cash", "bank_transfer", "debit_card", "credit_card", "digital_wallet", "other"])
def test_create_all_stable_types_and_server_owned_fields(client, tenant, method_type):
    response = _create(client, tenant, label=f"Método {method_type}", type=method_type)
    assert response.status_code == 201, response.text
    assert response.json()["data"]["type"] == method_type
    rejected = client.post("/api/v1/payment-methods", headers=_headers(tenant), json={"label": "X", "type": method_type, "tenant_id": str(tenant.id)})
    assert rejected.status_code == 422


def test_active_label_is_trimmed_case_insensitive_and_tenant_scoped(client, tenant, other_tenant):
    assert _create(client, tenant, label="  Tarjeta Visa  ", type="credit_card").status_code == 201
    duplicate = _create(client, tenant, label="tarjeta   visa", type="debit_card")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "payment_method_label_duplicate"
    assert _create(client, other_tenant, label="TARJETA VISA", type="other").status_code == 201


def test_inactive_duplicates_allowed_but_reactivation_is_guarded(client, tenant):
    first = _create(client, tenant, label="Transferencia", type="bank_transfer").json()["data"]
    assert client.patch(f"/api/v1/payment-methods/{first['id']}", headers=_headers(tenant), json={"is_active": False}).status_code == 200
    second = _create(client, tenant, label="transferencia", type="other").json()["data"]
    response = client.patch(f"/api/v1/payment-methods/{first['id']}", headers=_headers(tenant), json={"is_active": True})
    assert response.status_code == 409
    assert client.patch(f"/api/v1/payment-methods/{second['id']}", headers=_headers(tenant), json={"label": "Otro nombre"}).status_code == 200


def test_list_filters_order_search_usage_and_cross_tenant_detail(client, tenant, other_tenant):
    later = _create(client, tenant, label="Billetera", type="digital_wallet", sort_order=20).json()["data"]
    first = _create(client, tenant, label="Banco", type="bank_transfer", sort_order=1).json()["data"]
    _create(client, other_tenant, label="Ajeno", type="cash")
    listed = client.get("/api/v1/payment-methods", headers=_headers(tenant)).json()["data"]
    assert [item["id"] for item in listed] == [first["id"], later["id"]]
    filtered = client.get("/api/v1/payment-methods?active=true&type=bank_transfer&search=ban", headers=_headers(tenant)).json()["data"]
    assert [item["id"] for item in filtered] == [first["id"]]
    assert filtered[0]["has_payments"] is False
    assert client.get(f"/api/v1/payment-methods/{first['id']}", headers=_headers(other_tenant)).status_code == 404


def test_update_rejects_null_and_invalid_type(client, tenant):
    method = _create(client, tenant).json()["data"]
    assert client.patch(f"/api/v1/payment-methods/{method['id']}", headers=_headers(tenant), json={"label": None}).status_code == 422
    assert client.patch(f"/api/v1/payment-methods/{method['id']}", headers=_headers(tenant), json={"type": "crypto"}).status_code == 422

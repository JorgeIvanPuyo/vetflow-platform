import uuid

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models.supplier import Supplier
from app.models.user import User


def _headers(tenant) -> dict[str, str]:
    return {"X-Tenant-Id": str(tenant.id)}


def _auth_headers(email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {email}"}


def _setup_auth(monkeypatch) -> None:
    import app.core.tenant as tenant_core

    monkeypatch.setattr(tenant_core, "verify_id_token", lambda token: {"email": token})


def _create_user(db_session, tenant, email="buyer@example.com") -> User:
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=email,
        full_name="Comprador",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_supplier(client, tenant, **overrides):
    payload = {
        "name": "Laboratorio Norte",
        "tax_id": "30-12345678-9",
        "phone": "+54 11 1234 5678",
        "email": "ventas@laboratorio.test",
        "address": "Calle 123",
        "notes": "Entrega semanal",
    }
    payload.update(overrides)
    response = client.post("/api/v1/suppliers", headers=_headers(tenant), json=payload)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_supplier_requires_authentication(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()

    response = client.get("/api/v1/suppliers")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_auth_token"


def test_create_normalizes_fields_and_records_creator(
    client, db_session, tenant, monkeypatch
):
    _setup_auth(monkeypatch)
    user = _create_user(db_session, tenant)

    response = client.post(
        "/api/v1/suppliers",
        headers=_auth_headers(user.email),
        json={
            "name": "  Clínica   Álamo  ",
            "tax_id": "  30-123  456  ",
            "email": "  contacto@alamo.test  ",
            "phone": "  +54   11  ",
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "Clínica Álamo"
    assert data["tax_id"] == "30-123 456"
    assert data["phone"] == "+54 11"
    assert data["created_by_user_id"] == str(user.id)
    assert data["created_by_user_name"] == "Comprador"
    supplier = db_session.scalar(select(Supplier).where(Supplier.id == uuid.UUID(data["id"])))
    assert supplier.normalized_name == "clínica álamo"


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"name": "   "}, "name"),
        ({"name": "Válido", "email": "correo-invalido"}, "email"),
        ({"name": "Válido", "normalized_name": "ataque"}, "normalized_name"),
        ({"name": "Válido", "tenant_id": "00000000-0000-0000-0000-000000000001"}, "tenant_id"),
        ({"name": "Válido", "is_active": False}, "is_active"),
    ],
)
def test_create_rejects_invalid_or_server_owned_fields(client, tenant, payload, field):
    response = client.post("/api/v1/suppliers", headers=_headers(tenant), json=payload)

    assert response.status_code == 422, field
    assert response.json()["error"]["code"] == "validation_error"


def test_name_and_tax_id_are_unique_per_tenant(client, tenant, other_tenant):
    first = _create_supplier(client, tenant)

    same_name = client.post(
        "/api/v1/suppliers",
        headers=_headers(tenant),
        json={"name": "  LABORATORIO   NORTE ", "tax_id": "otro"},
    )
    same_tax = client.post(
        "/api/v1/suppliers",
        headers=_headers(tenant),
        json={"name": "Otro", "tax_id": "  30-12345678-9  "},
    )
    other = _create_supplier(client, other_tenant)

    assert same_name.status_code == 409
    assert same_name.json()["error"]["code"] == "supplier_name_conflict"
    assert same_tax.status_code == 409
    assert same_tax.json()["error"]["code"] == "supplier_tax_id_conflict"
    assert first["name"] == other["name"]


def test_multiple_null_tax_ids_are_allowed(client, tenant):
    first = _create_supplier(client, tenant, name="Proveedor A", tax_id=None)
    second = _create_supplier(client, tenant, name="Proveedor B", tax_id=None)

    assert first["tax_id"] is None
    assert second["tax_id"] is None


def test_list_defaults_active_and_supports_search_status_sort_and_pagination(client, tenant):
    zeta = _create_supplier(client, tenant, name="Zeta", tax_id="20-Z")
    alpha = _create_supplier(client, tenant, name="Alpha", tax_id="20-A")
    inactive = _create_supplier(client, tenant, name="Dormido", tax_id="20-D")
    client.patch(
        f"/api/v1/suppliers/{inactive['id']}",
        headers=_headers(tenant),
        json={"is_active": False},
    )

    default = client.get(
        "/api/v1/suppliers",
        headers=_headers(tenant),
        params={"page_size": 1, "sort_by": "name", "sort_direction": "asc"},
    )
    search = client.get(
        "/api/v1/suppliers", headers=_headers(tenant), params={"search": "20-Z"}
    )
    inactive_list = client.get(
        "/api/v1/suppliers", headers=_headers(tenant), params={"is_active": False}
    )

    assert default.json()["data"][0]["id"] == alpha["id"]
    assert default.json()["meta"] == {
        "page": 1,
        "page_size": 1,
        "total": 2,
        "total_pages": 2,
    }
    assert [row["id"] for row in search.json()["data"]] == [zeta["id"]]
    assert [row["id"] for row in inactive_list.json()["data"]] == [inactive["id"]]


def test_detail_update_activation_and_no_delete(client, tenant):
    supplier = _create_supplier(client, tenant)
    update = client.patch(
        f"/api/v1/suppliers/{supplier['id']}",
        headers=_headers(tenant),
        json={"name": "Laboratorio Centro", "email": None, "is_active": False},
    )
    detail = client.get(
        f"/api/v1/suppliers/{supplier['id']}", headers=_headers(tenant)
    )
    delete = client.delete(
        f"/api/v1/suppliers/{supplier['id']}", headers=_headers(tenant)
    )

    assert update.status_code == 200
    assert update.json()["data"]["is_active"] is False
    assert detail.json()["data"]["name"] == "Laboratorio Centro"
    assert detail.json()["data"]["email"] is None
    assert delete.status_code == 405


def test_rename_recomputes_normalized_name_and_rejects_duplicate(client, db_session, tenant):
    first = _create_supplier(client, tenant, name="Proveedor Primero", tax_id="20-1")
    second = _create_supplier(client, tenant, name="Proveedor Segundo", tax_id="20-2")

    renamed = client.patch(
        f"/api/v1/suppliers/{first['id']}",
        headers=_headers(tenant),
        json={"name": "  PROVEEDOR   CENTRAL  "},
    )
    duplicate = client.patch(
        f"/api/v1/suppliers/{second['id']}",
        headers=_headers(tenant),
        json={"name": "proveedor central"},
    )

    db_session.expire_all()
    stored = db_session.scalar(
        select(Supplier).where(Supplier.id == uuid.UUID(first["id"]))
    )
    assert renamed.status_code == 200
    assert renamed.json()["data"]["name"] == "PROVEEDOR CENTRAL"
    assert stored.normalized_name == "proveedor central"
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "supplier_name_conflict"


def test_supplier_access_is_tenant_scoped(client, tenant, other_tenant):
    supplier = _create_supplier(client, tenant)

    detail = client.get(
        f"/api/v1/suppliers/{supplier['id']}", headers=_headers(other_tenant)
    )
    update = client.patch(
        f"/api/v1/suppliers/{supplier['id']}",
        headers=_headers(other_tenant),
        json={"name": "Ataque"},
    )
    listing = client.get("/api/v1/suppliers", headers=_headers(other_tenant))

    assert detail.status_code == 404
    assert update.status_code == 404
    assert listing.json()["data"] == []

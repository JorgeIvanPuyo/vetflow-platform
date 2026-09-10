import uuid

from app.models.user import User


def _headers(tenant) -> dict[str, str]:
    return {"X-Tenant-Id": str(tenant.id)}


def _user_headers(email: str) -> dict[str, str]:
    return {"X-User-Email": email}


def _create_user(db_session, tenant, email: str, full_name: str, role: str) -> User:
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=email,
        full_name=full_name,
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _supplier_payload(**overrides) -> dict:
    payload = {
        "name": "Distribuidora Veterinaria SA",
        "tax_id": "RUC-123",
        "phone": "+507 6000-0000",
        "email": "contacto@distribuidora.example",
        "address": "Calle 50",
        "notes": "Entrega semanal",
    }
    payload.update(overrides)
    return payload


def _create_supplier(client, admin, **overrides) -> dict:
    response = client.post(
        "/api/v1/suppliers",
        headers=_user_headers(admin.email),
        json=_supplier_payload(**overrides),
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_clinic_admin_can_create_and_list_suppliers(client, db_session, tenant):
    admin = _create_user(db_session, tenant, "sup-admin@example.com", "Clinic Admin", "clinic_admin")

    created = _create_supplier(client, admin)
    response = client.get("/api/v1/suppliers", headers=_headers(tenant))

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == created["id"]
    assert response.json()["data"][0]["tenant_id"] == str(tenant.id)
    assert response.json()["data"][0]["normalized_name"] == "distribuidora veterinaria sa"
    assert response.json()["data"][0]["created_by_user_id"] == str(admin.id)


def test_non_clinic_admin_cannot_mutate_suppliers(client, db_session, tenant):
    vet = _create_user(
        db_session,
        tenant,
        "sup-vet@example.com",
        "Regular Vet",
        "medico_veterinario",
    )

    response = client.post(
        "/api/v1/suppliers",
        headers=_user_headers(vet.email),
        json=_supplier_payload(),
    )
    read_response = client.get("/api/v1/suppliers", headers=_headers(tenant))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert read_response.status_code == 200


def test_duplicate_active_supplier_name_is_normalized_per_tenant(
    client,
    db_session,
    tenant,
    other_tenant,
):
    admin = _create_user(db_session, tenant, "sup-admin2@example.com", "Clinic Admin", "clinic_admin")
    other_admin = _create_user(
        db_session,
        other_tenant,
        "sup-other-admin@example.com",
        "Other Admin",
        "clinic_admin",
    )
    _create_supplier(client, admin, name="Proveedor   Central")

    duplicate = client.post(
        "/api/v1/suppliers",
        headers=_user_headers(admin.email),
        json=_supplier_payload(name=" proveedor central "),
    )
    other_tenant_response = client.post(
        "/api/v1/suppliers",
        headers=_user_headers(other_admin.email),
        json=_supplier_payload(name="proveedor central"),
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "supplier_name_conflict"
    assert other_tenant_response.status_code == 201


def test_deactivate_activate_and_include_inactive(client, db_session, tenant):
    admin = _create_user(db_session, tenant, "sup-admin3@example.com", "Clinic Admin", "clinic_admin")
    supplier = _create_supplier(client, admin)

    deactivate = client.post(
        f"/api/v1/suppliers/{supplier['id']}/deactivate",
        headers=_user_headers(admin.email),
    )
    active_list = client.get("/api/v1/suppliers", headers=_headers(tenant))
    inactive_list = client.get(
        "/api/v1/suppliers",
        headers=_headers(tenant),
        params={"include_inactive": True},
    )
    activate = client.post(
        f"/api/v1/suppliers/{supplier['id']}/activate",
        headers=_user_headers(admin.email),
    )

    assert deactivate.status_code == 200
    assert deactivate.json()["data"]["is_active"] is False
    assert active_list.json()["data"] == []
    assert inactive_list.json()["data"][0]["id"] == supplier["id"]
    assert activate.status_code == 200
    assert activate.json()["data"]["is_active"] is True


def test_reactivate_blocked_when_active_duplicate_exists(client, db_session, tenant):
    admin = _create_user(db_session, tenant, "sup-admin4@example.com", "Clinic Admin", "clinic_admin")
    original = _create_supplier(client, admin, name="Insumos del Sur")

    deactivate = client.post(
        f"/api/v1/suppliers/{original['id']}/deactivate",
        headers=_user_headers(admin.email),
    )
    replacement = _create_supplier(
        client, admin, name="insumos del sur", tax_id="RUC-456"
    )
    reactivate = client.post(
        f"/api/v1/suppliers/{original['id']}/activate",
        headers=_user_headers(admin.email),
    )

    assert deactivate.status_code == 200
    assert replacement["normalized_name"] == "insumos del sur"
    assert reactivate.status_code == 409
    assert reactivate.json()["error"]["code"] == "supplier_name_conflict"


def test_update_supplier_renames_and_renormalizes(client, db_session, tenant):
    admin = _create_user(db_session, tenant, "sup-admin5@example.com", "Clinic Admin", "clinic_admin")
    supplier = _create_supplier(client, admin, name="Veterinaria Insumos")

    response = client.patch(
        f"/api/v1/suppliers/{supplier['id']}",
        headers=_user_headers(admin.email),
        json={"name": "  Nuevos Insumos  ", "phone": "+507 6111-1111"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Nuevos Insumos"
    assert response.json()["data"]["normalized_name"] == "nuevos insumos"
    assert response.json()["data"]["phone"] == "+507 6111-1111"


def test_supplier_requires_authentication(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    response = client.get("/api/v1/suppliers")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_auth_token"


def test_tax_id_is_unique_per_tenant_and_null_is_repeatable(
    client, db_session, tenant, other_tenant
):
    admin = _create_user(
        db_session, tenant, "sup-tax-admin@example.com", "Clinic Admin", "clinic_admin"
    )
    other_admin = _create_user(
        db_session,
        other_tenant,
        "sup-tax-other@example.com",
        "Other Admin",
        "clinic_admin",
    )
    _create_supplier(client, admin, name="Proveedor A", tax_id="RUC-001")

    duplicate = client.post(
        "/api/v1/suppliers",
        headers=_user_headers(admin.email),
        json=_supplier_payload(name="Proveedor B", tax_id="RUC-001"),
    )
    cross_tenant = _create_supplier(
        client, other_admin, name="Proveedor Otro", tax_id="RUC-001"
    )
    first_null = _create_supplier(client, admin, name="Sin RUC A", tax_id=None)
    second_null = _create_supplier(client, admin, name="Sin RUC B", tax_id=None)

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "supplier_tax_id_conflict"
    assert cross_tenant["tax_id"] == "RUC-001"
    assert first_null["tax_id"] is None
    assert second_null["tax_id"] is None


def test_supplier_list_supports_search_pagination_and_inactive_filter(
    client, db_session, tenant
):
    admin = _create_user(
        db_session, tenant, "sup-list-admin@example.com", "Clinic Admin", "clinic_admin"
    )
    zeta = _create_supplier(client, admin, name="Zeta", tax_id="20-Z")
    alpha = _create_supplier(client, admin, name="Alpha", tax_id="20-A")
    inactive = _create_supplier(client, admin, name="Dormido", tax_id="20-D")
    client.post(
        f"/api/v1/suppliers/{inactive['id']}/deactivate",
        headers=_user_headers(admin.email),
    )

    page = client.get(
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

    assert page.json()["data"][0]["id"] == alpha["id"]
    assert page.json()["meta"] == {
        "page": 1,
        "page_size": 1,
        "total": 2,
        "total_pages": 2,
    }
    assert [row["id"] for row in search.json()["data"]] == [zeta["id"]]
    assert [row["id"] for row in inactive_list.json()["data"]] == [inactive["id"]]

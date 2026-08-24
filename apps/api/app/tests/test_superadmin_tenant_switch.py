import uuid

from app.models.user import User


def _create_user(db_session, tenant, email, full_name, role="medico_veterinario"):
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


def _auth_headers(email, acting_tenant_id=None):
    headers = {"Authorization": f"Bearer {email}"}
    if acting_tenant_id is not None:
        headers["X-Acting-Tenant-Id"] = str(acting_tenant_id)
    return headers


def _mock_auth(monkeypatch):
    import app.core.tenant as tenant_core

    monkeypatch.setattr(tenant_core, "verify_id_token", lambda token: {"email": token})


def test_superadmin_can_switch_acting_tenant(client, db_session, tenant, other_tenant, monkeypatch):
    _mock_auth(monkeypatch)
    admin = _create_user(db_session, tenant, "super1@example.com", "Super Admin", "superadmin")

    home_response = client.get("/api/v1/auth/me", headers=_auth_headers(admin.email))
    switched_response = client.get(
        "/api/v1/auth/me",
        headers=_auth_headers(admin.email, other_tenant.id),
    )

    assert home_response.json()["data"]["tenant_id"] == str(tenant.id)
    assert switched_response.status_code == 200
    body = switched_response.json()["data"]
    assert body["tenant_id"] == str(other_tenant.id)
    assert body["tenant_name"] == other_tenant.name
    # identity stays the superadmin's own, only the effective tenant changes
    assert body["id"] == str(admin.id)
    assert body["role"] == "superadmin"


def test_non_superadmin_cannot_switch_acting_tenant(
    client, db_session, tenant, other_tenant, monkeypatch
):
    _mock_auth(monkeypatch)
    vet = _create_user(db_session, tenant, "vet1@example.com", "Regular Vet")

    response = client.get(
        "/api/v1/auth/me",
        headers=_auth_headers(vet.email, other_tenant.id),
    )

    assert response.status_code == 200
    assert response.json()["data"]["tenant_id"] == str(tenant.id)


def test_switching_to_unknown_tenant_returns_404(client, db_session, tenant, monkeypatch):
    _mock_auth(monkeypatch)
    admin = _create_user(db_session, tenant, "super2@example.com", "Super Admin", "superadmin")

    response = client.get(
        "/api/v1/auth/me",
        headers=_auth_headers(admin.email, uuid.uuid4()),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "tenant_not_found"


def test_switching_to_malformed_tenant_id_returns_400(client, db_session, tenant, monkeypatch):
    _mock_auth(monkeypatch)
    admin = _create_user(db_session, tenant, "super3@example.com", "Super Admin", "superadmin")

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {admin.email}",
            "X-Acting-Tenant-Id": "not-a-uuid",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_acting_tenant_header"


def test_switched_data_reads_reflect_acting_tenant(
    client, db_session, tenant, other_tenant, monkeypatch
):
    _mock_auth(monkeypatch)
    admin = _create_user(db_session, tenant, "super4@example.com", "Super Admin", "superadmin")
    _create_user(db_session, other_tenant, "vet-other@example.com", "Vet In Other Tenant")

    response = client.post(
        "/api/v1/owners",
        headers=_auth_headers(admin.email, other_tenant.id),
        json={"full_name": "Owner In Other Tenant", "phone": "555-2000"},
    )
    list_response = client.get(
        "/api/v1/owners",
        headers=_auth_headers(admin.email, other_tenant.id),
    )
    home_list_response = client.get(
        "/api/v1/owners",
        headers=_auth_headers(admin.email),
    )

    assert response.status_code == 201
    assert response.json()["data"]["tenant_id"] == str(other_tenant.id)
    assert [owner["id"] for owner in list_response.json()["data"]] == [
        response.json()["data"]["id"]
    ]
    assert home_list_response.json()["data"] == []


def test_acting_as_tenant_does_not_grant_clinic_admin_permissions(
    client, db_session, tenant, other_tenant, monkeypatch
):
    _mock_auth(monkeypatch)
    admin = _create_user(db_session, tenant, "super5@example.com", "Super Admin", "superadmin")

    response = client.post(
        "/api/v1/services",
        headers=_auth_headers(admin.email, other_tenant.id),
        json={
            "code": "CONSULTA",
            "name": "Consulta general",
            "kind": "consultation",
            "default_duration_minutes": 30,
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"

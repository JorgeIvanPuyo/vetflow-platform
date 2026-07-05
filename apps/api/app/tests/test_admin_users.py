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


def _auth_headers(email):
    return {"Authorization": f"Bearer {email}"}


def _mock_auth(monkeypatch):
    import app.core.tenant as tenant_core

    monkeypatch.setattr(tenant_core, "verify_id_token", lambda token: {"email": token})


def _mock_firebase(monkeypatch):
    import app.services.admin_user as admin_service

    monkeypatch.setattr(
        admin_service,
        "create_firebase_user",
        lambda email, display_name, password: "fake-uid",
    )
    monkeypatch.setattr(
        admin_service,
        "generate_password_reset_link",
        lambda email: f"https://reset.example/{email}",
    )


def test_superadmin_lists_users_across_tenants(
    client, db_session, tenant, other_tenant, monkeypatch
):
    _mock_auth(monkeypatch)
    admin = _create_user(db_session, tenant, "admin@example.com", "Admin", "superadmin")
    _create_user(db_session, tenant, "vet@example.com", "Vet A")
    _create_user(db_session, other_tenant, "vet-b@example.com", "Vet B")

    response = client.get("/api/v1/admin/users", headers=_auth_headers(admin.email))

    assert response.status_code == 200
    body = response.json()
    emails = {item["email"] for item in body["data"]}
    assert {"admin@example.com", "vet@example.com", "vet-b@example.com"} <= emails
    assert body["meta"]["total"] == 3


def test_list_users_filters_by_tenant_and_active(
    client, db_session, tenant, other_tenant, monkeypatch
):
    _mock_auth(monkeypatch)
    admin = _create_user(db_session, tenant, "admin@example.com", "Admin", "superadmin")
    inactive = _create_user(db_session, tenant, "old@example.com", "Old Vet")
    inactive.is_active = False
    db_session.commit()
    _create_user(db_session, other_tenant, "vet-b@example.com", "Vet B")

    by_tenant = client.get(
        "/api/v1/admin/users",
        headers=_auth_headers(admin.email),
        params={"tenant_id": str(tenant.id)},
    )
    assert by_tenant.status_code == 200
    assert all(
        item["tenant_id"] == str(tenant.id) for item in by_tenant.json()["data"]
    )

    inactive_only = client.get(
        "/api/v1/admin/users",
        headers=_auth_headers(admin.email),
        params={"is_active": "false"},
    )
    assert inactive_only.status_code == 200
    emails = {item["email"] for item in inactive_only.json()["data"]}
    assert emails == {"old@example.com"}


def test_non_superadmin_cannot_access_admin_users(
    client, db_session, tenant, monkeypatch
):
    _mock_auth(monkeypatch)
    vet = _create_user(db_session, tenant, "vet@example.com", "Vet")

    response = client.get("/api/v1/admin/users", headers=_auth_headers(vet.email))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_superadmin_invites_user_creates_db_row(
    client, db_session, tenant, other_tenant, monkeypatch
):
    _mock_auth(monkeypatch)
    _mock_firebase(monkeypatch)
    admin = _create_user(db_session, tenant, "admin@example.com", "Admin", "superadmin")

    response = client.post(
        "/api/v1/admin/users/invite",
        headers=_auth_headers(admin.email),
        json={
            "email": "New.User@Example.com",
            "full_name": "New User",
            "role": "contador",
            "tenant_id": str(other_tenant.id),
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["user"]["email"] == "new.user@example.com"
    assert data["user"]["role"] == "contador"
    assert data["user"]["tenant_id"] == str(other_tenant.id)
    assert data["password_reset_link"] == "https://reset.example/new.user@example.com"

    created = (
        db_session.query(User).filter(User.email == "new.user@example.com").one()
    )
    assert created.role == "contador"
    assert created.tenant_id == other_tenant.id


def test_invite_rejects_duplicate_email(client, db_session, tenant, monkeypatch):
    _mock_auth(monkeypatch)
    _mock_firebase(monkeypatch)
    admin = _create_user(db_session, tenant, "admin@example.com", "Admin", "superadmin")

    response = client.post(
        "/api/v1/admin/users/invite",
        headers=_auth_headers(admin.email),
        json={
            "email": "admin@example.com",
            "full_name": "Dup User",
            "role": "medico_veterinario",
            "tenant_id": str(tenant.id),
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "user_already_exists"


def test_invite_rejects_invalid_role(client, db_session, tenant, monkeypatch):
    _mock_auth(monkeypatch)
    _mock_firebase(monkeypatch)
    admin = _create_user(db_session, tenant, "admin@example.com", "Admin", "superadmin")

    response = client.post(
        "/api/v1/admin/users/invite",
        headers=_auth_headers(admin.email),
        json={
            "email": "someone@example.com",
            "full_name": "Someone",
            "role": "wizard",
            "tenant_id": str(tenant.id),
        },
    )

    assert response.status_code == 422


def test_superadmin_lists_tenants(client, db_session, tenant, other_tenant, monkeypatch):
    _mock_auth(monkeypatch)
    admin = _create_user(db_session, tenant, "admin@example.com", "Admin", "superadmin")

    response = client.get("/api/v1/admin/tenants", headers=_auth_headers(admin.email))

    assert response.status_code == 200
    names = {item["name"] for item in response.json()["data"]}
    assert {"Tenant A", "Tenant B"} <= names

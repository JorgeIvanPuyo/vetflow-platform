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


def test_me_returns_role_from_database(client, db_session, tenant, monkeypatch):
    import app.core.tenant as tenant_core

    user = _create_user(db_session, tenant, "admin@example.com", "Super Admin", "superadmin")
    monkeypatch.setattr(tenant_core, "verify_id_token", lambda token: {"email": token})

    response = client.get("/api/v1/auth/me", headers=_auth_headers(user.email))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["email"] == "admin@example.com"
    assert data["role"] == "superadmin"
    assert data["tenant_id"] == str(tenant.id)
    assert data["tenant_name"] == tenant.name


def test_me_defaults_existing_users_to_medico_veterinario(
    client, db_session, tenant, monkeypatch
):
    import app.core.tenant as tenant_core

    user = _create_user(db_session, tenant, "vet@example.com", "Regular Vet")
    monkeypatch.setattr(tenant_core, "verify_id_token", lambda token: {"email": token})

    response = client.get("/api/v1/auth/me", headers=_auth_headers(user.email))

    assert response.status_code == 200
    assert response.json()["data"]["role"] == "medico_veterinario"

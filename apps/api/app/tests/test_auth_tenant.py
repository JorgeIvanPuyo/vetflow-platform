import uuid

from app.core.config import get_settings
from app.core.firebase import FirebaseTokenVerificationError
from app.models.user import User


def test_development_fallback_with_tenant_header_still_works(client, tenant):
    response = client.get(
        "/api/v1/owners",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 0


def test_production_rejects_missing_authorization(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()

    response = client.get("/api/v1/owners")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_auth_token"


def test_valid_firebase_email_resolves_user_tenant(
    client,
    db_session,
    tenant,
    other_tenant,
    monkeypatch,
):
    import app.core.tenant as tenant_core

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="vet@example.com",
        full_name="Vet User",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    monkeypatch.setattr(
        tenant_core,
        "verify_id_token",
        lambda token: {"email": "vet@example.com"},
    )

    response = client.post(
        "/api/v1/owners",
        headers={"Authorization": "Bearer test-token"},
        json={"full_name": "Auth Owner", "phone": "555"},
    )

    assert response.status_code == 201
    assert response.json()["data"]["tenant_id"] == str(tenant.id)
    assert response.json()["data"]["tenant_id"] != str(other_tenant.id)


def test_unknown_user_email_returns_forbidden(client, monkeypatch):
    import app.core.tenant as tenant_core

    monkeypatch.setattr(
        tenant_core,
        "verify_id_token",
        lambda token: {"email": "unknown@example.com"},
    )

    response = client.get(
        "/api/v1/owners",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "user_not_registered"


def test_inactive_user_returns_forbidden(client, db_session, tenant, monkeypatch):
    import app.core.tenant as tenant_core

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="inactive@example.com",
        full_name="Inactive User",
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    monkeypatch.setattr(
        tenant_core,
        "verify_id_token",
        lambda token: {"email": "inactive@example.com"},
    )

    response = client.get(
        "/api/v1/owners",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "inactive_user"


def test_invalid_token_returns_unauthorized(client, monkeypatch):
    import app.core.tenant as tenant_core

    def raise_invalid_token(token: str) -> dict[str, str]:
        raise FirebaseTokenVerificationError("invalid")

    monkeypatch.setattr(tenant_core, "verify_id_token", raise_invalid_token)

    response = client.get(
        "/api/v1/owners",
        headers={"Authorization": "Bearer bad-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_auth_token"

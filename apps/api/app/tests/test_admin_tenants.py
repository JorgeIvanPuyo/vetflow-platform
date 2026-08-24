import uuid

from app.models.catalog_item import CatalogItem
from app.models.service import Service
from app.models.tenant import Tenant
from app.models.tenant_preference import TenantPreference
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
    import app.services.tenant_provisioning as provisioning

    monkeypatch.setattr(
        provisioning,
        "create_firebase_user",
        lambda email, display_name, password: "fake-uid",
    )
    monkeypatch.setattr(
        provisioning,
        "generate_password_reset_link",
        lambda email: f"https://reset.example/{email}",
    )


def _create_tenant_payload(**overrides) -> dict:
    payload = {
        "name": "Nueva Clínica",
        "admin_email": "nueva-clinica-admin@example.com",
        "admin_full_name": "Admin Nueva Clínica",
    }
    payload.update(overrides)
    return payload


def test_superadmin_creates_tenant_with_seeded_defaults(
    client, db_session, tenant, monkeypatch
):
    _mock_auth(monkeypatch)
    _mock_firebase(monkeypatch)
    admin = _create_user(db_session, tenant, "admin@example.com", "Admin", "superadmin")

    response = client.post(
        "/api/v1/admin/tenants",
        headers=_auth_headers(admin.email),
        json=_create_tenant_payload(),
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["tenant"]["name"] == "Nueva Clínica"
    assert data["admin_user"]["email"] == "nueva-clinica-admin@example.com"
    assert data["admin_user"]["role"] == "clinic_admin"
    assert data["admin_user"]["tenant_id"] == data["tenant"]["id"]
    assert data["password_reset_link"] == (
        "https://reset.example/nueva-clinica-admin@example.com"
    )

    new_tenant_id = uuid.UUID(data["tenant"]["id"])
    db_session.expire_all()

    admin_user = (
        db_session.query(User)
        .filter(User.email == "nueva-clinica-admin@example.com")
        .one()
    )
    assert admin_user.tenant_id == new_tenant_id
    assert admin_user.role == "clinic_admin"
    assert admin_user.is_active is True

    created_tenant = db_session.get(Tenant, new_tenant_id)
    assert created_tenant is not None

    preferences = (
        db_session.query(TenantPreference)
        .filter(TenantPreference.tenant_id == new_tenant_id)
        .one_or_none()
    )
    assert preferences is not None
    assert preferences.currency_code == "USD"
    assert preferences.locale == "es-PA"
    assert preferences.appointment_duration_options == [15, 30, 45, 60]

    services = (
        db_session.query(Service).filter(Service.tenant_id == new_tenant_id).all()
    )
    assert len(services) == 5
    assert all(service.is_active for service in services)

    catalog_items = (
        db_session.query(CatalogItem)
        .filter(CatalogItem.tenant_id == new_tenant_id)
        .all()
    )
    mucous = [item for item in catalog_items if item.catalog_type == "mucous_membrane"]
    hydration = [item for item in catalog_items if item.catalog_type == "hydration"]
    assert len(mucous) == 6
    assert len(hydration) == 4
    assert all(item.is_active for item in catalog_items)


def test_non_superadmin_cannot_create_tenant(client, db_session, tenant, monkeypatch):
    _mock_auth(monkeypatch)
    _mock_firebase(monkeypatch)
    vet = _create_user(db_session, tenant, "vet@example.com", "Vet")

    response = client.post(
        "/api/v1/admin/tenants",
        headers=_auth_headers(vet.email),
        json=_create_tenant_payload(name="Otra Clínica"),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_create_tenant_rejects_blank_name(client, db_session, tenant, monkeypatch):
    _mock_auth(monkeypatch)
    _mock_firebase(monkeypatch)
    admin = _create_user(db_session, tenant, "admin2@example.com", "Admin", "superadmin")

    response = client.post(
        "/api/v1/admin/tenants",
        headers=_auth_headers(admin.email),
        json=_create_tenant_payload(name="   "),
    )

    assert response.status_code == 422


def test_create_tenant_rejects_duplicate_admin_email(
    client, db_session, tenant, monkeypatch
):
    _mock_auth(monkeypatch)
    _mock_firebase(monkeypatch)
    admin = _create_user(db_session, tenant, "admin3@example.com", "Admin", "superadmin")
    _create_user(db_session, tenant, "taken@example.com", "Ya Existe")

    tenants_before = db_session.query(Tenant).count()

    response = client.post(
        "/api/v1/admin/tenants",
        headers=_auth_headers(admin.email),
        json=_create_tenant_payload(admin_email="taken@example.com"),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "user_already_exists"
    db_session.expire_all()
    assert db_session.query(Tenant).count() == tenants_before


def test_create_tenant_leaves_no_partial_tenant_when_firebase_fails(
    client, db_session, tenant, monkeypatch
):
    import app.services.tenant_provisioning as provisioning

    _mock_auth(monkeypatch)
    admin = _create_user(db_session, tenant, "admin4@example.com", "Admin", "superadmin")

    def _raise_firebase_error(email, display_name, password):
        raise provisioning.FirebaseUserProvisioningError("boom")

    monkeypatch.setattr(provisioning, "create_firebase_user", _raise_firebase_error)

    tenants_before = db_session.query(Tenant).count()

    response = client.post(
        "/api/v1/admin/tenants",
        headers=_auth_headers(admin.email),
        json=_create_tenant_payload(name="Clínica Fallida"),
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "firebase_user_create_failed"
    db_session.expire_all()
    assert db_session.query(Tenant).count() == tenants_before
    assert (
        db_session.query(Tenant).filter(Tenant.name == "Clínica Fallida").one_or_none()
        is None
    )

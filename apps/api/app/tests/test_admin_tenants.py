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


def test_superadmin_creates_tenant_with_seeded_defaults(
    client, db_session, tenant, monkeypatch
):
    _mock_auth(monkeypatch)
    admin = _create_user(db_session, tenant, "admin@example.com", "Admin", "superadmin")

    response = client.post(
        "/api/v1/admin/tenants",
        headers=_auth_headers(admin.email),
        json={"name": "Nueva Clínica"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "Nueva Clínica"

    new_tenant_id = uuid.UUID(data["id"])
    db_session.expire_all()

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
    vet = _create_user(db_session, tenant, "vet@example.com", "Vet")

    response = client.post(
        "/api/v1/admin/tenants",
        headers=_auth_headers(vet.email),
        json={"name": "Otra Clínica"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_create_tenant_rejects_blank_name(client, db_session, tenant, monkeypatch):
    _mock_auth(monkeypatch)
    admin = _create_user(db_session, tenant, "admin2@example.com", "Admin", "superadmin")

    response = client.post(
        "/api/v1/admin/tenants",
        headers=_auth_headers(admin.email),
        json={"name": "   "},
    )

    assert response.status_code == 422

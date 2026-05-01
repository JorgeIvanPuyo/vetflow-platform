import uuid

from app.models.user import User
from app.schemas.patient import ClinicalHistoryPdfExportRequest
from app.services.clinical_history_pdf import ClinicalHistoryPdfService


def _headers(tenant) -> dict[str, str]:
    return {"X-Tenant-Id": str(tenant.id)}


def _create_user(
    db_session,
    tenant,
    *,
    email: str,
    full_name: str,
    is_active: bool = True,
) -> User:
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=email,
        full_name=full_name,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_owner(client, tenant) -> dict:
    response = client.post(
        "/api/v1/owners",
        headers=_headers(tenant),
        json={"full_name": "Clinic Owner", "phone": "555-1000"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_patient(client, tenant) -> dict:
    owner = _create_owner(client, tenant)
    response = client.post(
        "/api/v1/patients",
        headers=_headers(tenant),
        json={"owner_id": owner["id"], "name": "Luna", "species": "Canine"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_get_clinic_profile_uses_display_name_fallback(client, tenant):
    response = client.get("/api/v1/clinic/profile", headers=_headers(tenant))

    assert response.status_code == 200
    profile = response.json()["data"]
    assert profile["id"] == str(tenant.id)
    assert profile["name"] == "Tenant A"
    assert profile["display_name"] == "Tenant A"
    assert profile["logo_url"] is None
    assert profile["phone"] is None


def test_patch_clinic_profile(client, tenant):
    response = client.patch(
        "/api/v1/clinic/profile",
        headers=_headers(tenant),
        json={
            "display_name": "VetFlow Centro",
            "logo_url": "https://example.com/logo.png",
            "phone": "555-2200",
            "email": "hola@vetflow.test",
            "address": "Calle 12",
            "notes": "Atención por cita",
        },
    )

    assert response.status_code == 200
    profile = response.json()["data"]
    assert profile["name"] == "Tenant A"
    assert profile["display_name"] == "VetFlow Centro"
    assert profile["logo_url"] == "https://example.com/logo.png"
    assert profile["phone"] == "555-2200"
    assert profile["email"] == "hola@vetflow.test"
    assert profile["address"] == "Calle 12"
    assert profile["notes"] == "Atención por cita"


def test_get_clinic_team_returns_active_same_tenant_users_ordered(
    client,
    db_session,
    tenant,
):
    _create_user(
        db_session,
        tenant,
        email="zeta@example.com",
        full_name="Zeta Vet",
    )
    _create_user(
        db_session,
        tenant,
        email="ana@example.com",
        full_name="Ana Vet",
    )

    response = client.get("/api/v1/clinic/team", headers=_headers(tenant))

    assert response.status_code == 200
    team = response.json()["data"]
    assert [member["full_name"] for member in team] == ["Ana Vet", "Zeta Vet"]
    assert team[0]["email"] == "ana@example.com"
    assert team[0]["is_active"] is True


def test_get_clinic_team_excludes_inactive_users(client, db_session, tenant):
    active = _create_user(
        db_session,
        tenant,
        email="active@example.com",
        full_name="Active Vet",
    )
    _create_user(
        db_session,
        tenant,
        email="inactive@example.com",
        full_name="Inactive Vet",
        is_active=False,
    )

    response = client.get("/api/v1/clinic/team", headers=_headers(tenant))

    assert response.status_code == 200
    team = response.json()["data"]
    assert [member["id"] for member in team] == [str(active.id)]


def test_get_clinic_team_excludes_other_tenant_users(
    client,
    db_session,
    tenant,
    other_tenant,
):
    own_user = _create_user(
        db_session,
        tenant,
        email="own@example.com",
        full_name="Own Vet",
    )
    _create_user(
        db_session,
        other_tenant,
        email="foreign@example.com",
        full_name="Foreign Vet",
    )

    response = client.get("/api/v1/clinic/team", headers=_headers(tenant))

    assert response.status_code == 200
    team = response.json()["data"]
    assert [member["id"] for member in team] == [str(own_user.id)]


def test_clinic_profile_isolated_by_tenant(client, tenant, other_tenant):
    update_response = client.patch(
        "/api/v1/clinic/profile",
        headers=_headers(tenant),
        json={"display_name": "Clínica Norte", "phone": "555-1111"},
    )
    assert update_response.status_code == 200

    response = client.get("/api/v1/clinic/profile", headers=_headers(other_tenant))

    assert response.status_code == 200
    profile = response.json()["data"]
    assert profile["id"] == str(other_tenant.id)
    assert profile["display_name"] == "Tenant B"
    assert profile["phone"] is None


def test_pdf_export_includes_clinic_branding_when_configured(
    client,
    db_session,
    tenant,
):
    tenant.display_name = "Clínica Vet Central"
    tenant.phone = "555-3000"
    tenant.email = "contacto@vetcentral.test"
    tenant.address = "Avenida Principal 123"
    db_session.add(tenant)
    db_session.commit()

    patient = _create_patient(client, tenant)

    export = ClinicalHistoryPdfService(db_session).export_patient_history_pdf(
        tenant.id,
        uuid.UUID(patient["id"]),
        ClinicalHistoryPdfExportRequest(),
    )

    assert "Clínica: Clínica Vet Central" in export.text_lines
    assert "Teléfono de la clínica: 555-3000" in export.text_lines
    assert "Correo de la clínica: contacto@vetcentral.test" in export.text_lines
    assert "Dirección de la clínica: Avenida Principal 123" in export.text_lines

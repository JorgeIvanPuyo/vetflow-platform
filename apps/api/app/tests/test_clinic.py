import uuid

from app.models.user import User
from app.schemas.patient import ClinicalHistoryPdfExportRequest
from app.services.clinical_history_pdf import ClinicalHistoryPdfService
from app.services.storage import get_storage_service


class FakeStorageService:
    def __init__(self, bucket_name: str | None = "clinic-test-bucket") -> None:
        self.bucket_name = bucket_name
        self.uploads: list[dict] = []
        self.deletes: list[dict] = []
        self.signed_urls: list[dict] = []

    def upload_clinical_file(
        self,
        *,
        object_path: str,
        content: bytes,
        content_type: str,
    ) -> None:
        self.uploads.append(
            {
                "object_path": object_path,
                "content": content,
                "content_type": content_type,
            }
        )

    def delete_clinical_file(self, *, bucket_name: str, object_path: str) -> None:
        self.deletes.append(
            {
                "bucket_name": bucket_name,
                "object_path": object_path,
            }
        )

    def generate_signed_download_url(
        self,
        *,
        bucket_name: str,
        object_path: str,
        expires_in_seconds: int,
    ) -> str:
        self.signed_urls.append(
            {
                "bucket_name": bucket_name,
                "object_path": object_path,
                "expires_in_seconds": expires_in_seconds,
            }
        )
        return f"https://signed.example/{object_path}?expires={expires_in_seconds}"


class FailingUploadStorageService(FakeStorageService):
    def upload_clinical_file(
        self,
        *,
        object_path: str,
        content: bytes,
        content_type: str,
    ) -> None:
        raise RuntimeError("upload failed")


class FailingDeleteStorageService(FakeStorageService):
    def delete_clinical_file(self, *, bucket_name: str, object_path: str) -> None:
        raise RuntimeError("delete failed")


def _headers(tenant) -> dict[str, str]:
    return {"X-Tenant-Id": str(tenant.id)}


def _override_storage(client, storage: FakeStorageService) -> FakeStorageService:
    client.app.dependency_overrides[get_storage_service] = lambda: storage
    return storage


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


def test_upload_clinic_logo_success(client, db_session, tenant):
    storage = _override_storage(client, FakeStorageService())

    response = client.post(
        "/api/v1/clinic/logo",
        headers=_headers(tenant),
        files={"file": ("logo.png", b"logo-bytes", "image/png")},
    )

    assert response.status_code == 200
    profile = response.json()["data"]
    assert profile["logo_url"].startswith(
        f"https://signed.example/tenants/{tenant.id}/branding/logo/"
    )
    assert len(storage.uploads) == 1
    upload = storage.uploads[0]
    assert upload["object_path"] == (
        f"tenants/{tenant.id}/branding/logo/{tenant.id}-logo.png"
    )
    assert upload["content"] == b"logo-bytes"
    assert upload["content_type"] == "image/png"

    db_session.refresh(tenant)
    assert tenant.logo_url == f"gs://clinic-test-bucket/{upload['object_path']}"
    assert tenant.logo_object_path == upload["object_path"]


def test_upload_clinic_logo_rejects_invalid_mime_type(client, tenant):
    storage = _override_storage(client, FakeStorageService())

    response = client.post(
        "/api/v1/clinic/logo",
        headers=_headers(tenant),
        files={"file": ("logo.gif", b"gif", "image/gif")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "invalid_logo_type"
    assert storage.uploads == []


def test_upload_clinic_logo_rejects_oversize_file(client, tenant):
    storage = _override_storage(client, FakeStorageService())

    response = client.post(
        "/api/v1/clinic/logo",
        headers=_headers(tenant),
        files={"file": ("logo.png", b"x" * (5 * 1024 * 1024 + 1), "image/png")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "logo_too_large"
    assert storage.uploads == []


def test_upload_clinic_logo_replaces_old_logo(client, db_session, tenant):
    storage = _override_storage(client, FakeStorageService())
    tenant.logo_url = "gs://clinic-test-bucket/tenants/old/logo.png"
    tenant.logo_object_path = "tenants/old/logo.png"
    db_session.add(tenant)
    db_session.commit()

    response = client.post(
        "/api/v1/clinic/logo",
        headers=_headers(tenant),
        files={"file": ("new-logo.webp", b"webp", "image/webp")},
    )

    assert response.status_code == 200
    assert storage.deletes == [
        {
            "bucket_name": "clinic-test-bucket",
            "object_path": "tenants/old/logo.png",
        }
    ]
    assert storage.uploads[0]["object_path"] == (
        f"tenants/{tenant.id}/branding/logo/{tenant.id}-new-logo.webp"
    )


def test_delete_clinic_logo(client, db_session, tenant):
    storage = _override_storage(client, FakeStorageService())
    tenant.logo_url = "gs://clinic-test-bucket/tenants/tenant/logo.png"
    tenant.logo_object_path = "tenants/tenant/logo.png"
    db_session.add(tenant)
    db_session.commit()

    response = client.delete("/api/v1/clinic/logo", headers=_headers(tenant))

    assert response.status_code == 200
    profile = response.json()["data"]
    assert profile["logo_url"] is None
    assert storage.deletes == [
        {
            "bucket_name": "clinic-test-bucket",
            "object_path": "tenants/tenant/logo.png",
        }
    ]
    db_session.refresh(tenant)
    assert tenant.logo_url is None
    assert tenant.logo_object_path is None


def test_clinic_profile_returns_signed_logo_url(client, db_session, tenant):
    storage = _override_storage(client, FakeStorageService())
    tenant.logo_url = "gs://clinic-test-bucket/tenants/tenant/logo.png"
    tenant.logo_object_path = "tenants/tenant/logo.png"
    db_session.add(tenant)
    db_session.commit()

    response = client.get("/api/v1/clinic/profile", headers=_headers(tenant))

    assert response.status_code == 200
    assert response.json()["data"]["logo_url"] == (
        "https://signed.example/tenants/tenant/logo.png?expires=900"
    )
    assert storage.signed_urls == [
        {
            "bucket_name": "clinic-test-bucket",
            "object_path": "tenants/tenant/logo.png",
            "expires_in_seconds": 900,
        }
    ]


def test_clinic_logo_tenant_isolation(client, db_session, tenant, other_tenant):
    storage = _override_storage(client, FakeStorageService())

    upload_response = client.post(
        "/api/v1/clinic/logo",
        headers=_headers(tenant),
        files={"file": ("logo.jpg", b"jpeg", "image/jpeg")},
    )
    assert upload_response.status_code == 200

    other_profile_response = client.get(
        "/api/v1/clinic/profile",
        headers=_headers(other_tenant),
    )

    assert other_profile_response.status_code == 200
    assert other_profile_response.json()["data"]["logo_url"] is None
    db_session.refresh(other_tenant)
    assert other_tenant.logo_object_path is None
    assert len(storage.uploads) == 1

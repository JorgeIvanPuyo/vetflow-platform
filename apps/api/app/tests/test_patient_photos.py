import uuid

from app.models.patient import Patient
from app.services.storage import get_storage_service


class FakeStorageService:
    def __init__(self, bucket_name: str | None = "patient-photo-test-bucket") -> None:
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
        super().upload_clinical_file(
            object_path=object_path,
            content=content,
            content_type=content_type,
        )
        raise RuntimeError("upload denied")


def _headers(tenant) -> dict[str, str]:
    return {"X-Tenant-Id": str(tenant.id)}


def _override_storage(client, storage: FakeStorageService) -> FakeStorageService:
    client.app.dependency_overrides[get_storage_service] = lambda: storage
    return storage


def _create_owner(client, tenant, full_name: str = "Owner") -> dict:
    response = client.post(
        "/api/v1/owners",
        headers=_headers(tenant),
        json={"full_name": full_name, "phone": "555-1000"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_patient(client, tenant, name: str = "Luna") -> dict:
    owner = _create_owner(client, tenant, f"{name} Owner")
    response = client.post(
        "/api/v1/patients",
        headers=_headers(tenant),
        json={"owner_id": owner["id"], "name": name, "species": "Canine"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def _upload_photo(
    client,
    tenant,
    patient_id: str,
    *,
    filename: str = "luna.png",
    content: bytes = b"image-bytes",
    content_type: str = "image/png",
) -> dict:
    response = client.post(
        f"/api/v1/patients/{patient_id}/photo",
        headers=_headers(tenant),
        files={"file": (filename, content, content_type)},
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_upload_patient_photo_success(client, tenant):
    storage = _override_storage(client, FakeStorageService())
    patient = _create_patient(client, tenant)

    body = _upload_photo(client, tenant, patient["id"])

    assert body["id"] == patient["id"]
    assert body["photo_url"].startswith(
        f"https://signed.example/tenants/{tenant.id}/patients/{patient['id']}/profile-photo/"
    )
    assert body["photo_original_filename"] == "luna.png"
    assert body["photo_content_type"] == "image/png"
    assert body["photo_size_bytes"] == len(b"image-bytes")
    assert body["photo_uploaded_at"] is not None
    assert len(storage.uploads) == 1


def test_upload_patient_photo_stores_metadata_on_patient(
    client,
    db_session,
    tenant,
):
    storage = _override_storage(client, FakeStorageService())
    patient = _create_patient(client, tenant)

    _upload_photo(client, tenant, patient["id"], filename="Luna bonita.webp")

    db_patient = db_session.get(Patient, uuid.UUID(patient["id"]))
    assert db_patient is not None
    assert db_patient.photo_url == (
        f"gs://patient-photo-test-bucket/{storage.uploads[0]['object_path']}"
    )
    assert db_patient.photo_bucket_name == "patient-photo-test-bucket"
    assert db_patient.photo_object_path == storage.uploads[0]["object_path"]
    assert db_patient.photo_original_filename == "Luna bonita.webp"
    assert db_patient.photo_content_type == "image/png"
    assert db_patient.photo_size_bytes == len(b"image-bytes")
    assert db_patient.photo_uploaded_at is not None


def test_upload_patient_photo_returns_signed_url(client, tenant):
    storage = _override_storage(client, FakeStorageService())
    patient = _create_patient(client, tenant)

    body = _upload_photo(client, tenant, patient["id"])

    assert body["photo_url"].startswith("https://signed.example/")
    assert storage.signed_urls == [
        {
            "bucket_name": "patient-photo-test-bucket",
            "object_path": storage.uploads[0]["object_path"],
            "expires_in_seconds": 900,
        }
    ]


def test_upload_patient_photo_rejects_invalid_mime_type(client, tenant):
    storage = _override_storage(client, FakeStorageService())
    patient = _create_patient(client, tenant)

    response = client.post(
        f"/api/v1/patients/{patient['id']}/photo",
        headers=_headers(tenant),
        files={"file": ("luna.gif", b"gif", "image/gif")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "invalid_patient_photo_type"
    assert storage.uploads == []


def test_upload_patient_photo_rejects_oversized_image(client, tenant):
    storage = _override_storage(client, FakeStorageService())
    patient = _create_patient(client, tenant)

    response = client.post(
        f"/api/v1/patients/{patient['id']}/photo",
        headers=_headers(tenant),
        files={"file": ("luna.png", b"x" * (5 * 1024 * 1024 + 1), "image/png")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "patient_photo_too_large"
    assert storage.uploads == []


def test_upload_patient_photo_rejects_patient_from_another_tenant(
    client,
    tenant,
    other_tenant,
):
    storage = _override_storage(client, FakeStorageService())
    foreign_patient = _create_patient(client, other_tenant, "Nina")

    response = client.post(
        f"/api/v1/patients/{foreign_patient['id']}/photo",
        headers=_headers(tenant),
        files={"file": ("nina.jpg", b"jpg", "image/jpeg")},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_cross_tenant_access"
    assert storage.uploads == []


def test_replacing_patient_photo_deletes_previous_object(client, tenant):
    storage = _override_storage(client, FakeStorageService())
    patient = _create_patient(client, tenant)
    first = _upload_photo(client, tenant, patient["id"], filename="first.png")

    second = _upload_photo(
        client,
        tenant,
        patient["id"],
        filename="second.jpg",
        content=b"second",
        content_type="image/jpeg",
    )

    assert storage.deletes == [
        {
            "bucket_name": "patient-photo-test-bucket",
            "object_path": storage.uploads[0]["object_path"],
        }
    ]
    assert second["photo_original_filename"] == "second.jpg"
    assert second["photo_url"] != first["photo_url"]


def test_delete_patient_photo_deletes_object_and_clears_metadata(
    client,
    db_session,
    tenant,
):
    storage = _override_storage(client, FakeStorageService())
    patient = _create_patient(client, tenant)
    _upload_photo(client, tenant, patient["id"])

    response = client.delete(
        f"/api/v1/patients/{patient['id']}/photo",
        headers=_headers(tenant),
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["photo_url"] is None
    assert body["photo_original_filename"] is None
    assert body["photo_content_type"] is None
    assert body["photo_size_bytes"] is None
    assert body["photo_uploaded_at"] is None
    assert storage.deletes == [
        {
            "bucket_name": "patient-photo-test-bucket",
            "object_path": storage.uploads[0]["object_path"],
        }
    ]
    db_patient = db_session.get(Patient, uuid.UUID(patient["id"]))
    assert db_patient is not None
    assert db_patient.photo_url is None
    assert db_patient.photo_object_path is None


def test_patient_list_includes_signed_photo_url(client, tenant):
    storage = _override_storage(client, FakeStorageService())
    patient = _create_patient(client, tenant)
    _upload_photo(client, tenant, patient["id"])

    response = client.get("/api/v1/patients", headers=_headers(tenant))

    assert response.status_code == 200
    body = response.json()["data"]
    assert body[0]["photo_url"].startswith("https://signed.example/")


def test_patient_detail_includes_signed_photo_url(client, tenant):
    storage = _override_storage(client, FakeStorageService())
    patient = _create_patient(client, tenant)
    _upload_photo(client, tenant, patient["id"])

    response = client.get(
        f"/api/v1/patients/{patient['id']}",
        headers=_headers(tenant),
    )

    assert response.status_code == 200
    assert response.json()["data"]["photo_url"].startswith("https://signed.example/")


def test_patient_without_photo_returns_null_photo_url(client, tenant):
    _override_storage(client, FakeStorageService())
    patient = _create_patient(client, tenant)

    response = client.get(
        f"/api/v1/patients/{patient['id']}",
        headers=_headers(tenant),
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["photo_url"] is None
    assert body["photo_original_filename"] is None


def test_deleting_patient_removes_photo_object(client, tenant):
    storage = _override_storage(client, FakeStorageService())
    patient = _create_patient(client, tenant)
    _upload_photo(client, tenant, patient["id"])

    response = client.delete(
        f"/api/v1/patients/{patient['id']}",
        headers=_headers(tenant),
    )

    assert response.status_code == 204
    assert storage.deletes == [
        {
            "bucket_name": "patient-photo-test-bucket",
            "object_path": storage.uploads[0]["object_path"],
        }
    ]


def test_storage_upload_failure_rolls_back_photo_metadata(
    client,
    db_session,
    tenant,
):
    storage = _override_storage(client, FailingUploadStorageService())
    patient = _create_patient(client, tenant)

    response = client.post(
        f"/api/v1/patients/{patient['id']}/photo",
        headers=_headers(tenant),
        files={"file": ("luna.png", b"image-bytes", "image/png")},
    )

    assert response.status_code == 502
    assert response.json()["error"] == {
        "code": "patient_photo_upload_failed",
        "message": "Patient photo upload failed",
    }
    db_patient = db_session.get(Patient, uuid.UUID(patient["id"]))
    assert db_patient is not None
    assert db_patient.photo_url is None
    assert db_patient.photo_object_path is None
    assert db_patient.photo_original_filename is None

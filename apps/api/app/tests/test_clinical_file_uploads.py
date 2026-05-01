import logging
import uuid

from app.core.config import get_settings
from app.services.storage import get_storage_service


class FakeStorageService:
    def __init__(self, bucket_name: str | None = "clinical-test-bucket") -> None:
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
        return "https://signed.example/download?token=test"


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
        raise RuntimeError("GCS upload denied")


def _headers(tenant) -> dict:
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


def _create_manual_file_reference(client, tenant, patient_id: str) -> dict:
    response = client.post(
        f"/api/v1/patients/{patient_id}/file-references",
        headers=_headers(tenant),
        json={
            "name": "Referencia externa",
            "file_type": "radiography",
            "description": "Archivo en sistema externo",
            "external_url": "https://example.com/file.pdf",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def _upload_file(
    client,
    tenant,
    patient_id: str,
    *,
    filename: str = "laboratorio.pdf",
    content: bytes = b"%PDF-1.4",
    content_type: str = "application/pdf",
) -> dict:
    response = client.post(
        f"/api/v1/patients/{patient_id}/files/upload",
        headers=_headers(tenant),
        data={
            "name": "Laboratorio",
            "file_type": "laboratory",
            "description": "Hemograma",
        },
        files={"file": (filename, content, content_type)},
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_upload_file_creates_metadata_and_calls_storage(client, tenant):
    storage = _override_storage(client, FakeStorageService())
    patient = _create_patient(client, tenant)

    file_reference = _upload_file(client, tenant, patient["id"])

    assert file_reference["tenant_id"] == str(tenant.id)
    assert file_reference["patient_id"] == patient["id"]
    assert file_reference["bucket_name"] == "clinical-test-bucket"
    assert file_reference["original_filename"] == "laboratorio.pdf"
    assert file_reference["content_type"] == "application/pdf"
    assert file_reference["size_bytes"] == len(b"%PDF-1.4")
    assert file_reference["uploaded_at"] is not None
    assert file_reference["object_path"].startswith(
        f"tenants/{tenant.id}/patients/{patient['id']}/files/{file_reference['id']}/"
    )
    assert len(storage.uploads) == 1
    assert storage.uploads[0]["object_path"] == file_reference["object_path"]
    assert storage.uploads[0]["content"] == b"%PDF-1.4"
    assert storage.uploads[0]["content_type"] == "application/pdf"


def test_upload_rejects_invalid_content_type(client, tenant):
    _override_storage(client, FakeStorageService())
    patient = _create_patient(client, tenant)

    response = client.post(
        f"/api/v1/patients/{patient['id']}/files/upload",
        headers=_headers(tenant),
        data={"name": "Texto", "file_type": "document"},
        files={"file": ("nota.txt", b"not a clinical file", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "invalid_file_type"


def test_upload_rejects_oversized_file(client, tenant, monkeypatch):
    _override_storage(client, FakeStorageService())
    monkeypatch.setenv("MAX_CLINICAL_FILE_SIZE_MB", "0")
    get_settings.cache_clear()
    patient = _create_patient(client, tenant)

    response = client.post(
        f"/api/v1/patients/{patient['id']}/files/upload",
        headers=_headers(tenant),
        data={"name": "Imagen", "file_type": "photo"},
        files={"file": ("imagen.png", b"x", "image/png")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_upload_rejects_patient_from_another_tenant(client, tenant, other_tenant):
    storage = _override_storage(client, FakeStorageService())
    foreign_patient = _create_patient(client, other_tenant, "Nina")

    response = client.post(
        f"/api/v1/patients/{foreign_patient['id']}/files/upload",
        headers=_headers(tenant),
        data={"name": "Archivo", "file_type": "laboratory"},
        files={"file": ("laboratorio.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_cross_tenant_access"
    assert storage.uploads == []


def test_upload_failure_logs_safe_storage_context(client, tenant, caplog):
    storage = _override_storage(client, FailingUploadStorageService())
    patient = _create_patient(client, tenant)

    with caplog.at_level(logging.ERROR, logger="app.services.file_reference"):
        response = client.post(
            f"/api/v1/patients/{patient['id']}/files/upload",
            headers=_headers(tenant),
            data={"name": "Laboratorio", "file_type": "laboratory"},
            files={"file": ("laboratorio.pdf", b"%PDF-1.4", "application/pdf")},
        )

    assert response.status_code == 502
    assert response.json()["error"] == {
        "code": "storage_upload_failed",
        "message": "Clinical file upload failed",
    }
    assert len(storage.uploads) == 1

    log_record = next(
        record
        for record in caplog.records
        if record.message.startswith("Clinical file upload failed.")
    )
    assert log_record.exception_class == "RuntimeError"
    assert log_record.exception_message == "GCS upload denied"
    assert log_record.bucket_name == "clinical-test-bucket"
    assert log_record.object_path.startswith(
        f"tenants/{tenant.id}/patients/{patient['id']}/files/"
    )
    assert log_record.content_type == "application/pdf"
    assert log_record.size_bytes == len(b"%PDF-1.4")


def test_download_url_returns_signed_url_for_uploaded_file(client, tenant):
    storage = _override_storage(client, FakeStorageService())
    patient = _create_patient(client, tenant)
    file_reference = _upload_file(client, tenant, patient["id"])

    response = client.get(
        f"/api/v1/file-references/{file_reference['id']}/download-url",
        headers=_headers(tenant),
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body == {
        "download_url": "https://signed.example/download?token=test",
        "expires_in_seconds": 900,
    }
    assert storage.signed_urls == [
        {
            "bucket_name": "clinical-test-bucket",
            "object_path": file_reference["object_path"],
            "expires_in_seconds": 900,
        }
    ]


def test_download_url_rejects_reference_without_object_path(client, tenant):
    _override_storage(client, FakeStorageService())
    patient = _create_patient(client, tenant)
    file_reference = _create_manual_file_reference(client, tenant, patient["id"])

    response = client.get(
        f"/api/v1/file-references/{file_reference['id']}/download-url",
        headers=_headers(tenant),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "file_reference_not_found"


def test_delete_uploaded_file_deletes_storage_object_and_metadata(client, tenant):
    storage = _override_storage(client, FakeStorageService())
    patient = _create_patient(client, tenant)
    file_reference = _upload_file(client, tenant, patient["id"])

    response = client.delete(
        f"/api/v1/file-references/{file_reference['id']}",
        headers=_headers(tenant),
    )

    assert response.status_code == 204
    assert storage.deletes == [
        {
            "bucket_name": "clinical-test-bucket",
            "object_path": file_reference["object_path"],
        }
    ]
    get_response = client.get(
        f"/api/v1/file-references/{file_reference['id']}",
        headers=_headers(tenant),
    )
    assert get_response.status_code == 404


def test_delete_reference_only_file_reference_still_works(client, tenant):
    storage = _override_storage(client, FakeStorageService())
    patient = _create_patient(client, tenant)
    file_reference = _create_manual_file_reference(client, tenant, patient["id"])

    response = client.delete(
        f"/api/v1/file-references/{file_reference['id']}",
        headers=_headers(tenant),
    )

    assert response.status_code == 204
    assert storage.deletes == []
    get_response = client.get(
        f"/api/v1/file-references/{file_reference['id']}",
        headers=_headers(tenant),
    )
    assert get_response.status_code == 404


def test_tenant_isolation_for_download_and_delete(client, tenant, other_tenant):
    storage = _override_storage(client, FakeStorageService())
    foreign_patient = _create_patient(client, other_tenant, "Nina")
    file_reference = _upload_file(client, other_tenant, foreign_patient["id"])

    download_response = client.get(
        f"/api/v1/file-references/{file_reference['id']}/download-url",
        headers=_headers(tenant),
    )
    delete_response = client.delete(
        f"/api/v1/file-references/{file_reference['id']}",
        headers=_headers(tenant),
    )

    assert download_response.status_code == 404
    assert delete_response.status_code == 404
    assert storage.signed_urls == []
    assert storage.deletes == []


def test_clinical_history_still_includes_uploaded_file_reference(client, tenant):
    _override_storage(client, FakeStorageService())
    patient = _create_patient(client, tenant)
    file_reference = _upload_file(client, tenant, patient["id"])

    response = client.get(
        f"/api/v1/patients/{patient['id']}/clinical-history",
        headers=_headers(tenant),
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["file_references"][0]["id"] == file_reference["id"]
    assert any(
        item["type"] == "file_reference"
        and item["id"] == file_reference["id"]
        and item["title"] == "Laboratorio"
        and item["summary"] == "laboratory"
        for item in body["timeline"]
    )


def test_unknown_file_reference_download_url_returns_not_found(client, tenant):
    _override_storage(client, FakeStorageService())

    response = client.get(
        f"/api/v1/file-references/{uuid.uuid4()}/download-url",
        headers=_headers(tenant),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "file_reference_not_found"

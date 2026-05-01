import json

from app.core.config import get_settings
from app.services.storage import ClinicalFileStorageService


class FakeCredentials:
    def __init__(self, project_id: str) -> None:
        self.project_id = project_id


class FakeBlob:
    def __init__(self) -> None:
        self.uploads: list[dict] = []
        self.deleted = False
        self.signed_url_kwargs: dict | None = None

    def upload_from_string(self, content: bytes, *, content_type: str) -> None:
        self.uploads.append({"content": content, "content_type": content_type})

    def delete(self) -> None:
        self.deleted = True

    def generate_signed_url(self, **kwargs) -> str:
        self.signed_url_kwargs = kwargs
        return "https://signed.example/file"


class FakeBucket:
    def __init__(self) -> None:
        self.blobs: dict[str, FakeBlob] = {}

    def blob(self, object_path: str) -> FakeBlob:
        if object_path not in self.blobs:
            self.blobs[object_path] = FakeBlob()
        return self.blobs[object_path]


class FakeStorageClient:
    instances: list["FakeStorageClient"] = []

    def __init__(self, credentials=None, project=None) -> None:
        self.credentials = credentials
        self.project = project
        self.buckets: dict[str, FakeBucket] = {}
        FakeStorageClient.instances.append(self)

    def bucket(self, bucket_name: str) -> FakeBucket:
        if bucket_name not in self.buckets:
            self.buckets[bucket_name] = FakeBucket()
        return self.buckets[bucket_name]


def _patch_storage_client(monkeypatch) -> None:
    from google.cloud import storage

    FakeStorageClient.instances = []
    monkeypatch.setattr(storage, "Client", FakeStorageClient)


def test_storage_client_uses_google_application_credentials_path_first(monkeypatch):
    from google.oauth2 import service_account

    file_credentials = FakeCredentials(project_id="file-project")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/app/firebase-service-account.json")
    monkeypatch.setenv(
        "FIREBASE_SERVICE_ACCOUNT_JSON",
        json.dumps({"project_id": "env-project"}),
    )
    get_settings.cache_clear()
    _patch_storage_client(monkeypatch)
    monkeypatch.setattr(
        service_account.Credentials,
        "from_service_account_file",
        staticmethod(lambda path: file_credentials),
    )
    monkeypatch.setattr(
        service_account.Credentials,
        "from_service_account_info",
        staticmethod(lambda info: (_ for _ in ()).throw(AssertionError("env not used"))),
    )

    service = ClinicalFileStorageService(bucket_name="clinical-files")
    service.upload_clinical_file(
        object_path="tenants/t1/patients/p1/files/f1/lab.pdf",
        content=b"%PDF-1.4",
        content_type="application/pdf",
    )

    assert len(FakeStorageClient.instances) == 1
    client = FakeStorageClient.instances[0]
    assert client.credentials is file_credentials
    assert client.project == "file-project"
    blob = client.buckets["clinical-files"].blobs[
        "tenants/t1/patients/p1/files/f1/lab.pdf"
    ]
    assert blob.uploads == [
        {"content": b"%PDF-1.4", "content_type": "application/pdf"}
    ]


def test_signed_url_uses_firebase_service_account_json_credentials(monkeypatch):
    from google.oauth2 import service_account

    env_credentials = FakeCredentials(project_id="env-project")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setenv(
        "FIREBASE_SERVICE_ACCOUNT_JSON",
        json.dumps({"project_id": "env-project", "client_email": "svc@example.com"}),
    )
    get_settings.cache_clear()
    _patch_storage_client(monkeypatch)
    monkeypatch.setattr(
        service_account.Credentials,
        "from_service_account_info",
        staticmethod(lambda info: env_credentials),
    )

    service = ClinicalFileStorageService(bucket_name="clinical-files")
    signed_url = service.generate_signed_download_url(
        bucket_name="clinical-files",
        object_path="tenants/t1/patients/p1/files/f1/lab.pdf",
        expires_in_seconds=900,
    )

    assert signed_url == "https://signed.example/file"
    assert len(FakeStorageClient.instances) == 1
    client = FakeStorageClient.instances[0]
    assert client.credentials is env_credentials
    assert client.project == "env-project"
    blob = client.buckets["clinical-files"].blobs[
        "tenants/t1/patients/p1/files/f1/lab.pdf"
    ]
    assert blob.signed_url_kwargs is not None
    assert blob.signed_url_kwargs["method"] == "GET"
    assert blob.signed_url_kwargs["credentials"] is env_credentials


def test_storage_client_falls_back_to_adc_when_no_explicit_credentials(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_JSON", raising=False)
    get_settings.cache_clear()
    _patch_storage_client(monkeypatch)

    service = ClinicalFileStorageService(bucket_name="clinical-files")
    signed_url = service.generate_signed_download_url(
        bucket_name="clinical-files",
        object_path="tenants/t1/patients/p1/files/f1/lab.pdf",
        expires_in_seconds=900,
    )

    assert signed_url == "https://signed.example/file"
    client = FakeStorageClient.instances[0]
    assert client.credentials is None
    assert client.project is None
    blob = client.buckets["clinical-files"].blobs[
        "tenants/t1/patients/p1/files/f1/lab.pdf"
    ]
    assert "credentials" not in blob.signed_url_kwargs

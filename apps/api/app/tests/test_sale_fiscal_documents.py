import uuid

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.models.sale_fiscal import (
    SaleFiscalDocument,
    SaleFiscalDocumentFileVersion,
)
from app.models.user import User
from app.repositories.sale_fiscal_document import SaleFiscalDocumentRepository
from app.services.storage import get_purchase_attachment_storage_service


PDF = b"%PDF-1.7\nsale receipt"
JPEG = b"\xff\xd8\xff\xe0sale receipt"
PNG = b"\x89PNG\r\n\x1a\nsale receipt"


class FakeStorage:
    bucket_name = "sale-fiscal-test-bucket"

    def __init__(self):
        self.objects = {}
        self.uploads = []
        self.deletes = []
        self.fail_upload = False

    def upload_clinical_file(self, *, object_path, content, content_type):
        del content_type
        self.objects[object_path] = content
        self.uploads.append(object_path)
        if self.fail_upload:
            raise RuntimeError("storage unavailable")

    def delete_clinical_file(self, *, bucket_name, object_path):
        assert bucket_name == self.bucket_name
        self.objects.pop(object_path, None)
        self.deletes.append(object_path)

    def download_object_bytes(self, *, bucket_name, object_path):
        assert bucket_name == self.bucket_name
        return self.objects[object_path]


def _headers(tenant):
    return {"X-Tenant-Id": str(tenant.id)}


def _auth_headers(email):
    return {"Authorization": f"Bearer {email}"}


def _storage(client):
    storage = FakeStorage()
    client.app.dependency_overrides[get_purchase_attachment_storage_service] = (
        lambda: storage
    )
    return storage


def _user(db, tenant, *, email="fiscal@example.com", name="Dra. Fiscal"):
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=email,
        full_name=name,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def _issuer(client, tenant, user, *, mode="service", same_mixed=False):
    service = mode in {"service", "mixed"}
    product = mode in {"product", "mixed"}
    payload = {
        "user_id": str(user.id),
        "display_name": "Dra. Fiscal",
        "tax_id": "20-11111111-1",
        "can_issue_service_receipt_c": service,
        "can_issue_product_invoice_c": product,
        "service_document_type": "receipt_c" if service else None,
        "service_document_code": "015" if service else None,
        "product_document_type": (
            "receipt_c" if same_mixed else "invoice_c"
        )
        if product
        else None,
        "product_document_code": ("015" if same_mixed else "011")
        if product
        else None,
    }
    response = client.post(
        "/api/v1/fiscal-issuers", headers=_headers(tenant), json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _product(client, tenant):
    response = client.post(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        json={
            "name": "Vacuna",
            "category": "vaccine",
            "unit": "unit",
            "minimum_stock": "0",
            "sale_price_ars": "100",
        },
    )
    assert response.status_code == 201, response.text
    product = response.json()["data"]
    response = client.post(
        f"/api/v1/inventory/items/{product['id']}/movements/entry",
        headers=_headers(tenant),
        json={"quantity": "10"},
    )
    assert response.status_code == 201
    return product


def _sale(client, tenant, *, kind="service", status="confirmed"):
    items = []
    if kind in {"product", "mixed"}:
        product = _product(client, tenant)
        items.append(
            {
                "line_type": "product",
                "inventory_item_id": product["id"],
                "quantity": "1",
                "unit_price_ars": "100",
                "discount_percentage": "0",
            }
        )
    if kind in {"service", "mixed"}:
        items.append(
            {
                "line_type": "service",
                "description": "Consulta",
                "quantity": "1",
                "unit_price_ars": "50",
                "discount_percentage": "0",
            }
        )
    response = client.post(
        "/api/v1/sales",
        headers=_headers(tenant),
        json={
            "owner_id": None,
            "patient_id": None,
            "sale_date": "2026-08-09",
            "items": items,
        },
    )
    assert response.status_code == 201, response.text
    sale = response.json()["data"]
    if status in {"confirmed", "reversed"}:
        response = client.post(
            f"/api/v1/sales/{sale['id']}/confirm",
            headers=_headers(tenant),
            json={"confirm": True},
        )
        assert response.status_code == 200, response.text
        sale = response.json()["data"]
    elif status == "cancelled":
        response = client.post(
            f"/api/v1/sales/{sale['id']}/cancel",
            headers=_headers(tenant),
            json={"reason": "Error"},
        )
        sale = response.json()["data"]
    if status == "reversed":
        response = client.post(
            f"/api/v1/sales/{sale['id']}/reverse",
            headers=_headers(tenant),
            json={"reason": "Error"},
        )
        sale = response.json()["data"]
    return sale


def _issue(
    client,
    tenant,
    sale_id,
    issuer,
    *,
    filename="receipt.pdf",
    content=PDF,
    content_type="application/pdf",
    number=" 0001-00000001 ",
    document_type=None,
    code=None,
    headers=None,
):
    resolved_type = document_type or issuer["service_document_type"] or issuer[
        "product_document_type"
    ]
    resolved_code = code or issuer["service_document_code"] or issuer[
        "product_document_code"
    ]
    return client.post(
        f"/api/v1/sales/{sale_id}/fiscal-document",
        headers=headers or _headers(tenant),
        data={
            "fiscal_issuer_id": issuer["id"],
            "document_type": resolved_type,
            "document_code": resolved_code,
            "document_number": number,
            "issue_date": "2026-08-09",
        },
        files={"file": (filename, content, content_type)},
    )


@pytest.mark.parametrize("status", ["draft", "cancelled", "reversed"])
def test_initial_document_requires_confirmed_sale(
    client, db_session, tenant, status
):
    _storage(client)
    issuer = _issuer(client, tenant, _user(db_session, tenant))
    sale = _sale(client, tenant, status=status)
    response = _issue(client, tenant, sale["id"], issuer)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "sale_fiscal_document_status_not_allowed"


@pytest.mark.parametrize(
    ("filename", "content", "content_type"),
    [
        ("receipt.pdf", PDF, "application/pdf"),
        ("receipt.JPG", JPEG, "image/jpeg"),
        ("receipt.png", PNG, "image/png"),
    ],
)
def test_issue_supported_files_and_private_download(
    client, db_session, tenant, filename, content, content_type
):
    storage = _storage(client)
    issuer = _issuer(client, tenant, _user(db_session, tenant))
    sale = _sale(client, tenant)
    response = _issue(
        client,
        tenant,
        sale["id"],
        issuer,
        filename=filename,
        content=content,
        content_type=content_type,
    )
    assert response.status_code == 201, response.text
    document = response.json()["data"]
    assert document["document_number"] == "0001-00000001"
    assert document["total_ars_snapshot"] == sale["total_ars"]
    assert len(document["sha256"]) == 64
    assert "storage_key" not in document and "bucket_name" not in document
    assert storage.uploads[0].startswith(
        f"tenants/{tenant.id}/sales/{sale['id']}/fiscal-documents/"
    )
    inline = client.get(
        f"/api/v1/sales/{sale['id']}/fiscal-document/file",
        headers=_headers(tenant),
    )
    download = client.get(
        f"/api/v1/sales/{sale['id']}/fiscal-document/file?download=true",
        headers=_headers(tenant),
    )
    assert inline.content == content and inline.headers["cache-control"] == "private, no-store"
    assert inline.headers["content-disposition"].startswith("inline;")
    assert download.headers["content-disposition"].startswith("attachment;")


@pytest.mark.parametrize("missing", ["document_number", "issue_date", "file"])
def test_required_document_fields_and_file(client, db_session, tenant, missing):
    storage = _storage(client)
    issuer = _issuer(client, tenant, _user(db_session, tenant))
    sale = _sale(client, tenant)
    data = {
        "fiscal_issuer_id": issuer["id"],
        "document_type": "receipt_c",
        "document_code": "015",
        "document_number": "0001-1",
        "issue_date": "2026-08-09",
    }
    files = {"file": ("receipt.pdf", PDF, "application/pdf")}
    if missing == "file":
        files = None
    else:
        data.pop(missing)
    response = client.post(
        f"/api/v1/sales/{sale['id']}/fiscal-document",
        headers=_headers(tenant),
        data=data,
        files=files,
    )
    assert response.status_code == 422
    assert storage.uploads == []


@pytest.mark.parametrize(
    ("kind", "issuer_mode", "same_mixed", "expected"),
    [
        ("service", "service", False, 201),
        ("product", "product", False, 201),
        ("mixed", "mixed", False, 409),
        ("mixed", "mixed", True, 201),
        ("service", "product", False, 409),
        ("product", "service", False, 409),
    ],
)
def test_issuer_eligibility_by_sale_composition(
    client, db_session, tenant, kind, issuer_mode, same_mixed, expected
):
    _storage(client)
    issuer = _issuer(
        client,
        tenant,
        _user(db_session, tenant),
        mode=issuer_mode,
        same_mixed=same_mixed,
    )
    sale = _sale(client, tenant, kind=kind)
    response = _issue(client, tenant, sale["id"], issuer)
    assert response.status_code == expected, response.text
    if kind == "mixed" and not same_mixed:
        assert response.json()["error"]["code"] == "sale_fiscal_document_mixed_not_supported"


@pytest.mark.parametrize(
    ("filename", "content", "content_type", "expected_status"),
    [
        ("malware.exe", PDF, "application/pdf", 422),
        ("receipt.pdf", PDF, "image/png", 422),
        ("receipt.pdf", b"not-pdf", "application/pdf", 422),
        ("receipt.pdf", b"", "application/pdf", 422),
        ("receipt.pdf", b"%PDF-" + b"x" * (10 * 1024 * 1024), "application/pdf", 413),
    ],
)
def test_invalid_files_are_rejected_before_storage(
    client, db_session, tenant, filename, content, content_type, expected_status
):
    storage = _storage(client)
    issuer = _issuer(client, tenant, _user(db_session, tenant))
    sale = _sale(client, tenant)
    response = _issue(
        client,
        tenant,
        sale["id"],
        issuer,
        filename=filename,
        content=content,
        content_type=content_type,
    )
    assert response.status_code == expected_status
    assert storage.uploads == []


def test_inactive_and_cross_tenant_issuers_are_not_selectable(
    client, db_session, tenant, other_tenant
):
    _storage(client)
    issuer = _issuer(client, tenant, _user(db_session, tenant))
    sale = _sale(client, tenant)
    client.patch(
        f"/api/v1/fiscal-issuers/{issuer['id']}",
        headers=_headers(tenant),
        json={"is_active": False},
    )
    assert _issue(client, tenant, sale["id"], issuer).status_code == 409
    foreign_user = _user(db_session, other_tenant, email="other-fiscal@example.com")
    foreign_issuer = _issuer(client, other_tenant, foreign_user)
    assert _issue(client, tenant, sale["id"], foreign_issuer).status_code == 404


def test_number_uniqueness_is_scoped_by_tenant_issuer_and_type(
    client, db_session, tenant, other_tenant
):
    _storage(client)
    issuer = _issuer(client, tenant, _user(db_session, tenant))
    first = _sale(client, tenant)
    second = _sale(client, tenant)
    assert _issue(client, tenant, first["id"], issuer).status_code == 201
    duplicate = _issue(client, tenant, second["id"], issuer)
    assert duplicate.status_code == 409
    other_user = _user(db_session, other_tenant, email="tenant-b-fiscal@example.com")
    other_issuer = _issuer(client, other_tenant, other_user)
    other_sale = _sale(client, other_tenant)
    assert _issue(client, other_tenant, other_sale["id"], other_issuer).status_code == 201


def test_replace_file_preserves_history_and_metadata_correction(
    client, db_session, tenant
):
    storage = _storage(client)
    issuer = _issuer(client, tenant, _user(db_session, tenant))
    sale = _sale(client, tenant)
    created = _issue(client, tenant, sale["id"], issuer).json()["data"]
    response = client.patch(
        f"/api/v1/sales/{sale['id']}/fiscal-document",
        headers=_headers(tenant),
        data={"document_number": "0001-00000002", "issue_date": "2026-08-10"},
        files={"file": ("replacement.png", PNG, "image/png")},
    )
    assert response.status_code == 200, response.text
    updated = response.json()["data"]
    assert updated["id"] == created["id"]
    assert updated["document_number"] == "0001-00000002"
    assert updated["original_filename"] == "replacement.png"
    assert len(updated["file_history"]) == 1
    assert updated["file_history"][0]["original_filename"] == "receipt.pdf"
    assert len(storage.uploads) == 2 and storage.deletes == []
    assert db_session.scalar(select(func.count()).select_from(SaleFiscalDocumentFileVersion)) == 1


def test_identical_file_update_does_not_create_version(client, db_session, tenant):
    storage = _storage(client)
    issuer = _issuer(client, tenant, _user(db_session, tenant))
    sale = _sale(client, tenant)
    _issue(client, tenant, sale["id"], issuer)
    response = client.patch(
        f"/api/v1/sales/{sale['id']}/fiscal-document",
        headers=_headers(tenant),
        files={"file": ("same.pdf", PDF, "application/pdf")},
    )
    assert response.status_code == 200
    assert len(storage.uploads) == 1
    assert response.json()["data"]["file_history"] == []


def test_replacement_failure_preserves_previous_file_and_compensates(
    client, db_session, tenant, monkeypatch
):
    storage = _storage(client)
    issuer = _issuer(client, tenant, _user(db_session, tenant))
    sale = _sale(client, tenant)
    original = _issue(client, tenant, sale["id"], issuer).json()["data"]

    def fail_save(self, document):
        raise RuntimeError("database failed")

    monkeypatch.setattr(SaleFiscalDocumentRepository, "save", fail_save)
    response = client.patch(
        f"/api/v1/sales/{sale['id']}/fiscal-document",
        headers=_headers(tenant),
        files={"file": ("replacement.png", PNG, "image/png")},
    )
    assert response.status_code == 500
    assert storage.deletes == [storage.uploads[-1]]
    db_session.expire_all()
    current = db_session.scalar(select(SaleFiscalDocument))
    assert current.original_filename == original["original_filename"]
    assert current.sha256 == original["sha256"]
    assert db_session.scalar(select(func.count()).select_from(SaleFiscalDocumentFileVersion)) == 0


@pytest.mark.parametrize("tamper", ["storage_key", "content"])
def test_download_rejects_storage_mismatch_or_corruption(
    client, db_session, tenant, tamper
):
    storage = _storage(client)
    issuer = _issuer(client, tenant, _user(db_session, tenant))
    sale = _sale(client, tenant)
    _issue(client, tenant, sale["id"], issuer)
    model = db_session.scalar(select(SaleFiscalDocument))
    if tamper == "storage_key":
        model.storage_key = "tenants/foreign/sales/leak/document.pdf"
        db_session.commit()
        expected = "sale_fiscal_document_storage_mismatch"
    else:
        storage.objects[model.storage_key] = b"%PDF-corrupted"
        expected = "sale_fiscal_document_integrity_error"
    response = client.get(
        f"/api/v1/sales/{sale['id']}/fiscal-document/file",
        headers=_headers(tenant),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == expected


def test_storage_and_database_failures_compensate_without_document(
    client, db_session, tenant, monkeypatch
):
    storage = _storage(client)
    issuer = _issuer(client, tenant, _user(db_session, tenant))
    first_sale = _sale(client, tenant)
    storage.fail_upload = True
    failed_upload = _issue(client, tenant, first_sale["id"], issuer)
    assert failed_upload.status_code == 502
    assert storage.deletes == storage.uploads
    storage.fail_upload = False
    second_sale = _sale(client, tenant)

    def fail_create(self, document):
        raise RuntimeError("database failed")

    monkeypatch.setattr(SaleFiscalDocumentRepository, "create", fail_create)
    failed_db = _issue(
        client, tenant, second_sale["id"], issuer, number="0001-00000002"
    )
    assert failed_db.status_code == 500
    assert storage.deletes == storage.uploads
    assert db_session.scalar(select(func.count()).select_from(SaleFiscalDocument)) == 0


def test_cross_tenant_document_metadata_file_and_mutation_are_hidden(
    client, db_session, tenant, other_tenant
):
    _storage(client)
    issuer = _issuer(client, tenant, _user(db_session, tenant))
    sale = _sale(client, tenant)
    _issue(client, tenant, sale["id"], issuer)
    base = f"/api/v1/sales/{sale['id']}/fiscal-document"
    assert client.get(base, headers=_headers(other_tenant)).status_code == 404
    assert client.get(f"{base}/file", headers=_headers(other_tenant)).status_code == 404
    assert client.patch(
        base,
        headers=_headers(other_tenant),
        data={"document_number": "X"},
    ).status_code == 404


def test_fiscal_status_filter_and_reversal_requires_attention(
    client, db_session, tenant
):
    _storage(client)
    issuer = _issuer(client, tenant, _user(db_session, tenant))
    pending = _sale(client, tenant)
    documented = _sale(client, tenant)
    assert pending["fiscal_status"] == "pending"
    _issue(client, tenant, documented["id"], issuer)
    assert [
        row["id"]
        for row in client.get(
            "/api/v1/sales?fiscal_status=pending", headers=_headers(tenant)
        ).json()["data"]
    ] == [pending["id"]]
    documented_rows = client.get(
        "/api/v1/sales?fiscal_status=documented", headers=_headers(tenant)
    ).json()["data"]
    assert [row["id"] for row in documented_rows] == [documented["id"]]
    assert client.post(
        f"/api/v1/sales/{documented['id']}/reverse",
        headers=_headers(tenant),
        json={"reason": "Corrección operativa"},
    ).status_code == 200
    detail = client.get(
        f"/api/v1/sales/{documented['id']}", headers=_headers(tenant)
    ).json()["data"]
    assert detail["status"] == "reversed"
    assert detail["fiscal_status"] == "requires_attention"
    assert detail["fiscal_document"] is not None
    attention = client.get(
        "/api/v1/sales?fiscal_status=requires_attention", headers=_headers(tenant)
    ).json()["data"]
    assert [row["id"] for row in attention] == [documented["id"]]


def test_operational_actor_is_distinct_from_issuer_and_snapshots_survive_changes(
    client, db_session, tenant, monkeypatch
):
    import app.core.tenant as tenant_core

    _storage(client)
    issuer_user = _user(db_session, tenant, email="issuer-user@example.com", name="Emisora")
    actor = _user(db_session, tenant, email="actor@example.com", name="Operador")
    issuer = _issuer(client, tenant, issuer_user)
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    monkeypatch.setattr(tenant_core, "verify_id_token", lambda token: {"email": token})
    created = client.post(
        "/api/v1/sales",
        headers=_auth_headers(actor.email),
        json={
            "owner_id": None,
            "patient_id": None,
            "sale_date": "2026-08-09",
            "items": [{
                "line_type": "service",
                "description": "Consulta",
                "quantity": "1",
                "unit_price_ars": "50",
                "discount_percentage": "0",
            }],
        },
    )
    assert created.status_code == 201, created.text
    sale = client.post(
        f"/api/v1/sales/{created.json()['data']['id']}/confirm",
        headers=_auth_headers(actor.email),
        json={"confirm": True},
    ).json()["data"]
    assert sale["created_by_user_id"] == str(actor.id)
    assert sale["confirmed_by_user_id"] == str(actor.id)
    response = _issue(
        client,
        tenant,
        sale["id"],
        issuer,
        headers=_auth_headers(actor.email),
    )
    assert response.status_code == 201, response.text
    document = response.json()["data"]
    assert document["issuer_user_id_snapshot"] == str(issuer_user.id)
    assert document["uploaded_by_user_id"] == str(actor.id)
    assert document["uploaded_by_user_name"] == "Operador"
    after_document = client.get(
        f"/api/v1/sales/{sale['id']}", headers=_auth_headers(actor.email)
    ).json()["data"]
    assert after_document["created_by_user_id"] == str(actor.id)
    assert after_document["confirmed_by_user_id"] == str(actor.id)
    client.patch(
        f"/api/v1/fiscal-issuers/{issuer['id']}",
        headers=_auth_headers(actor.email),
        json={"display_name": "Nuevo nombre", "tax_id": "30-99999999-9"},
    )
    stable = client.get(
        f"/api/v1/sales/{sale['id']}/fiscal-document",
        headers=_auth_headers(actor.email),
    ).json()["data"]
    assert stable["issuer_name_snapshot"] == "Dra. Fiscal"
    assert stable["issuer_tax_id_snapshot"] == "20-11111111-1"
    replaced = client.patch(
        f"/api/v1/sales/{sale['id']}/fiscal-document",
        headers=_auth_headers(actor.email),
        files={"file": ("replacement.png", PNG, "image/png")},
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["data"]["issuer_name_snapshot"] == "Dra. Fiscal"
    assert replaced.json()["data"]["issuer_tax_id_snapshot"] == "20-11111111-1"


@pytest.mark.parametrize(
    ("method", "suffix"),
    [
        ("get", ""),
        ("get", "/file"),
        ("post", ""),
        ("patch", ""),
    ],
)
def test_document_endpoints_require_authentication(
    client, monkeypatch, method, suffix
):
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    path = f"/api/v1/sales/{uuid.uuid4()}/fiscal-document{suffix}"
    response = getattr(client, method)(path)
    assert response.status_code == 401

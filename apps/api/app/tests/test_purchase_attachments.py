import uuid

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.purchase import Purchase
from app.models.purchase_attachment import PurchaseAttachment
from app.models.user import User
from app.repositories.purchase_attachment import PurchaseAttachmentRepository
from app.services.storage import get_purchase_attachment_storage_service


PDF = b"%PDF-1.7\nprivate receipt"
JPEG = b"\xff\xd8\xff\xe0jpeg receipt"
PNG = b"\x89PNG\r\n\x1a\npng receipt"


class FakeStorage:
    bucket_name = "purchase-test-bucket"

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.uploads: list[str] = []
        self.deletes: list[str] = []
        self.fail_upload = False

    def upload_clinical_file(self, *, object_path, content, content_type) -> None:
        del content_type
        if self.fail_upload:
            self.objects[object_path] = content
            self.uploads.append(object_path)
            raise RuntimeError("storage unavailable")
        self.objects[object_path] = content
        self.uploads.append(object_path)

    def delete_clinical_file(self, *, bucket_name, object_path) -> None:
        assert bucket_name == self.bucket_name
        self.objects.pop(object_path, None)
        self.deletes.append(object_path)

    def download_object_bytes(self, *, bucket_name, object_path) -> bytes:
        assert bucket_name == self.bucket_name
        return self.objects[object_path]


def _headers(tenant) -> dict[str, str]:
    return {"X-Tenant-Id": str(tenant.id)}


def _storage(client) -> FakeStorage:
    storage = FakeStorage()
    client.app.dependency_overrides[get_purchase_attachment_storage_service] = lambda: storage
    return storage


def _create_item(client, tenant, name="Alimento") -> dict:
    response = client.post(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        json={"name": name, "category": "food", "unit": "unit", "minimum_stock": "0"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _create_purchase(client, tenant, *, name="Proveedor comprobante") -> dict:
    item = _create_item(client, tenant, f"Producto {name}")
    supplier_response = client.post(
        "/api/v1/suppliers",
        headers=_headers(tenant),
        json={"name": name},
    )
    assert supplier_response.status_code == 201, supplier_response.text
    supplier = supplier_response.json()["data"]
    response = client.post(
        "/api/v1/purchases",
        headers=_headers(tenant),
        json={
            "supplier_id": supplier["id"],
            "purchase_date": "2026-08-09",
            "document_type": "invoice",
            "document_number": "FAC-23",
            "items": [
                {
                    "inventory_item_id": item["id"],
                    "quantity": "2",
                    "unit_price_without_tax_ars": "100",
                    "tax_rate_percentage": "21",
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _upload(client, tenant, purchase_id, *, filename="factura.pdf", content=PDF, content_type="application/pdf"):
    return client.post(
        f"/api/v1/purchases/{purchase_id}/attachment",
        headers=_headers(tenant),
        files={"file": (filename, content, content_type)},
    )


def test_purchase_starts_pending_and_list_exposes_status(client, tenant):
    _storage(client)
    purchase = _create_purchase(client, tenant)

    assert purchase["attachment_status"] == "pending"
    assert purchase["attachment"] is None
    assert purchase["attachment_history"] == []
    listing = client.get("/api/v1/purchases", headers=_headers(tenant)).json()["data"]
    assert listing[0]["attachment_status"] == "pending"


@pytest.mark.parametrize(
    ("filename", "content", "content_type"),
    [
        ("factura.pdf", PDF, "application/pdf"),
        ("foto.JPG", JPEG, "image/jpeg"),
        ("ticket.png", PNG, "image/png"),
    ],
)
def test_upload_and_authenticated_download_support_allowed_formats(
    client, db_session, tenant, filename, content, content_type
):
    storage = _storage(client)
    purchase = _create_purchase(client, tenant)

    response = _upload(
        client,
        tenant,
        purchase["id"],
        filename=f"../unsafe/{filename}",
        content=content,
        content_type=content_type,
    )

    assert response.status_code == 200, response.text
    attachment = response.json()["data"]
    assert attachment["original_filename"] == filename
    assert attachment["content_type"] == content_type
    assert attachment["size_bytes"] == len(content)
    assert len(attachment["sha256"]) == 64
    assert "bucket_name" not in attachment
    assert "storage_key" not in attachment
    row = db_session.get(PurchaseAttachment, uuid.UUID(attachment["id"]))
    assert row.storage_key.startswith(
        f"tenants/{tenant.id}/purchases/{purchase['id']}/attachments/{attachment['id']}/"
    )
    assert filename not in row.storage_key
    assert storage.objects[row.storage_key] == content

    inline = client.get(
        f"/api/v1/purchases/{purchase['id']}/attachment", headers=_headers(tenant)
    )
    downloaded = client.get(
        f"/api/v1/purchases/{purchase['id']}/attachment?download=true",
        headers=_headers(tenant),
    )
    assert inline.status_code == 200
    assert inline.content == content
    assert inline.headers["content-type"] == content_type
    assert inline.headers["content-disposition"].startswith("inline;")
    assert downloaded.headers["content-disposition"].startswith("attachment;")
    assert downloaded.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize(
    ("filename", "content", "content_type", "code"),
    [
        ("malware.exe", PDF, "application/pdf", "purchase_attachment_extension_not_allowed"),
        ("factura.pdf", PDF, "image/png", "purchase_attachment_content_type_mismatch"),
        ("factura.pdf", b"not a pdf", "application/pdf", "purchase_attachment_signature_mismatch"),
        ("factura.pdf", b"", "application/pdf", "purchase_attachment_empty"),
    ],
)
def test_upload_rejects_invalid_extension_mime_signature_and_empty_file(
    client, tenant, filename, content, content_type, code
):
    storage = _storage(client)
    purchase = _create_purchase(client, tenant)

    response = _upload(
        client,
        tenant,
        purchase["id"],
        filename=filename,
        content=content,
        content_type=content_type,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == code
    assert storage.uploads == []


def test_upload_rejects_more_than_ten_megabytes(client, tenant):
    storage = _storage(client)
    purchase = _create_purchase(client, tenant)

    response = _upload(
        client,
        tenant,
        purchase["id"],
        content=b"%PDF-" + b"x" * (10 * 1024 * 1024),
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "purchase_attachment_too_large"
    assert storage.uploads == []


def test_identical_upload_is_idempotent_and_replacement_preserves_history(
    client, db_session, tenant
):
    storage = _storage(client)
    purchase = _create_purchase(client, tenant)
    first = _upload(client, tenant, purchase["id"])

    identical = _upload(client, tenant, purchase["id"], filename="same-content.pdf")
    replacement = _upload(
        client,
        tenant,
        purchase["id"],
        filename="replacement.png",
        content=PNG,
        content_type="image/png",
    )

    assert identical.status_code == 200
    assert identical.json()["data"]["id"] == first.json()["data"]["id"]
    assert identical.json()["meta"]["idempotent"] is True
    assert replacement.status_code == 200
    assert len(storage.uploads) == 2
    assert storage.deletes == []
    db_session.expire_all()
    rows = list(
        db_session.scalars(
            select(PurchaseAttachment).where(
                PurchaseAttachment.purchase_id == uuid.UUID(purchase["id"])
            )
        ).all()
    )
    assert len(rows) == 2
    assert sum(row.is_active for row in rows) == 1
    detail = client.get(
        f"/api/v1/purchases/{purchase['id']}", headers=_headers(tenant)
    ).json()["data"]
    assert detail["attachment"]["original_filename"] == "replacement.png"
    assert detail["attachment_history"][0]["original_filename"] == "factura.pdf"
    assert detail["attachment_history"][0]["replaced_at"] is not None


def test_upload_and_replacement_record_tenant_users(
    client, db_session, tenant, monkeypatch
):
    import app.core.tenant as tenant_core

    storage = _storage(client)
    purchase = _create_purchase(client, tenant)
    first_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="first-buyer@example.com",
        full_name="Primera compradora",
        is_active=True,
    )
    replacement_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="replacement-buyer@example.com",
        full_name="Comprador reemplazo",
        is_active=True,
    )
    db_session.add_all([first_user, replacement_user])
    db_session.commit()
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    monkeypatch.setattr(tenant_core, "verify_id_token", lambda token: {"email": token})

    first = client.post(
        f"/api/v1/purchases/{purchase['id']}/attachment",
        headers={"Authorization": f"Bearer {first_user.email}"},
        files={"file": ("factura.pdf", PDF, "application/pdf")},
    )
    replacement = client.post(
        f"/api/v1/purchases/{purchase['id']}/attachment",
        headers={"Authorization": f"Bearer {replacement_user.email}"},
        files={"file": ("ticket.png", PNG, "image/png")},
    )

    assert first.status_code == 200
    assert first.json()["data"]["uploaded_by_user_id"] == str(first_user.id)
    assert first.json()["data"]["uploaded_by_user_name"] == "Primera compradora"
    assert replacement.status_code == 200
    assert replacement.json()["data"]["uploaded_by_user_id"] == str(replacement_user.id)
    old = db_session.get(PurchaseAttachment, uuid.UUID(first.json()["data"]["id"]))
    assert old.replaced_by_user_id == replacement_user.id
    assert len(storage.uploads) == 2


def test_storage_failure_keeps_previous_attachment_active(client, db_session, tenant):
    storage = _storage(client)
    purchase = _create_purchase(client, tenant)
    first = _upload(client, tenant, purchase["id"]).json()["data"]
    storage.fail_upload = True

    response = _upload(
        client,
        tenant,
        purchase["id"],
        filename="replacement.png",
        content=PNG,
        content_type="image/png",
    )

    assert response.status_code == 502
    db_session.expire_all()
    active = db_session.scalar(
        select(PurchaseAttachment).where(PurchaseAttachment.is_active.is_(True))
    )
    assert str(active.id) == first["id"]
    assert db_session.scalar(select(func.count()).select_from(PurchaseAttachment)) == 1
    assert len(storage.uploads) == 2
    assert storage.deletes == [storage.uploads[-1]]
    assert list(storage.objects) == [storage.uploads[0]]


def test_database_failure_compensates_new_storage_object(
    client, db_session, tenant, monkeypatch
):
    storage = _storage(client)
    purchase = _create_purchase(client, tenant)

    def fail_create(self, attachment):
        raise RuntimeError("database write failed")

    monkeypatch.setattr(PurchaseAttachmentRepository, "create", fail_create)
    response = _upload(client, tenant, purchase["id"])

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "purchase_attachment_persistence_failed"
    assert len(storage.uploads) == 1
    assert storage.deletes == storage.uploads
    assert storage.objects == {}
    assert db_session.scalar(select(func.count()).select_from(PurchaseAttachment)) == 0


def test_cross_tenant_access_is_not_found_and_filters_are_tenant_scoped(
    client, tenant, other_tenant
):
    storage = _storage(client)
    attached = _create_purchase(client, tenant, name="Con archivo")
    pending = _create_purchase(client, tenant, name="Pendiente")
    _upload(client, tenant, attached["id"])

    foreign_upload = _upload(client, other_tenant, attached["id"])
    foreign_download = client.get(
        f"/api/v1/purchases/{attached['id']}/attachment",
        headers=_headers(other_tenant),
    )
    attached_filter = client.get(
        "/api/v1/purchases",
        headers=_headers(tenant),
        params={"attachment_status": "attached"},
    ).json()["data"]
    pending_filter = client.get(
        "/api/v1/purchases",
        headers=_headers(tenant),
        params={"attachment_status": "pending"},
    ).json()["data"]
    foreign_filter = client.get(
        "/api/v1/purchases",
        headers=_headers(other_tenant),
        params={"attachment_status": "attached"},
    ).json()["data"]

    assert foreign_upload.status_code == 404
    assert foreign_download.status_code == 404
    assert len(storage.uploads) == 1
    assert [row["id"] for row in attached_filter] == [attached["id"]]
    assert [row["id"] for row in pending_filter] == [pending["id"]]
    assert foreign_filter == []


@pytest.mark.parametrize("purchase_status", ["draft", "received", "reversed", "cancelled"])
def test_attachment_is_allowed_in_every_functional_purchase_status(
    client, db_session, tenant, purchase_status
):
    _storage(client)
    purchase = _create_purchase(client, tenant)
    row = db_session.get(Purchase, uuid.UUID(purchase["id"]))
    row.status = purchase_status
    db_session.commit()

    response = _upload(client, tenant, purchase["id"])

    assert response.status_code == 200, response.text


def test_attachment_does_not_change_stock_movements_or_purchase_status(
    client, db_session, tenant
):
    _storage(client)
    purchase = _create_purchase(client, tenant)
    purchase_row = db_session.get(Purchase, uuid.UUID(purchase["id"]))
    item_id = purchase_row.items[0].inventory_item_id
    stock_before = db_session.get(InventoryItem, item_id).current_stock
    movement_count_before = db_session.scalar(select(func.count()).select_from(InventoryMovement))

    response = _upload(client, tenant, purchase["id"])

    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.get(Purchase, uuid.UUID(purchase["id"])).status == "draft"
    assert db_session.get(InventoryItem, item_id).current_stock == stock_before
    assert db_session.scalar(select(func.count()).select_from(InventoryMovement)) == movement_count_before


def test_attachment_endpoints_require_authentication(client, tenant, monkeypatch):
    _storage(client)
    purchase = _create_purchase(client, tenant)
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()

    upload = client.post(
        f"/api/v1/purchases/{purchase['id']}/attachment",
        files={"file": ("factura.pdf", PDF, "application/pdf")},
    )
    download = client.get(f"/api/v1/purchases/{purchase['id']}/attachment")

    assert upload.status_code == 401
    assert download.status_code == 401

import uuid

import pytest

from app.core.config import get_settings
from app.models.user import User


def _headers(tenant):
    return {"X-Tenant-Id": str(tenant.id)}


def _user(db, tenant, *, email="issuer@example.com", name="Dra. Emisora"):
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


def _payload(user_id, **changes):
    payload = {
        "user_id": str(user_id),
        "display_name": "  Dra. Emisora  ",
        "tax_id": "  20-12345678-9  ",
        "can_issue_service_receipt_c": True,
        "can_issue_product_invoice_c": False,
        "service_document_type": "receipt_c",
        "service_document_code": "015",
        "product_document_type": None,
        "product_document_code": None,
    }
    payload.update(changes)
    return payload


def _create(client, tenant, user_id, **changes):
    return client.post(
        "/api/v1/fiscal-issuers",
        headers=_headers(tenant),
        json=_payload(user_id, **changes),
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [
            ("get", "/api/v1/fiscal-issuers"),
            ("post", "/api/v1/fiscal-issuers"),
            ("get", f"/api/v1/fiscal-issuers/{uuid.uuid4()}"),
            ("patch", f"/api/v1/fiscal-issuers/{uuid.uuid4()}"),
    ],
)
def test_fiscal_issuer_endpoints_require_authentication(
    client, monkeypatch, method, path
):
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    response = (
        getattr(client, method)(path)
        if method == "get"
        else getattr(client, method)(path, json={})
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "configuration",
    [
        {},
        {
            "can_issue_service_receipt_c": False,
            "service_document_type": None,
            "service_document_code": None,
            "can_issue_product_invoice_c": True,
            "product_document_type": "invoice_c",
            "product_document_code": "011",
        },
        {
            "can_issue_product_invoice_c": True,
            "product_document_type": "receipt_c",
            "product_document_code": "015",
        },
    ],
)
def test_create_supported_issuer_configurations(
    client, db_session, tenant, configuration
):
    user = _user(db_session, tenant)
    response = _create(client, tenant, user.id, **configuration)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["display_name"] == "Dra. Emisora"
    assert data["tax_id"] == "20-12345678-9"
    assert data["user_name"] == user.full_name


@pytest.mark.parametrize(
    "changes",
    [
        {
            "can_issue_service_receipt_c": False,
            "service_document_type": None,
            "service_document_code": None,
        },
        {"service_document_type": None},
        {
            "can_issue_service_receipt_c": False,
            "service_document_type": "receipt_c",
        },
        {"display_name": "   "},
        {"tax_id": ""},
    ],
)
def test_reject_invalid_issuer_configurations(
    client, db_session, tenant, changes
):
    user = _user(db_session, tenant)
    response = _create(client, tenant, user.id, **changes)
    assert response.status_code == 422


def test_one_configuration_per_tenant_user(client, db_session, tenant):
    user = _user(db_session, tenant)
    assert _create(client, tenant, user.id).status_code == 201
    duplicate = _create(client, tenant, user.id)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "fiscal_issuer_user_duplicate"


def test_cross_tenant_user_and_resource_are_hidden(
    client, db_session, tenant, other_tenant
):
    user = _user(db_session, tenant)
    foreign_user = _user(
        db_session, other_tenant, email="foreign@example.com", name="Ajena"
    )
    issuer = _create(client, tenant, user.id).json()["data"]
    assert _create(client, tenant, foreign_user.id).status_code == 404
    assert (
        client.get(
            f"/api/v1/fiscal-issuers/{issuer['id']}",
            headers=_headers(other_tenant),
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/fiscal-issuers/{issuer['id']}",
            headers=_headers(other_tenant),
            json={"is_active": False},
        ).status_code
        == 404
    )
    assert client.get(
        "/api/v1/fiscal-issuers", headers=_headers(other_tenant)
    ).json()["data"] == []


def test_update_activation_capabilities_and_active_filter(
    client, db_session, tenant
):
    user = _user(db_session, tenant)
    issuer = _create(client, tenant, user.id).json()["data"]
    updated = client.patch(
        f"/api/v1/fiscal-issuers/{issuer['id']}",
        headers=_headers(tenant),
        json={
            "display_name": "Nombre fiscal nuevo",
            "is_active": False,
            "can_issue_service_receipt_c": False,
            "can_issue_product_invoice_c": True,
            "product_document_type": "invoice_c",
            "product_document_code": "011",
        },
    )
    assert updated.status_code == 200, updated.text
    data = updated.json()["data"]
    assert data["display_name"] == "Nombre fiscal nuevo"
    assert data["is_active"] is False
    assert data["service_document_type"] is None
    assert client.get(
        "/api/v1/fiscal-issuers?active_only=true",
        headers=_headers(tenant),
    ).json()["data"] == []


def test_update_rejects_foreign_or_duplicate_user(
    client, db_session, tenant, other_tenant
):
    first = _user(db_session, tenant, email="one@example.com")
    second = _user(db_session, tenant, email="two@example.com")
    foreign = _user(db_session, other_tenant, email="other@example.com")
    first_issuer = _create(client, tenant, first.id).json()["data"]
    _create(client, tenant, second.id)
    duplicate = client.patch(
        f"/api/v1/fiscal-issuers/{first_issuer['id']}",
        headers=_headers(tenant),
        json={"user_id": str(second.id)},
    )
    cross = client.patch(
        f"/api/v1/fiscal-issuers/{first_issuer['id']}",
        headers=_headers(tenant),
        json={"user_id": str(foreign.id)},
    )
    assert duplicate.status_code == 409
    assert cross.status_code == 404

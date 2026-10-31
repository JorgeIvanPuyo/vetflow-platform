"""ARCA.1 opt-in configuration, real fiscal identities and historical contracts."""

import uuid

import pytest
from sqlalchemy import func, select

from app.models.fiscal_configuration import FiscalPolicy, FiscalPolicyReview
from app.models.sale_fiscal import FiscalIssuer
from app.models.user import User
from app.schemas.fiscal_issuer import normalize_cuit
from app.tests.role_helpers import clinic_admin_headers
from app.tests.test_sale_payments import _method, _pay, _sale


CONFIG = "/api/v1/fiscal/configuration"
VALID_CUIT = "20123456786"
OTHER_CUIT = "30712345671"


def _issuer(client, db, tenant, *, complete=True, **changes):
    user = User(id=uuid.uuid4(), tenant_id=tenant.id, email=f"arca-issuer-{uuid.uuid4()}@example.com", full_name="Emisor sintético", role="medico_veterinario", is_active=True)
    db.add(user)
    db.commit()
    payload = {
        "user_id": str(user.id), "display_name": "Emisor sintético",
        "tax_id": "ID histórico internacional", "can_issue_service_receipt_c": True,
        "service_document_type": "receipt_c", "service_document_code": "015",
    }
    if complete:
        payload.update(cuit=VALID_CUIT, legal_name="Razón fiscal sintética", tax_condition="Monotributo")
    payload.update(changes)
    response = client.post("/api/v1/fiscal-issuers", headers=clinic_admin_headers(tenant), json=payload)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _series(client, tenant, issuer, **changes):
    payload = {"fiscal_issuer_id": issuer["id"], "environment": "homologation", "point_of_sale": 1, "document_type": "receipt_c", "concept": 2, **changes}
    return client.post(f"{CONFIG}/series", headers=clinic_admin_headers(tenant), json=payload)


def _enable(client, tenant, **changes):
    response = client.patch(f"{CONFIG}/policy", headers=clinic_admin_headers(tenant), json={"enabled": True, **changes})
    assert response.status_code == 200, response.text
    return response.json()["data"]


@pytest.mark.parametrize("cuit", ["20-12345678-6", "20123456786", " 20 12345678 6 "])
def test_cuit_normalized_with_verified_check_digit(cuit):
    assert normalize_cuit(cuit) == VALID_CUIT


@pytest.mark.parametrize("cuit", ["20123456788", "00000000000", "2012345678", "201234567888", "CUIT20123456786", "٢٠١٢٣٤٥٦٧٨٦"])
def test_invalid_cuit_is_not_silently_accepted(cuit):
    with pytest.raises(ValueError):
        normalize_cuit(cuit)


def test_checksum_does_not_substitute_nine_when_verifier_would_be_ten():
    # 144 % 11 == 1: this ten-digit base has no decimal check digit.
    base = "2012345676"
    for digit in range(10):
        with pytest.raises(ValueError):
            normalize_cuit(base + str(digit))


@pytest.mark.parametrize("cuit", ["20123456786", "30712345671", "27123456780", "23123456785"])
def test_accepted_identities_satisfy_the_complete_modular_checksum(cuit):
    normalized = normalize_cuit(cuit)
    weights = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2, 1)
    assert sum(int(digit) * weight for digit, weight in zip(normalized, weights)) % 11 == 0


def test_historical_issuers_remain_without_fake_argentine_identity(client, db_session, tenant):
    issuer = _issuer(client, db_session, tenant, complete=False)
    assert issuer["tax_id"] == "ID histórico internacional"
    assert issuer["cuit"] is issuer["legal_name"] is issuer["tax_condition"] is None
    response = client.get(CONFIG, headers=clinic_admin_headers(tenant))
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["policy"]["enabled"] is False
    assert data["policy"]["payment_scope"] == "electronic_only"
    assert data["policy"]["production_blocked"] is True
    assert data["policy"]["external_emission_available"] is False
    assert data["issuers"][0]["id"] == issuer["id"]
    # Reading a default does not opt the tenant into Argentina or persist data.
    assert db_session.scalar(select(func.count(FiscalPolicy.id))) == 0


def test_identity_patch_validates_without_rewriting_legacy_tax_id(client, db_session, tenant):
    issuer = _issuer(client, db_session, tenant, complete=False)
    response = client.patch(f"/api/v1/fiscal-issuers/{issuer['id']}", headers=clinic_admin_headers(tenant), json={"cuit": "20-12345678-6", "legal_name": "  Razón legal  ", "tax_condition": "Monotributo"})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["cuit"] == VALID_CUIT
    assert response.json()["data"]["legal_name"] == "Razón legal"
    assert response.json()["data"]["tax_id"] == issuer["tax_id"]
    assert client.patch(f"/api/v1/fiscal-issuers/{issuer['id']}", headers=clinic_admin_headers(tenant), json={"cuit": "20123456789"}).status_code == 422
    assert client.get(f"/api/v1/fiscal-issuers/{issuer['id']}", headers=clinic_admin_headers(tenant)).json()["data"]["cuit"] == VALID_CUIT


def test_policy_review_records_actor_scope_date_and_preserves_prior_evidence(client, db_session, tenant):
    first = _enable(client, tenant, accounting_review_note="  Revisada con contabilidad: efectivo por separado  ")
    assert first["accounting_reviewed_at"]
    assert first["accounting_reviewed_by_user_id"]
    assert first["accounting_review_note"] == "Revisada con contabilidad: efectivo por separado"
    assert first["production_blocked"] is True
    changed = client.patch(f"{CONFIG}/policy", headers=clinic_admin_headers(tenant), json={"payment_scope": "all_payments"})
    assert changed.status_code == 200, changed.text
    data = changed.json()["data"]
    assert data["revision"] > first["revision"]
    assert data["accounting_reviewed_at"] is None
    assert data["accounting_reviewed_by_user_id"] is None
    assert data["accounting_review_note"] is None
    assert data["review_history"][0]["note"] == first["accounting_review_note"]
    assert data["review_history"][0]["payment_scope"] == "electronic_only"
    assert db_session.scalar(select(func.count(FiscalPolicyReview.id))) == 1


def test_incomplete_series_persists_as_pending_and_is_never_ready_to_emit(client, db_session, tenant):
    issuer = _issuer(client, db_session, tenant, complete=False)
    response = _series(client, tenant, issuer)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["cuit_snapshot"] is None
    assert data["readiness"] == "pending"
    assert len(data["pending_reasons"]) >= 3
    assert data["external_emission_available"] is False


def test_homologation_ready_means_configuration_complete_without_external_issuance(client, db_session, tenant):
    issuer = _issuer(client, db_session, tenant)
    _enable(client, tenant)
    response = _series(client, tenant, issuer, credential_reference="opaque://issuer-one/homologation")
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["readiness"] == "ready"
    assert data["pending_reasons"] == []
    assert data["cuit_snapshot"] == VALID_CUIT
    assert data["external_emission_available"] is False


def test_series_does_not_claim_readiness_for_incompatible_capability_or_inactive_responsible(client, db_session, tenant):
    issuer = _issuer(client, db_session, tenant)
    _enable(client, tenant)
    incompatible = _series(client, tenant, issuer, concept=1, credential_reference="opaque://credentials")
    assert incompatible.status_code == 201, incompatible.text
    assert incompatible.json()["data"]["readiness"] == "pending"
    assert any("productos" in reason for reason in incompatible.json()["data"]["pending_reasons"])
    record = db_session.scalar(select(FiscalIssuer).where(FiscalIssuer.tenant_id == tenant.id, FiscalIssuer.id == uuid.UUID(issuer["id"])))
    responsible = db_session.scalar(select(User).where(User.tenant_id == tenant.id, User.id == record.user_id))
    responsible.is_active = False
    db_session.commit()
    current = client.get(CONFIG, headers=clinic_admin_headers(tenant)).json()["data"]["series"][0]
    assert any("veterinario activo" in reason for reason in current["pending_reasons"])


def test_production_remains_blocked_and_accounting_review_is_explicit(client, db_session, tenant):
    issuer = _issuer(client, db_session, tenant)
    _enable(client, tenant)
    response = _series(client, tenant, issuer, environment="production", credential_reference="opaque://production")
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["readiness"] == "pending"
    assert any("contable" in reason for reason in data["pending_reasons"])
    assert any("producción permanece bloqueada" in reason for reason in data["pending_reasons"])
    _enable(client, tenant, accounting_review_note="Política revisada")
    data = client.get(CONFIG, headers=clinic_admin_headers(tenant)).json()["data"]["series"][0]
    assert data["readiness"] == "pending"
    assert not any("contable" in reason for reason in data["pending_reasons"])
    assert any("producción permanece bloqueada" in reason for reason in data["pending_reasons"])


def test_numbering_uniqueness_uses_real_cuit_and_concept_cannot_create_second_series(client, db_session, tenant):
    first = _issuer(client, db_session, tenant)
    alias = _issuer(client, db_session, tenant)
    assert _series(client, tenant, first).status_code == 201
    duplicate = _series(client, tenant, alias, concept=3)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "fiscal_series_duplicate"
    assert _series(client, tenant, first, concept=1).status_code == 409
    assert _series(client, tenant, first, environment="production").status_code == 201
    assert _series(client, tenant, first, point_of_sale=2).status_code == 201
    assert _series(client, tenant, first, document_type="invoice_c").status_code == 201


@pytest.mark.parametrize("changes", [{"environment": "testing"}, {"point_of_sale": 0}, {"point_of_sale": 100000}, {"concept": 4}, {"authorization_mode": "PASSWORD"}, {"credential_reference": "-----BEGIN PRIVATE KEY-----"}, {"credential_reference": "secret-password"}, {"caea_reference": "token=secret"}, {"private_key": "not-accepted"}])
def test_series_rejects_invalid_environment_pos_and_secret_payloads(client, db_session, tenant, changes):
    issuer = _issuer(client, db_session, tenant)
    assert _series(client, tenant, issuer, **changes).status_code == 422


def test_caea_has_only_nonsecret_reference_and_incomplete_configuration_is_pending(client, db_session, tenant):
    issuer = _issuer(client, db_session, tenant)
    _enable(client, tenant)
    response = _series(client, tenant, issuer, authorization_mode="CAEA", credential_reference="opaque://credentials")
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert any("CAEA" in reason for reason in data["pending_reasons"])
    updated = client.patch(f"{CONFIG}/series/{data['id']}", headers=clinic_admin_headers(tenant), json={"caea_reference": "opaque://caea/configuration"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["readiness"] == "ready"
    assert updated.json()["data"]["external_emission_available"] is False


def test_changed_identity_marks_series_pending_until_explicit_revision(client, db_session, tenant):
    issuer = _issuer(client, db_session, tenant)
    _enable(client, tenant)
    series = _series(client, tenant, issuer, credential_reference="opaque://credentials").json()["data"]
    response = client.patch(f"/api/v1/fiscal-issuers/{issuer['id']}", headers=clinic_admin_headers(tenant), json={"cuit": OTHER_CUIT})
    assert response.status_code == 200, response.text
    current = client.get(CONFIG, headers=clinic_admin_headers(tenant)).json()["data"]["series"][0]
    assert current["readiness"] == "pending"
    assert any("identidad" in reason for reason in current["pending_reasons"])
    reviewed = client.patch(f"{CONFIG}/series/{series['id']}", headers=clinic_admin_headers(tenant), json={})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["data"]["cuit_snapshot"] == OTHER_CUIT
    assert reviewed.json()["data"]["revision"] > series["revision"]


def test_mapping_is_tenant_scoped_and_does_not_rewrite_payment_snapshots(client, db_session, tenant, other_tenant):
    issuer = _issuer(client, db_session, tenant)
    foreign = _issuer(client, db_session, other_tenant)
    method = _method(client, tenant, label="Cuenta sintética", type="bank_transfer")
    sale = _sale(client, tenant)
    payment = _pay(client, tenant, sale, method, "10.00").json()["data"]
    path = f"/api/v1/payment-methods/{method['id']}"
    assert client.patch(path, headers=clinic_admin_headers(tenant), json={"suggested_fiscal_issuer_id": foreign["id"]}).status_code == 404
    response = client.patch(path, headers=clinic_admin_headers(tenant), json={"operational_reference": "Cuenta de cobro sintética", "suggested_fiscal_issuer_id": issuer["id"]})
    assert response.status_code == 200, response.text
    mapped = response.json()["data"]
    assert mapped["type"] == "bank_transfer"
    assert mapped["suggested_fiscal_issuer_id"] == issuer["id"]
    history = client.get(f"/api/v1/sales/{sale['id']}/payments", headers={"X-Tenant-Id": str(tenant.id)}).json()["data"]
    assert history[0] == payment
    # Optional mapping fields can be explicitly cleared.
    response = client.patch(path, headers=clinic_admin_headers(tenant), json={"operational_reference": None, "suggested_fiscal_issuer_id": None})
    assert response.status_code == 200
    assert response.json()["data"]["suggested_fiscal_issuer_id"] is None


def test_series_related_issuer_and_update_are_hidden_across_tenants(client, db_session, tenant, other_tenant):
    issuer = _issuer(client, db_session, tenant)
    foreign = _issuer(client, db_session, other_tenant)
    assert _series(client, tenant, foreign).status_code == 404
    series = _series(client, tenant, issuer).json()["data"]
    assert client.patch(f"{CONFIG}/series/{series['id']}", headers=clinic_admin_headers(other_tenant), json={"point_of_sale": 2}).status_code == 404
    assert client.patch(f"{CONFIG}/series/{series['id']}", headers=clinic_admin_headers(tenant), json={"fiscal_issuer_id": foreign["id"]}).status_code == 404
    foreign_config = client.get(CONFIG, headers=clinic_admin_headers(other_tenant)).json()["data"]
    assert foreign_config["series"] == []
    assert {row["id"] for row in foreign_config["issuers"]} == {foreign["id"]}


def test_same_real_identity_can_have_independent_series_in_two_tenants(client, db_session, tenant, other_tenant):
    local_issuer = _issuer(client, db_session, tenant)
    foreign_issuer = _issuer(client, db_session, other_tenant)
    local = _series(client, tenant, local_issuer)
    foreign = _series(client, other_tenant, foreign_issuer)
    assert local.status_code == foreign.status_code == 201
    visible = client.get(CONFIG, headers=clinic_admin_headers(tenant)).json()["data"]["series"]
    assert [row["id"] for row in visible] == [local.json()["data"]["id"]]

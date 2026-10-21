"""Server fiscal authorization, related IDs, and snapshot tenant boundaries."""
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.core.tenant import TenantContext
from app.models.fiscal_proposal import FiscalPaymentAllocation, FiscalProposal
from app.models.sale_fiscal import SaleFiscalDocument, SaleFiscalDocumentFileVersion
from app.schemas.fiscal_proposal import FiscalProposalApprove, FiscalProposalGenerate, FiscalProposalUpdate
from app.services.fiscal_configuration import FiscalConfigurationService
from app.services.fiscal_proposal import FiscalProposalService
from app.tests.fiscal_test_support import context_for, seed_fiscal_case


@pytest.fixture()
def fiscal_case(db_session):
    return seed_fiscal_case(db_session)


def _auth(actor):
    return {"X-User-Email": actor.email}


def _draft(db, case, *, context=None):
    proposals = FiscalProposalService(db).generate(
        context or case.context, case.sale_id,
        FiscalProposalGenerate(payment_ids=[case.payment_id], fiscal_series_id=case.series_id,
                               fiscal_description="Synthetic reviewed service"),
    )
    assert len(proposals) == 1
    return proposals[0]


def _approve(db, case, proposal, *, context=None, key="arca1-permissions"):
    return FiscalProposalService(db).approve(
        context or case.context, case.sale_id, proposal.id,
        FiscalProposalApprove(content_hash=proposal.content_hash, confirm_fiscal_identity=True),
        idempotency_key=key,
    )


def _manual_document(db, case):
    document = SaleFiscalDocument(
        tenant_id=case.tenant_id, sale_id=case.sale_id, fiscal_issuer_id=case.issuer_id,
        issuer_user_id_snapshot=case.actors["medico_veterinario"].id,
        issuer_name_snapshot="Synthetic retained issuer", issuer_tax_id_snapshot="Historical reference",
        source="manual", authorization_status="manual", document_type="receipt_c", document_code="015",
        document_number="synthetic-history", issue_date=date(2026, 10, 20), total_ars_snapshot=Decimal("100.00"),
        original_filename="own-history.pdf", bucket_name="synthetic", storage_key="synthetic/key",
        content_type="application/pdf", size_bytes=10, sha256="a" * 64,
        uploaded_by_user_id=case.context.user_id, uploaded_at=datetime.now(UTC), is_active=True,
    )
    db.add(document)
    db.commit()
    return document


@pytest.mark.parametrize("role,read_status,write_status", [
    ("clinic_admin", 200, 200), ("contador", 200, 200),
    ("medico_veterinario", 200, 403), ("secretaria", 200, 403), ("superadmin", 403, 403),
])
def test_configuration_permissions_enforced_by_api(client, fiscal_case, role, read_status, write_status):
    auth = _auth(fiscal_case.actors[role])
    assert client.get("/api/v1/fiscal/configuration", headers=auth).status_code == read_status
    assert client.patch("/api/v1/fiscal/configuration/policy", headers=auth,
                        json={"enabled": True}).status_code == write_status


@pytest.mark.parametrize("kind", ["missing_actor", "missing_role", "forged_role", "foreign_actor", "inactive_actor"])
def test_fiscal_context_never_grants_permissions_by_omission(db_session, fiscal_case, kind):
    context = fiscal_case.context
    if kind == "missing_actor":
        context = TenantContext(tenant_id=fiscal_case.tenant_id, role="clinic_admin")
    elif kind == "missing_role":
        context = replace(context, role=None)
    elif kind == "forged_role":
        context = replace(context_for(fiscal_case.actors["secretaria"]), role="clinic_admin")
    elif kind == "foreign_actor":
        foreign = seed_fiscal_case(db_session)
        context = replace(context, user_id=foreign.context.user_id)
    else:
        fiscal_case.actors["clinic_admin"].is_active = False
        db_session.commit()
    with pytest.raises(AppError) as error:
        FiscalConfigurationService(db_session).configuration(context)
    assert error.value.status_code == 403


def test_anonymous_development_tenant_has_no_fiscal_access(client, fiscal_case):
    auth = {"X-Tenant-Id": str(fiscal_case.tenant_id)}
    assert client.get("/api/v1/fiscal/configuration", headers=auth).status_code == 403
    assert client.get(f"/api/v1/sales/{fiscal_case.sale_id}/fiscal-review", headers=auth).status_code == 403
    assert client.get(f"/api/v1/sales/{fiscal_case.sale_id}/fiscal-document", headers=auth).status_code == 403
    assert client.get(f"/api/v1/sales/{fiscal_case.sale_id}/fiscal-document/file", headers=auth).status_code == 403


def test_related_configuration_ids_are_tenant_scoped(client, db_session, fiscal_case):
    foreign = seed_fiscal_case(db_session)
    auth = _auth(fiscal_case.actors["clinic_admin"])
    response = client.post("/api/v1/fiscal/configuration/series", headers=auth, json={
        "fiscal_issuer_id": str(foreign.issuer_id), "point_of_sale": 2,
        "document_type": "receipt_c", "concept": 2,
    })
    assert response.status_code == 404
    assert client.patch(f"/api/v1/fiscal/configuration/series/{foreign.series_id}", headers=auth,
                        json={"point_of_sale": 2}).status_code == 404
    assert client.patch(f"/api/v1/payment-methods/{fiscal_case.method_id}", headers=auth,
                        json={"suggested_fiscal_issuer_id": str(foreign.issuer_id)}).status_code == 404
    configuration = client.get("/api/v1/fiscal/configuration", headers=auth).json()["data"]
    assert [row["id"] for row in configuration["issuers"]] == [str(fiscal_case.issuer_id)]
    assert [row["id"] for row in configuration["series"]] == [str(fiscal_case.series_id)]
    assert [row["id"] for row in configuration["payment_methods"]] == [str(fiscal_case.method_id)]


@pytest.mark.parametrize("foreign_resource", ["sale", "payment", "series"])
def test_proposal_creation_hides_foreign_related_ids(db_session, fiscal_case, foreign_resource):
    foreign = seed_fiscal_case(db_session)
    payload = FiscalProposalGenerate(
        payment_ids=[foreign.payment_id if foreign_resource == "payment" else fiscal_case.payment_id],
        fiscal_series_id=foreign.series_id if foreign_resource == "series" else fiscal_case.series_id,
        fiscal_description="Synthetic service",
    )
    with pytest.raises(AppError) as error:
        FiscalProposalService(db_session).generate(
            fiscal_case.context, foreign.sale_id if foreign_resource == "sale" else fiscal_case.sale_id, payload,
        )
    assert error.value.status_code == 404
    db_session.rollback()
    assert list(db_session.scalars(select(FiscalProposal).where(FiscalProposal.tenant_id == fiscal_case.tenant_id))) == []


@pytest.mark.parametrize("operation", ["review", "update", "approve", "cancel"])
def test_proposal_and_snapshot_are_hidden_from_other_tenant(db_session, fiscal_case, operation):
    foreign = seed_fiscal_case(db_session)
    proposal = _draft(db_session, foreign)
    service = FiscalProposalService(db_session)
    with pytest.raises(AppError) as error:
        if operation == "review":
            service.review(fiscal_case.context, foreign.sale_id)
        elif operation == "update":
            service.update(fiscal_case.context, fiscal_case.sale_id, proposal.id,
                FiscalProposalUpdate(payment_ids=[fiscal_case.payment_id], fiscal_series_id=fiscal_case.series_id,
                                     fiscal_description="Synthetic overwrite"))
        elif operation == "approve":
            _approve(db_session, fiscal_case, proposal)
        else:
            service.cancel(fiscal_case.context, fiscal_case.sale_id, proposal.id, reason="Synthetic cancel")
    assert error.value.status_code == 404
    db_session.rollback()
    review = service.review(fiscal_case.context, fiscal_case.sale_id)
    assert review.proposals == []
    assert str(foreign.issuer_id) not in review.model_dump_json()
    assert str(foreign.payment_id) not in review.model_dump_json()


@pytest.mark.parametrize("role", ["clinic_admin", "contador", "medico_veterinario"])
def test_authorized_actors_can_approve_and_share_own_tenant(db_session, fiscal_case, role):
    proposal = _draft(db_session, fiscal_case)
    approved = _approve(db_session, fiscal_case, proposal, context=context_for(fiscal_case.actors[role]))
    assert approved.status == "approved"
    assert approved.approved_by_user_id == fiscal_case.actors[role].id
    review = FiscalProposalService(db_session).review(context_for(fiscal_case.actors["contador"]), fiscal_case.sale_id)
    assert [row.id for row in review.proposals] == [proposal.id]
    assert review.totals.committed_ars == approved.total_ars


@pytest.mark.parametrize("operation", ["generate", "update", "approve", "cancel"])
def test_secretary_has_visual_review_without_fiscal_mutation(db_session, fiscal_case, operation):
    proposal = _draft(db_session, fiscal_case)
    context = context_for(fiscal_case.actors["secretaria"])
    service = FiscalProposalService(db_session)
    assert service.review(context, fiscal_case.sale_id).proposals[0].id == proposal.id
    with pytest.raises(AppError) as error:
        if operation == "generate":
            _draft(db_session, fiscal_case, context=context)
        elif operation == "approve":
            _approve(db_session, fiscal_case, proposal, context=context)
        elif operation == "update":
            service.update(context, fiscal_case.sale_id, proposal.id,
                FiscalProposalUpdate(payment_ids=[fiscal_case.payment_id], fiscal_series_id=fiscal_case.series_id,
                                     fiscal_description="Synthetic replacement"))
        else:
            service.cancel(context, fiscal_case.sale_id, proposal.id, reason="Synthetic cancellation")
    assert error.value.status_code == 403
    db_session.rollback()
    assert list(db_session.scalars(select(FiscalPaymentAllocation).where(
        FiscalPaymentAllocation.tenant_id == fiscal_case.tenant_id,
    ))) == []


def test_veterinarian_can_only_review_and_approve_linked_issuer(db_session, fiscal_case):
    colleague = seed_fiscal_case(db_session, tenant_id=fiscal_case.tenant_id, point_of_sale=2)
    proposal = _draft(db_session, colleague)
    context = context_for(fiscal_case.actors["medico_veterinario"])
    service = FiscalProposalService(db_session)
    with pytest.raises(AppError) as error:
        _approve(db_session, colleague, proposal, context=context)
    assert error.value.status_code == 403
    db_session.rollback()
    review = service.review(context, colleague.sale_id)
    assert review.proposals == []
    assert str(colleague.issuer_id) not in str([row.snapshot for row in review.proposals])


def test_fiscal_review_filters_inconsistent_foreign_file_history_and_actors(db_session, fiscal_case):
    foreign = seed_fiscal_case(db_session)
    document = _manual_document(db_session, fiscal_case)
    document.uploaded_by_user_id = foreign.context.user_id
    db_session.flush()
    version = SaleFiscalDocumentFileVersion(
        tenant_id=foreign.tenant_id, fiscal_document_id=document.id,
        original_filename="foreign-private-history.pdf", bucket_name="foreign",
        storage_key="foreign/secret/key", content_type="application/pdf", size_bytes=10,
        sha256="b" * 64, uploaded_at=datetime.now(UTC), replaced_at=datetime.now(UTC),
        replaced_by_user_id=foreign.context.user_id,
    )
    db_session.add(version)
    db_session.commit()
    # A prior unfiltered ORM load must not bypass tenant criteria on this read.
    assert len(document.file_history) == 1
    review = FiscalProposalService(db_session).review(fiscal_case.context, fiscal_case.sale_id)
    read = review.documents[0]
    assert read.file_history == []
    assert read.uploaded_by_user_name is None and read.uploaded_by_user_email is None
    serialized = review.model_dump_json()
    assert "foreign-private-history.pdf" not in serialized
    assert foreign.context.user_email not in serialized
    assert str(foreign.context.user_id) not in serialized


@pytest.mark.parametrize("foreign_resource", ["sale", "document", "payment"])
def test_manual_regularization_hides_foreign_related_ids(client, db_session, fiscal_case, foreign_resource):
    foreign = seed_fiscal_case(db_session)
    own_document = _manual_document(db_session, fiscal_case)
    foreign_document = _manual_document(db_session, foreign)
    sale_id = foreign.sale_id if foreign_resource == "sale" else fiscal_case.sale_id
    document_id = foreign_document.id if foreign_resource in {"sale", "document"} else own_document.id
    payment_id = foreign.payment_id if foreign_resource in {"sale", "payment"} else fiscal_case.payment_id
    response = client.post(f"/api/v1/sales/{sale_id}/fiscal-documents/{document_id}/allocate",
        headers={**_auth(fiscal_case.actors["clinic_admin"]), "Idempotency-Key": "manual-cross-tenant"},
        json={"payment_ids": [str(payment_id)], "confirm_fiscal_identity": True})
    assert response.status_code == 404, response.text
    assert list(db_session.scalars(select(FiscalPaymentAllocation))) == []


@pytest.mark.parametrize("role", ["secretaria", "superadmin"])
def test_manual_regularization_requires_fiscal_authorization(client, db_session, fiscal_case, role):
    document = _manual_document(db_session, fiscal_case)
    response = client.post(f"/api/v1/sales/{fiscal_case.sale_id}/fiscal-documents/{document.id}/allocate",
        headers={**_auth(fiscal_case.actors[role]), "Idempotency-Key": "manual-forbidden"},
        json={"payment_ids": [str(fiscal_case.payment_id)], "confirm_fiscal_identity": True})
    assert response.status_code == 403, response.text
    assert list(db_session.scalars(select(FiscalPaymentAllocation))) == []


@pytest.mark.parametrize("role,expected", [
    ("clinic_admin", 201), ("contador", 201), ("medico_veterinario", 201),
    ("secretaria", 403), ("superadmin", 403),
])
def test_manual_upload_checks_fiscal_role_and_own_issuer(client, fiscal_case, role, expected):
    from app.tests.test_sale_fiscal_documents import PDF, _storage

    storage = _storage(client)
    response = client.post(f"/api/v1/sales/{fiscal_case.sale_id}/fiscal-document",
        headers=_auth(fiscal_case.actors[role]), data={
            "fiscal_issuer_id": str(fiscal_case.issuer_id), "document_type": "receipt_c", "document_code": "015",
            "document_number": "synthetic-upload", "issue_date": "2026-10-20",
        }, files={"file": ("receipt.pdf", PDF, "application/pdf")})
    assert response.status_code == expected, response.text
    if expected == 403:
        assert storage.uploads == []


def test_manual_reads_allow_secretary_and_mutations_do_not(client, db_session, fiscal_case):
    document = _manual_document(db_session, fiscal_case)
    auth = _auth(fiscal_case.actors["secretaria"])
    base = f"/api/v1/sales/{fiscal_case.sale_id}/fiscal-document"
    assert client.get(base, headers=auth).status_code == 200
    response = client.patch(base, headers=auth, data={"document_number": "forbidden"})
    assert response.status_code == 403, response.text
    db_session.refresh(document)
    assert document.document_number == "synthetic-history"


@pytest.mark.parametrize("direction", ["takeover", "change_target"])
def test_manual_correction_requires_both_current_and_target_issuer_permission(client, db_session, fiscal_case, direction):
    colleague = seed_fiscal_case(db_session, tenant_id=fiscal_case.tenant_id, point_of_sale=2)
    document = _manual_document(db_session, fiscal_case)
    actor = colleague.actors["medico_veterinario"] if direction == "takeover" else fiscal_case.actors["medico_veterinario"]
    response = client.patch(f"/api/v1/sales/{fiscal_case.sale_id}/fiscal-document",
        headers=_auth(actor), data={"fiscal_issuer_id": str(colleague.issuer_id)})
    assert response.status_code == 403, response.text
    db_session.refresh(document)
    assert document.fiscal_issuer_id == fiscal_case.issuer_id

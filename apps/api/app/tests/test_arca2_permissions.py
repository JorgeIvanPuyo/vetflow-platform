"""Fiscal actor/tenant boundaries and production guards around emission/files."""
from dataclasses import replace
import json

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.errors import AppError
from app.core.tenant import TenantContext
from app.models.arca_emission import ArcaDocumentFile, ArcaEmissionIntent, ArcaParameterCache
from app.models.fiscal_configuration import FiscalSeries
from app.schemas.fiscal_emission import FiscalEmissionCreate
from app.services.arca_emission import ArcaEmissionService
from app.services.arca_wsfe import PARAMETER_METHODS
from app.tests.arca2_emission_support import NOW, SyntheticEmissionRuntime, SyntheticEmissionStorage, seed_emission_case
from app.tests.arca2_support import ControlledArcaTransport
from app.tests.fiscal_test_support import context_for


@pytest.fixture()
def case(db_session):
    return seed_emission_case(db_session)


@pytest.fixture()
def laboratory():
    # This fixture deliberately has two remote POS for two unrelated clinics.
    # The default transport only advertises POS 1 and must not silently enable 2.
    runtime = SyntheticEmissionRuntime(transport=ControlledArcaTransport(points_of_sale=(1, 2)))
    try:
        yield runtime, SyntheticEmissionStorage()
    finally:
        runtime.close()


def _service(db, laboratory):
    runtime, storage = laboratory
    return ArcaEmissionService(db, runtime=runtime, storage=storage, clock=lambda: NOW)


def _prepare(db, laboratory, case, *, context=None, key="permission-intent"):
    return _service(db, laboratory).prepare(context or case.context, case.sale_id, case.create, key)


def _count(db):
    return db.scalar(select(func.count()).select_from(ArcaEmissionIntent))


@pytest.fixture()
def readiness_api(client, db_session, laboratory):
    from app.api.fiscal_emissions import get_arca_emission_service
    service = _service(db_session, laboratory)
    client.app.dependency_overrides[get_arca_emission_service] = lambda: service
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(get_arca_emission_service, None)


@pytest.mark.parametrize("role", ["clinic_admin", "contador", "medico_veterinario"])
def test_allowed_actor_can_explicitly_issue_only_own_tenant_and_issuer(db_session, case, laboratory, role):
    context = context_for(case.actors[role])
    operation = _prepare(db_session, laboratory, case, context=context)
    issued = _service(db_session, laboratory).issue(context, case.sale_id, operation.id)
    assert issued.status == "authorized"
    assert laboratory[0].transport.authorization_calls == 1


@pytest.mark.parametrize("role", ["secretaria", "superadmin"])
@pytest.mark.parametrize("action", ["prepare", "issue", "reconcile", "regenerate"])
def test_read_or_admin_role_does_not_imply_fiscal_mutation_permissions(db_session, case, laboratory, role, action):
    operation = _prepare(db_session, laboratory, case)
    context = context_for(case.actors[role])
    service = _service(db_session, laboratory)
    before = list(laboratory[0].ticket_calls)
    with pytest.raises(AppError) as error:
        if action == "prepare":
            _prepare(db_session, laboratory, case, context=context, key="forbidden-intent")
        else:
            getattr(service, action)(context, case.sale_id, operation.id)
    assert error.value.status_code == 403
    assert laboratory[0].ticket_calls == before and laboratory[0].transport.authorization_calls == 0


@pytest.mark.parametrize("kind", ["missing_actor", "missing_role", "forged_role", "foreign_actor", "inactive_actor"])
def test_missing_or_invalid_actor_context_has_no_fiscal_access(db_session, case, laboratory, kind):
    context = case.context
    if kind == "missing_actor":
        context = TenantContext(tenant_id=case.tenant_id, role="clinic_admin")
    elif kind == "missing_role":
        context = replace(context, role=None)
    elif kind == "forged_role":
        context = replace(context_for(case.actors["secretaria"]), role="clinic_admin")
    elif kind == "foreign_actor":
        foreign = seed_emission_case(db_session, point_of_sale=2)
        context = replace(context, user_id=foreign.context.user_id)
    else:
        case.actors["clinic_admin"].is_active = False
        db_session.commit()
    with pytest.raises(AppError) as error:
        _service(db_session, laboratory).list(context, case.sale_id)
    assert error.value.status_code == 403
    assert laboratory[0].transport.calls == [] and laboratory[0].ticket_calls == []


@pytest.mark.parametrize("reference", ["sale", "proposal"])
def test_preparation_hides_foreign_related_resources(db_session, case, laboratory, reference):
    foreign = seed_emission_case(db_session, point_of_sale=2)
    payload = foreign.create if reference == "proposal" else case.create
    sale_id = foreign.sale_id if reference == "sale" else case.sale_id
    with pytest.raises(AppError) as error:
        _service(db_session, laboratory).prepare(case.context, sale_id, payload, "foreign-resource")
    assert error.value.status_code == 404
    assert _count(db_session) == 0 and laboratory[0].transport.authorization_calls == 0


@pytest.mark.parametrize("action", ["list", "issue", "reconcile", "regenerate", "download"])
def test_foreign_operations_snapshots_and_files_are_hidden(db_session, case, laboratory, action):
    foreign = seed_emission_case(db_session, point_of_sale=2)
    operation = _prepare(db_session, laboratory, foreign, key="foreign-operation")
    issued = _service(db_session, laboratory).issue(foreign.context, foreign.sale_id, operation.id)
    assert issued.status == "authorized", issued.diagnostics
    service = _service(db_session, laboratory)
    before = list(laboratory[0].ticket_calls)
    with pytest.raises(AppError) as error:
        if action == "list":
            service.list(case.context, foreign.sale_id)
        else:
            getattr(service, action)(case.context, case.sale_id, operation.id)
    assert error.value.status_code == 404
    assert laboratory[0].ticket_calls == before
    own = service.list(case.context, case.sale_id)
    assert own["operations"] == []
    assert str(foreign.issuer_id) not in json.dumps(own, default=str)


def test_foreign_file_version_id_is_not_resolved_under_own_operation(db_session, case, laboratory):
    foreign = seed_emission_case(db_session, point_of_sale=2)
    own_operation = _prepare(db_session, laboratory, case)
    foreign_operation = _prepare(db_session, laboratory, foreign, key="foreign-download-version")
    service = _service(db_session, laboratory)
    own_authorized = service.issue(case.context, case.sale_id, own_operation.id)
    foreign_authorized = service.issue(foreign.context, foreign.sale_id, foreign_operation.id)
    assert own_authorized.status == foreign_authorized.status == "authorized"
    assert own_authorized.file_status == foreign_authorized.file_status == "ready"
    file = db_session.scalar(select(ArcaDocumentFile).where(
        ArcaDocumentFile.tenant_id == foreign.tenant_id, ArcaDocumentFile.emission_id == foreign_operation.id))
    assert file is not None
    with pytest.raises(AppError) as error:
        service.download(case.context, case.sale_id, own_operation.id, version_id=file.id)
    assert error.value.status_code == 404


def test_secretary_reads_authorized_history_and_file_with_server_mutation_actions_disabled(db_session, case, laboratory):
    operation = _prepare(db_session, laboratory, case)
    service = _service(db_session, laboratory)
    service.issue(case.context, case.sale_id, operation.id)
    context = context_for(case.actors["secretaria"])
    response = service.list(context, case.sale_id)
    assert len(response["operations"]) == 1
    read = response["operations"][0]
    read = read.model_dump() if hasattr(read, "model_dump") else read
    actions = read["allowed_actions"]
    assert actions["download"] and not any(actions[name] for name in ("issue", "reconcile", "regenerate"))
    descriptor, content = service.download(context, case.sale_id, operation.id)
    assert descriptor is not None and content.startswith(b"%PDF-")


def test_veterinarian_cannot_take_over_another_linked_issuer(db_session, case, laboratory):
    # Another synthetic clinic operator in the SAME tenant owns a different POS.
    from app.tests.fiscal_test_support import seed_fiscal_case
    from app.schemas.fiscal_proposal import FiscalProposalGenerate, FiscalProposalApprove
    from app.services.fiscal_proposal import FiscalProposalService
    colleague = seed_fiscal_case(db_session, tenant_id=case.tenant_id, point_of_sale=2)
    proposals = FiscalProposalService(db_session).generate(colleague.context, colleague.sale_id,
        FiscalProposalGenerate(payment_ids=[colleague.payment_id], fiscal_series_id=colleague.series_id,
                               fiscal_description="Synthetic colleague fiscal service"))
    proposal = FiscalProposalService(db_session).approve(colleague.context, colleague.sale_id, proposals[0].id,
        FiscalProposalApprove(content_hash=proposals[0].content_hash, confirm_fiscal_identity=True),
        idempotency_key="colleague-approved")
    request = FiscalEmissionCreate(proposal_id=proposal.id,
        fiscal_data=case.payload.model_copy(update={"point_of_sale": 2}), confirm_fiscal_identity=True)
    with pytest.raises(AppError) as error:
        _service(db_session, laboratory).prepare(context_for(case.actors["medico_veterinario"]),
            colleague.sale_id, request, "veterinarian-takeover")
    assert error.value.status_code == 403
    assert laboratory[0].ticket_calls == []


def test_global_series_ownership_conflict_does_not_reveal_other_tenant(db_session, case, laboratory):
    _prepare(db_session, laboratory, case)
    foreign = seed_emission_case(db_session)  # Same CUIT/POS/type in another tenant.
    with pytest.raises(AppError) as error:
        _prepare(db_session, laboratory, foreign, key="same-real-series-other-tenant")
    assert error.value.status_code == 409
    assert str(case.tenant_id) not in error.value.message
    assert str(case.issuer_id) not in error.value.message
    assert case.context.user_email not in error.value.message
    assert _count(db_session) == 1


def test_production_is_blocked_before_ticket_resolution_or_any_soap_request(db_session, case, laboratory):
    series = db_session.scalar(select(FiscalSeries).where(FiscalSeries.tenant_id == case.tenant_id, FiscalSeries.id == case.series_id))
    series.environment = "production"
    db_session.commit()
    request = case.create.model_copy(update={"fiscal_data": case.payload.model_copy(update={"environment": "production"})})
    with pytest.raises(AppError) as error:
        _service(db_session, laboratory).prepare(case.context, case.sale_id, request, "forbidden-production")
    assert error.value.status_code in {403, 409}
    assert laboratory[0].ticket_calls == [] and laboratory[0].transport.calls == [] and _count(db_session) == 0


def test_api_payload_cannot_select_secret_resources_paths_or_transport_endpoints(case, laboratory):
    base = case.create.model_dump(mode="json")
    for name, value in {"credential_reference": "opaque://another-tenant/key", "secret_path": "../../private.key",
                        "endpoint": "https://attacker.example/", "token": "not-an-input"}.items():
        with pytest.raises(ValidationError):
            FiscalEmissionCreate.model_validate({**base, name: value})
    assert laboratory[0].ticket_calls == [] and laboratory[0].transport.calls == []


@pytest.mark.parametrize("role,can_validate", [
    ("clinic_admin", True), ("contador", True), ("medico_veterinario", True), ("secretaria", False),
])
def test_readiness_get_only_reads_safe_metadata_and_server_actions(readiness_api, case, laboratory, role, can_validate):
    response = readiness_api.get("/api/v1/fiscal/emission-readiness",
        params={"series_id": str(case.series_id)}, headers={"X-User-Email": case.actors[role].email})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["remote_validation"] == "pending" and data["parameters"] is None
    assert data["allowed_actions"]["validate"] is can_validate
    assert data["production_blocked"] is True
    assert laboratory[0].ticket_calls == [] and laboratory[0].transport.calls == []
    assert "synthetic-token-not-real" not in response.text and "synthetic-sign-not-real" not in response.text


def test_secretary_readiness_validation_post_is_forbidden_without_ticket_or_http(readiness_api, case, laboratory):
    response = readiness_api.post("/api/v1/fiscal/emission-readiness/validate",
        json={"series_id": str(case.series_id)}, headers={"X-User-Email": case.actors["secretaria"].email})
    assert response.status_code == 403, response.text
    assert laboratory[0].ticket_calls == [] and laboratory[0].transport.calls == []


@pytest.mark.parametrize("role", ["clinic_admin", "contador"])
def test_explicit_readiness_validation_uses_parameter_cache_and_returns_safe_results(readiness_api, db_session, case, laboratory, role):
    auth = {"X-User-Email": case.actors[role].email}
    for _attempt in range(2):
        response = readiness_api.post("/api/v1/fiscal/emission-readiness/validate",
            json={"series_id": str(case.series_id)}, headers=auth)
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["remote_validation"] == "validated" and data["production_blocked"]
        assert set(data["parameters"]) == PARAMETER_METHODS
        assert data["credential"]["fingerprint"] == "f" * 64
        assert data["credential"]["expires_at"] and data["allowed_actions"]["validate"]
        assert "synthetic-token-not-real" not in response.text and "synthetic-sign-not-real" not in response.text
    assert sorted(laboratory[0].transport.calls) == sorted(PARAMETER_METHODS)
    assert laboratory[0].transport.authorization_calls == 0
    assert db_session.scalar(select(func.count()).select_from(ArcaParameterCache).where(
        ArcaParameterCache.tenant_id == case.tenant_id)) == len(PARAMETER_METHODS)
    before_tickets, before_http = len(laboratory[0].ticket_calls), len(laboratory[0].transport.calls)
    assert readiness_api.get("/api/v1/fiscal/emission-readiness", params={"series_id": str(case.series_id)}, headers=auth).status_code == 200
    assert len(laboratory[0].ticket_calls) == before_tickets and len(laboratory[0].transport.calls) == before_http


def test_production_readiness_is_blocked_before_even_safe_credential_status_on_post(readiness_api, db_session, case, laboratory):
    series = db_session.scalar(select(FiscalSeries).where(FiscalSeries.tenant_id == case.tenant_id, FiscalSeries.id == case.series_id))
    series.environment = "production"
    db_session.commit()
    auth = {"X-User-Email": case.context.user_email}
    response = readiness_api.get("/api/v1/fiscal/emission-readiness", params={"series_id": str(case.series_id)}, headers=auth)
    assert response.status_code == 200 and not response.json()["data"]["allowed_actions"]["validate"]
    status_calls = len(laboratory[0].status_calls)
    response = readiness_api.post("/api/v1/fiscal/emission-readiness/validate",
        json={"series_id": str(case.series_id)}, headers=auth)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "arca_production_disabled"
    assert len(laboratory[0].status_calls) == status_calls
    assert laboratory[0].ticket_calls == [] and laboratory[0].transport.calls == []

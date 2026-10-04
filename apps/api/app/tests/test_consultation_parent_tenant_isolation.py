"""SEC.3.1: optional parent metadata is scoped without repairing stored FKs."""
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.models.consultation import Consultation
from app.models.owner import Owner
from app.models.patient import Patient
from app.repositories.consultation import ConsultationRepository
from app.schemas.consultation import ConsultationRead
from app.tests.role_helpers import veterinarian_headers


@pytest.fixture()
def relation_case(db_session, tenant, other_tenant):
    parents = {}
    for key, clinic in [("same", tenant), ("foreign", other_tenant)]:
        owner = Owner(tenant_id=clinic.id, full_name="Synthetic owner", phone="000")
        db_session.add(owner)
        db_session.flush()
        patient = Patient(tenant_id=clinic.id, owner_id=owner.id, name="Synthetic patient", species="canine")
        db_session.add(patient)
        db_session.flush()
        parent = Consultation(tenant_id=clinic.id, patient_id=patient.id, reason="Synthetic parent", visit_date=datetime(2026, 10, 3, 12, tzinfo=UTC))
        db_session.add(parent)
        db_session.flush()
        parents[key] = parent
    child = Consultation(tenant_id=tenant.id, patient_id=parents["same"].patient_id, reason="Synthetic child", visit_date=datetime(2026, 10, 3, 12, tzinfo=UTC))
    db_session.add(child)
    db_session.commit()
    return dict(child=child, parents=parents, tenant_id=tenant.id, headers=veterinarian_headers(tenant))


@pytest.fixture(params=["same", "foreign", "null"])
def parent_case(request, relation_case, db_session):
    c = relation_case
    c["kind"] = request.param
    c["stored_parent"] = c["parents"][request.param].id if request.param != "null" else None
    c["child"].parent_consultation_id = c["stored_parent"]
    c["child"].consultation_type = "follow_up" if c["stored_parent"] else "initial"
    db_session.commit()
    c["expected_parent"] = str(c["stored_parent"]) if request.param == "same" else None
    return c


def assert_stored_parent_unchanged(db_session, c):
    stored = db_session.scalar(select(Consultation.parent_consultation_id).where(
        Consultation.id == c["child"].id, Consultation.tenant_id == c["tenant_id"],
    ))
    assert stored == c["stored_parent"]


@pytest.mark.parametrize("endpoint", ["detail", "patient-list", "history", "patch", "patch-step"])
def test_parent_response_is_scoped_and_fk_is_preserved(client, db_session, parent_case, endpoint):
    c = parent_case
    path = f"/api/v1/consultations/{c['child'].id}"
    if endpoint in ["patch", "patch-step"]:
        suffix, payload = ("", {"reason": "Synthetic updated child"}) if endpoint == "patch" else ("/step", {"current_step": 2})
        response = client.patch(path + suffix, headers=c["headers"], json=payload)
    else:
        if endpoint != "detail":
            suffix = "consultations" if endpoint == "patient-list" else "clinical-history"
            path = f"/api/v1/patients/{c['child'].patient_id}/{suffix}"
        response = client.get(path, headers=c["headers"])
    assert response.status_code == 200
    data = response.json()["data"]
    if endpoint in ["patient-list", "history"]:
        rows = data if endpoint == "patient-list" else data["consultations"]
        data = next(row for row in rows if row["id"] == str(c["child"].id))
    assert data["parent_consultation_id"] == c["expected_parent"]
    assert_stored_parent_unchanged(db_session, c)


@pytest.mark.parametrize("read", ["detail", "patient-list"])
def test_parent_projection_handles_preloaded_relations(client, db_session, parent_case, read):
    c = parent_case
    # First load through the ordinary ORM relationship, including the foreign parent.
    parent = c["child"].parent_consultation
    assert (parent.id if parent else None) == c["stored_parent"]
    direct = ConsultationRead.model_validate(c["child"]).model_dump(mode="json")
    assert direct["parent_consultation_id"] == c["expected_parent"]
    repository = ConsultationRepository(db_session)
    if read == "detail":
        scoped = repository.get_by_id(c["tenant_id"], c["child"].id)
    else:
        rows, total = repository.list_by_patient(c["tenant_id"], c["child"].patient_id)
        assert total == 2
        scoped = next(row for row in rows if row.id == c["child"].id)
    assert (scoped.parent_consultation is not None) == (c["kind"] == "same")
    assert scoped.parent_consultation_id == c["stored_parent"]
    assert not db_session.dirty
    assert_stored_parent_unchanged(db_session, c)


def test_general_list_does_not_emit_parent_metadata(client, parent_case):
    c = parent_case
    response = client.get("/api/v1/consultations", headers=c["headers"])
    assert response.status_code == 200
    assert any(row["id"] == str(c["child"].id) for row in response.json()["data"])
    assert all("parent_consultation_id" not in row for row in response.json()["data"])


def test_follow_up_sets_owned_parent_even_if_original_parent_is_corrupt(client, db_session, parent_case):
    c = parent_case
    response = client.post(f"/api/v1/consultations/{c['child'].id}/follow-up", headers=c["headers"])
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["parent_consultation_id"] == str(c["child"].id)
    assert data["tenant_id"] == str(c["tenant_id"])
    follow_up = db_session.scalar(select(Consultation).where(Consultation.id == uuid.UUID(data["id"])))
    assert follow_up.parent_consultation_id == c["child"].id
    assert_stored_parent_unchanged(db_session, c)


def test_follow_up_foreign_and_absent_targets_are_indistinguishable(client, db_session, relation_case):
    c = relation_case
    before = db_session.scalar(select(func.count()).select_from(Consultation))
    responses = [client.post(f"/api/v1/consultations/{target}/follow-up", headers=c["headers"]) for target in [c["parents"]["foreign"].id, uuid.uuid4()]]
    assert all(r.status_code == 404 for r in responses)
    assert responses[0].json() == responses[1].json()
    assert responses[0].json()["error"]["code"] == "consultation_not_found"
    assert db_session.scalar(select(func.count()).select_from(Consultation)) == before


@pytest.mark.parametrize("target", ["same", "foreign", "absent"])
def test_create_does_not_accept_client_selected_parent(client, db_session, relation_case, target):
    c = relation_case
    candidate = uuid.uuid4() if target == "absent" else c["parents"][target].id
    response = client.post("/api/v1/consultations", headers=c["headers"], json={
        "patient_id": str(c["child"].patient_id), "visit_date": "2026-10-03T12:00:00Z",
        "reason": "Synthetic create", "parent_consultation_id": str(candidate),
    })
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["parent_consultation_id"] is None
    assert db_session.scalar(select(Consultation.parent_consultation_id).where(Consultation.id == uuid.UUID(data["id"]))) is None


@pytest.mark.parametrize("suffix", ["", "/step"])
@pytest.mark.parametrize("target", ["same", "foreign", "absent"])
def test_patch_does_not_accept_client_selected_parent(client, db_session, relation_case, target, suffix):
    c = relation_case
    original = c["parents"]["same"].id
    c["child"].parent_consultation_id = original
    db_session.commit()
    candidate = uuid.uuid4() if target == "absent" else c["parents"][target].id
    response = client.patch(f"/api/v1/consultations/{c['child'].id}{suffix}", headers=c["headers"], json={
        "reason": "Synthetic patch", "parent_consultation_id": str(candidate),
    })
    assert response.status_code == 200
    assert response.json()["data"]["parent_consultation_id"] == str(original)
    stored = db_session.scalar(select(Consultation.parent_consultation_id).where(Consultation.id == c["child"].id))
    assert stored == original

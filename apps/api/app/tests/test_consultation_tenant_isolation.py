"""Consultation reads must tolerate historically inconsistent tenant FKs safely."""

import json
import uuid

import pytest
from sqlalchemy import select

from app.models.catalog_item import CatalogItem
from app.models.consultation import (
    Consultation,
    ConsultationMedication,
    ConsultationStudyRequest,
)
from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.owner import Owner
from app.models.patient import Patient
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.consultation import ConsultationRepository
from app.schemas.patient import ClinicalHistoryPdfExportRequest
from app.services.clinical_history_pdf import ClinicalHistoryPdfService
from app.tests.role_helpers import veterinarian_headers
from app.tests.test_consultations import (
    _create_consultation,
    _create_owner,
    _create_patient,
)


@pytest.fixture()
def consultation_case(client, db_session, tenant, other_tenant):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])
    consultation = _create_consultation(client, tenant, patient["id"])
    consultation_id = uuid.UUID(consultation["id"])
    local_meds = [
        ConsultationMedication(
            tenant_id=tenant.id, consultation_id=consultation_id,
            medication_name=f"Local medication {index}",
        )
        for index in range(3)
    ]
    local_studies = [
        ConsultationStudyRequest(
            tenant_id=tenant.id, consultation_id=consultation_id,
            name=f"Local study {index}", study_type="other",
        )
        for index in range(2)
    ]
    # These valid single-column FKs reproduce the restored historical defect.
    foreign_med = ConsultationMedication(
        tenant_id=other_tenant.id, consultation_id=consultation_id,
        medication_name="FOREIGN CLINICAL DATA", instructions="FOREIGN INSTRUCTIONS",
    )
    foreign_study = ConsultationStudyRequest(
        tenant_id=other_tenant.id, consultation_id=consultation_id,
        name="FOREIGN CLINICAL DATA", study_type="other", notes="FOREIGN NOTES",
    )
    db_session.add_all([*local_meds, *local_studies, foreign_med, foreign_study])
    db_session.commit()
    case = {
        "id": consultation_id, "patient_id": uuid.UUID(patient["id"]),
        "owner_id": uuid.UUID(owner["id"]), "tenant_id": tenant.id,
        "foreign_tenant_id": other_tenant.id,
        "med_ids": {str(row.id) for row in local_meds},
        "study_ids": {str(row.id) for row in local_studies},
        "foreign_med_id": foreign_med.id, "foreign_study_id": foreign_study.id,
    }
    db_session.expunge_all()
    return case


@pytest.mark.parametrize("endpoint", ["detail", "patient-consultations", "history"])
def test_consultation_reads_exclude_foreign_children(client, consultation_case, endpoint):
    case = consultation_case
    urls = {
        "detail": f"/api/v1/consultations/{case['id']}",
        "patient-consultations": f"/api/v1/patients/{case['patient_id']}/consultations",
        "history": f"/api/v1/patients/{case['patient_id']}/clinical-history",
    }
    response = client.get(urls[endpoint], headers={"X-Tenant-Id": str(case["tenant_id"])})
    assert response.status_code == 200
    data = response.json()["data"]
    rows = [data] if endpoint == "detail" else data if endpoint == "patient-consultations" else data["consultations"]
    assert len(rows) == 1
    consultation = rows[0]
    assert consultation["tenant_id"] == str(case["tenant_id"])
    assert {row["id"] for row in consultation["medications"]} == case["med_ids"]
    assert {row["id"] for row in consultation["study_requests"]} == case["study_ids"]
    assert all(row["tenant_id"] == str(case["tenant_id"]) for row in consultation["medications"] + consultation["study_requests"])
    assert "FOREIGN" not in response.text


def test_foreign_tenant_cannot_read_consultation(client, consultation_case):
    case = consultation_case
    response = client.get(
        f"/api/v1/consultations/{case['id']}",
        headers={"X-Tenant-Id": str(case["foreign_tenant_id"])},
    )
    assert response.status_code == 404


def test_pdf_export_does_not_render_foreign_children(db_session, consultation_case, monkeypatch):
    case = consultation_case
    rendered = []

    def render(self, context, **kwargs):
        rendered.append(context)
        return b"%PDF-1.4 synthetic local output"

    monkeypatch.setattr(ClinicalHistoryPdfService, "_render_pdf_from_template", render)
    result = ClinicalHistoryPdfService(db_session).export_patient_history_pdf(
        case["tenant_id"], case["patient_id"],
        ClinicalHistoryPdfExportRequest(detail_level="full"),
    )
    assert len(rendered) == 1
    assert "FOREIGN" not in json.dumps(rendered[0], default=str)
    text = "\n".join(result.text_lines)
    assert "FOREIGN" not in text
    assert all(f"Local medication {index}" in text for index in range(3))
    assert all(f"Local study {index}" in text for index in range(2))


@pytest.mark.parametrize("read", ["detail", "patient-consultations"])
def test_scoped_read_replaces_preloaded_unscoped_children(db_session, consultation_case, read):
    case = consultation_case
    # Identity-map reuse must not bypass SQL tenant criteria on a later read.
    original = db_session.scalar(select(Consultation).where(Consultation.id == case["id"]))
    assert str(case["foreign_med_id"]) in {str(row.id) for row in original.medications}
    assert str(case["foreign_study_id"]) in {str(row.id) for row in original.study_requests}
    repository = ConsultationRepository(db_session)
    if read == "detail":
        scoped = repository.get_by_id(case["tenant_id"], case["id"])
    else:
        rows, total = repository.list_by_patient(case["tenant_id"], case["patient_id"])
        assert total == 1
        scoped = rows[0]
    assert {str(row.id) for row in scoped.medications} == case["med_ids"]
    assert {str(row.id) for row in scoped.study_requests} == case["study_ids"]


@pytest.mark.parametrize("relation", ["patient", "owner"])
def test_detail_rejects_corrupt_patient_or_owner_link(client, db_session, consultation_case, relation):
    case = consultation_case
    foreign_owner = Owner(tenant_id=case["foreign_tenant_id"], full_name="FOREIGN OWNER", phone="000")
    db_session.add(foreign_owner)
    db_session.flush()
    if relation == "patient":
        foreign_patient = Patient(tenant_id=case["foreign_tenant_id"], owner_id=foreign_owner.id, name="FOREIGN PATIENT", species="canine")
        db_session.add(foreign_patient)
        db_session.flush()
        db_session.execute(Consultation.__table__.update().where(Consultation.id == case["id"], Consultation.tenant_id == case["tenant_id"]).values(patient_id=foreign_patient.id))
    else:
        db_session.execute(Patient.__table__.update().where(Patient.id == case["patient_id"], Patient.tenant_id == case["tenant_id"]).values(owner_id=foreign_owner.id))
    db_session.commit()
    db_session.expunge_all()
    response = client.get(f"/api/v1/consultations/{case['id']}", headers={"X-Tenant-Id": str(case["tenant_id"])})
    assert response.status_code == 404
    assert "FOREIGN" not in response.text
    rows, total = ConsultationRepository(db_session).list_by_patient(case["tenant_id"], case["patient_id"])
    assert rows == [] and total == 0


def test_archived_local_owner_preserves_consultation_visibility(client, db_session, consultation_case):
    case = consultation_case
    db_session.execute(Owner.__table__.update().where(Owner.id == case["owner_id"], Owner.tenant_id == case["tenant_id"]).values(is_active=False))
    db_session.commit()
    response = client.get(f"/api/v1/consultations/{case['id']}", headers={"X-Tenant-Id": str(case["tenant_id"])})
    assert response.status_code == 200
    assert {row["id"] for row in response.json()["data"]["medications"]} == case["med_ids"]


def test_dashboard_consultations_do_not_expose_a_foreign_patient(client, db_session, consultation_case):
    case = consultation_case
    owner = Owner(tenant_id=case["foreign_tenant_id"], full_name="FOREIGN OWNER", phone="000")
    db_session.add(owner)
    db_session.flush()
    patient = Patient(tenant_id=case["foreign_tenant_id"], owner_id=owner.id, name="FOREIGN PATIENT", species="canine")
    db_session.add(patient)
    db_session.flush()
    db_session.execute(Consultation.__table__.update().where(
        Consultation.id == case["id"], Consultation.tenant_id == case["tenant_id"],
    ).values(patient_id=patient.id))
    db_session.commit()
    db_session.expunge_all()
    response = client.get(
        "/api/v1/dashboard/summary", headers={"X-Tenant-Id": str(case["tenant_id"])},
        params={"date_from": "2026-04-24", "date_to": "2026-04-24"},
    )
    assert response.status_code == 200
    assert "FOREIGN" not in response.text
    assert response.json()["data"]["recent_consultations"] == []


def test_follow_up_does_not_copy_foreign_children(client, db_session, consultation_case):
    case = consultation_case
    tenant = db_session.get(Tenant, case["tenant_id"])
    response = client.post(f"/api/v1/consultations/{case['id']}/follow-up", headers=veterinarian_headers(tenant))
    assert response.status_code == 201
    data = response.json()["data"]
    assert len(data["medications"]) == len(case["med_ids"])
    assert len(data["study_requests"]) == len(case["study_ids"])
    assert "FOREIGN" not in response.text


def test_update_response_keeps_children_tenant_scoped(client, db_session, consultation_case):
    case = consultation_case
    tenant = db_session.get(Tenant, case["tenant_id"])
    response = client.patch(
        f"/api/v1/consultations/{case['id']}",
        headers=veterinarian_headers(tenant), json={"reason": "Updated locally"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["reason"] == "Updated locally"
    assert {row["id"] for row in data["medications"]} == case["med_ids"]
    assert {row["id"] for row in data["study_requests"]} == case["study_ids"]
    assert "FOREIGN" not in response.text


@pytest.mark.parametrize("foreign", [False, True])
def test_nested_references_are_scoped_without_hiding_inactive_local_entities(
    client, db_session, consultation_case, foreign,
):
    case = consultation_case
    reference_tenant = case["foreign_tenant_id"] if foreign else case["tenant_id"]
    item = InventoryItem(
        tenant_id=reference_tenant, internal_code="SEC1", name="Reference item",
        category="medication", unit="tablet", minimum_stock=0, is_active=False,
        purchase_tax_rate_percentage=0, profit_margin_percentage=0, sale_tax_rate_percentage=0,
    )
    catalog = CatalogItem(
        tenant_id=reference_tenant, catalog_type="exam_type", name="Reference study",
        normalized_name="reference study", is_active=False,
    )
    actor = User(
        tenant_id=reference_tenant, full_name="Reference actor", email="sec1@example.invalid",
        role="medico_veterinario", is_active=False,
    )
    db_session.add_all([item, catalog, actor])
    db_session.flush()
    movement = InventoryMovement(
        tenant_id=reference_tenant, inventory_item_id=item.id, movement_type="entry",
        quantity=1, unit_sale_price_ars=17, total_sale_price_ars=17,
    )
    db_session.add(movement)
    db_session.flush()
    med_id = uuid.UUID(sorted(case["med_ids"])[0])
    study_id = uuid.UUID(sorted(case["study_ids"])[0])
    db_session.execute(ConsultationMedication.__table__.update().where(
        ConsultationMedication.id == med_id, ConsultationMedication.tenant_id == case["tenant_id"],
    ).values(inventory_item_id=item.id, inventory_movement_id=movement.id))
    db_session.execute(ConsultationStudyRequest.__table__.update().where(
        ConsultationStudyRequest.id == study_id, ConsultationStudyRequest.tenant_id == case["tenant_id"],
    ).values(exam_catalog_item_id=catalog.id))
    db_session.execute(Consultation.__table__.update().where(
        Consultation.id == case["id"], Consultation.tenant_id == case["tenant_id"],
    ).values(created_by_user_id=actor.id, attending_user_id=actor.id))
    actor_id = str(actor.id)
    db_session.commit()
    db_session.expunge_all()

    scoped = ConsultationRepository(db_session).get_by_id(case["tenant_id"], case["id"])
    med = next(row for row in scoped.medications if row.id == med_id)
    study = next(row for row in scoped.study_requests if row.id == study_id)
    for related in [med.inventory_item, med.inventory_movement, study.exam_catalog_item, scoped.created_by_user, scoped.attending_user]:
        if foreign:
            assert related is None
        else:
            assert related.tenant_id == case["tenant_id"]
    response = client.get(f"/api/v1/consultations/{case['id']}", headers={"X-Tenant-Id": str(case["tenant_id"])})
    assert response.status_code == 200
    data = response.json()["data"]
    med_data = next(row for row in data["medications"] if row["id"] == str(med_id))
    study_data = next(row for row in data["study_requests"] if row["id"] == str(study_id))
    assert med_data["inventory_item_name"] == (None if foreign else "Reference item")
    assert med_data["unit_sale_price_ars"] == (None if foreign else "17.00")
    assert study_data["exam_catalog_item_name"] == (None if foreign else "Reference study")
    assert data["created_by_user_id"] == (None if foreign else actor_id)
    assert data["attending_user_id"] == (None if foreign else actor_id)

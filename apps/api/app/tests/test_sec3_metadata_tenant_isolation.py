"""The four reproduced DB.3 metadata cases, with positive controls."""
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models.catalog_item import CatalogItem
from app.models.consultation import Consultation, ConsultationMedication, ConsultationStudyRequest
from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.owner import Owner
from app.models.patient import Patient
from app.models.patient_file_reference import PatientFileReference
from app.models.patient_preventive_care import PatientPreventiveCare
from app.models.purchase import Purchase
from app.models.supplier import Supplier
from app.repositories.consultation import ConsultationRepository
from app.repositories.inventory import InventoryRepository
from app.schemas.consultation import ConsultationMedicationRead, ConsultationStudyRequestRead
from app.schemas.inventory import InventoryMovementRead

NOW = datetime(2026, 10, 3, 12, tzinfo=UTC)
PERIOD = {"date_from": "2026-10-03", "date_to": "2026-10-03"}


@pytest.fixture(params=[False, True], ids=["same-tenant", "foreign"])
def metadata_case(request, db_session, tenant, other_tenant):
    foreign = request.param
    groups = {}
    for key, clinic in [("local", tenant), ("foreign", other_tenant)]:
        owner = Owner(tenant_id=clinic.id, full_name=f"Synthetic {key} owner", phone="000")
        db_session.add(owner)
        db_session.flush()
        patient = Patient(tenant_id=clinic.id, owner_id=owner.id, name=f"Synthetic {key} patient", species="canine")
        item = InventoryItem(tenant_id=clinic.id, internal_code="SEC3", name=f"Synthetic {key} item", category="medication", unit="tablet", is_active=False, purchase_tax_rate_percentage=0, profit_margin_percentage=0, sale_tax_rate_percentage=0)
        catalog = CatalogItem(tenant_id=clinic.id, catalog_type="exam_type", name=f"Synthetic {key} exam", normalized_name=f"synthetic {key} exam", is_active=False)
        supplier = Supplier(tenant_id=clinic.id, name=f"Synthetic {key} supplier", normalized_name=f"synthetic {key} supplier", is_active=False)
        db_session.add_all([patient, item, catalog, supplier])
        db_session.flush()
        consult = Consultation(tenant_id=clinic.id, patient_id=patient.id, visit_date=NOW, reason="Synthetic consultation")
        move = InventoryMovement(tenant_id=clinic.id, inventory_item_id=item.id, movement_type="entry", quantity=1, unit_sale_price_ars=17, total_sale_price_ars=17, created_at=NOW)
        db_session.add_all([consult, move])
        db_session.flush()
        groups[key] = dict(patient=patient, item=item, catalog=catalog, supplier=supplier, consult=consult, move=move)
    local, target = groups["local"], groups["foreign" if foreign else "local"]
    med = ConsultationMedication(tenant_id=tenant.id, consultation_id=local["consult"].id, medication_name="Own medication snapshot", inventory_item_id=target["item"].id, inventory_movement_id=target["move"].id)
    study = ConsultationStudyRequest(tenant_id=tenant.id, consultation_id=local["consult"].id, name="Own study snapshot", study_type="exam", exam_catalog_item_id=target["catalog"].id)
    move = InventoryMovement(tenant_id=tenant.id, inventory_item_id=local["item"].id, movement_type="entry", quantity=1, related_patient_id=target["patient"].id, related_consultation_id=target["consult"].id, reverses_movement_id=target["move"].id, created_at=NOW)
    purchases = [Purchase(tenant_id=tenant.id, supplier_id=groups[k]["supplier"].id, supplier_name="Own purchase snapshot", purchase_date=NOW.date(), document_type="invoice", currency="ARS", status="received", total_ars=100, subtotal_ars=100, tax_total_ars=0) for k in ({"local", "foreign"} if foreign else {"local"})]
    care = PatientPreventiveCare(tenant_id=tenant.id, patient_id=local["patient"].id, name="Own care", care_type="other", applied_at=NOW)
    file = PatientFileReference(tenant_id=tenant.id, patient_id=local["patient"].id, name="Own file", file_type="other", uploaded_at=NOW)
    db_session.add_all([med, study, move, *purchases, care, file])
    db_session.commit()
    return dict(foreign=foreign, headers={"X-Tenant-ID": str(tenant.id)}, tenant_id=tenant.id, local=local, target=target, med=med, study=study, move=move, care=care, file=file)


@pytest.mark.parametrize("endpoint", ["detail", "patient-consultations", "history"])
def test_consultation_optional_metadata(client, db_session, metadata_case, endpoint):
    c = metadata_case
    local, target = c["local"], c["target"]
    paths = {"detail": f"/api/v1/consultations/{local['consult'].id}", "patient-consultations": f"/api/v1/patients/{local['patient'].id}/consultations", "history": f"/api/v1/patients/{local['patient'].id}/clinical-history"}
    response = client.get(paths[endpoint], headers=c["headers"])
    assert response.status_code == 200
    data = response.json()["data"]
    row = data if endpoint == "detail" else data[0] if endpoint == "patient-consultations" else data["consultations"][0]
    med, study = row["medications"][0], row["study_requests"][0]
    for field, obj in [("inventory_item_id", target["item"]), ("inventory_movement_id", target["move"])]:
        assert med[field] == (None if c["foreign"] else str(obj.id))
    assert study["exam_catalog_item_id"] == (None if c["foreign"] else str(target["catalog"].id))
    assert med["inventory_item_name"] == (None if c["foreign"] else target["item"].name)
    assert med["inventory_unit"] == (None if c["foreign"] else "tablet")
    assert med["unit_sale_price_ars"] == (None if c["foreign"] else "17.00")
    assert med["total_sale_price_ars"] == (None if c["foreign"] else "17.00")
    assert study["exam_catalog_item_name"] == (None if c["foreign"] else target["catalog"].name)
    assert med["medication_name"] == "Own medication snapshot"
    assert db_session.scalar(select(ConsultationMedication.inventory_item_id).where(ConsultationMedication.id == c["med"].id)) == target["item"].id


@pytest.mark.parametrize("endpoint", ["dashboard", "detail", "list"])
def test_movement_optional_metadata(client, db_session, metadata_case, endpoint):
    c = metadata_case
    paths = {"dashboard": "/api/v1/inventory/dashboard", "detail": f"/api/v1/inventory/movements/{c['move'].id}", "list": "/api/v1/inventory/movements"}
    response = client.get(paths[endpoint], headers=c["headers"], params=PERIOD if endpoint == "dashboard" else {})
    assert response.status_code == 200
    data = response.json()["data"]
    rows = data["activity"]["recent_movements"] if endpoint == "dashboard" else [data] if endpoint == "detail" else data
    row = next(r for r in rows if r["id"] == str(c["move"].id))
    for field, key in [("related_patient_id", "patient"), ("related_consultation_id", "consult"), ("reverses_movement_id", "move")]:
        obj = c["target"][key]
        assert row[field] == (None if c["foreign"] else str(obj.id))
        assert db_session.scalar(select(getattr(InventoryMovement, field)).where(InventoryMovement.id == c["move"].id)) == obj.id
    assert row["inventory_item_name"] == "Synthetic local item"


def test_preloaded_projection_and_scoped_reload_preserve_fks(db_session, metadata_case):
    c = metadata_case
    assert c["med"].inventory_item.id == c["target"]["item"].id
    assert c["study"].exam_catalog_item.id == c["target"]["catalog"].id
    assert c["move"].related_patient.id == c["target"]["patient"].id
    assert ConsultationMedicationRead.model_validate(c["med"]).inventory_item_id == (None if c["foreign"] else c["target"]["item"].id)
    assert ConsultationStudyRequestRead.model_validate(c["study"]).exam_catalog_item_id == (None if c["foreign"] else c["target"]["catalog"].id)
    assert InventoryMovementRead.model_validate(c["move"]).related_patient_id == (None if c["foreign"] else c["target"]["patient"].id)
    scoped = ConsultationRepository(db_session).get_by_id(c["tenant_id"], c["local"]["consult"].id)
    scoped_move = InventoryRepository(db_session).get_movement_by_id(c["tenant_id"], c["move"].id)
    assert (scoped.medications[0].inventory_item is None) == c["foreign"]
    assert (scoped_move.related_patient is None) == c["foreign"]
    assert c["med"].inventory_item_id == c["target"]["item"].id
    assert c["move"].related_patient_id == c["target"]["patient"].id
    assert not db_session.dirty


def test_top_suppliers_owned_groups_only(client, metadata_case):
    c = metadata_case
    response = client.get("/api/v1/purchases/dashboard", headers=c["headers"], params=PERIOD)
    assert response.status_code == 200
    rows = response.json()["data"]["top_suppliers"]
    assert len(rows) == 1
    assert rows[0]["supplier_id"] == str(c["local"]["supplier"].id)
    assert rows[0]["supplier_name"] == "Own purchase snapshot"
    assert rows[0]["purchase_count"] == 1
    assert rows[0]["registered_total_ars"] == rows[0]["received_total_ars"] == "100.00"


@pytest.mark.parametrize("suffix,record", [("preventive-care", "care"), ("file-references", "file")])
def test_patient_lists_uniform_absence_and_positive(client, metadata_case, suffix, record):
    c = metadata_case
    response = client.get(f"/api/v1/patients/{c['target']['patient'].id}/{suffix}", headers=c["headers"])
    if c["foreign"]:
        absent = client.get(f"/api/v1/patients/{uuid.uuid4()}/{suffix}", headers=c["headers"])
        assert response.status_code == absent.status_code == 404
        assert response.json() == absent.json()
    else:
        assert response.status_code == 200
        assert [row["id"] for row in response.json()["data"]] == [str(c[record].id)]
        assert response.json()["meta"]["total"] == 1

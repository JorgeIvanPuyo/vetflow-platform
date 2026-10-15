"""Patient deletion against a migrated PostgreSQL TEST_DATABASE_URL."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.consultation import (
    Consultation,
    ConsultationMedication,
    ConsultationStudyRequest,
)
from app.models.exam import Exam
from app.models.follow_up import FollowUp
from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.patient import Patient
from app.models.patient_file_reference import PatientFileReference
from app.models.patient_preventive_care import PatientPreventiveCare
from app.models.sale import Sale
from app.repositories.appointment import AppointmentRepository
from app.repositories.patient import PatientRepository
from app.tests.role_helpers import veterinarian_headers
from app.tests.test_patients_patch_delete import (
    _create_consultation,
    _create_exam,
    _create_file_reference,
    _create_patient_for_tenant,
    _create_preventive_care,
)


@pytest.fixture()
def db_session(postgres_test_session_factory):
    # Keep service commits real within savepoints, then discard all synthetic data.
    with postgres_test_session_factory.kw["bind"].connect() as connection:
        transaction = connection.begin()
        with Session(
            bind=connection, autoflush=False, join_transaction_mode="create_savepoint"
        ) as session:
            yield session
        transaction.rollback()


def _create_appointment(client, tenant, patient_id, **overrides):
    payload = {
        "patient_id": patient_id,
        "title": "Control",
        "appointment_type": "consultation",
        "start_at": "2026-05-10T10:00:00Z",
        "end_at": "2026-05-10T10:30:00Z",
        **overrides,
    }
    response = client.post(
        "/api/v1/appointments", headers=veterinarian_headers(tenant), json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


@pytest.mark.parametrize("appointment_count", [0, 1, 3])
def test_delete_patient_with_appointments(client, db_session, tenant, appointment_count):
    patient = _create_patient_for_tenant(client, tenant)
    for _ in range(appointment_count):
        _create_appointment(client, tenant, patient["id"])

    response = client.delete(
        f"/api/v1/patients/{patient['id']}", headers=veterinarian_headers(tenant)
    )

    assert response.status_code == 204, response.text
    db_session.expire_all()
    patient_id = uuid.UUID(patient["id"])
    assert db_session.scalar(select(Patient.id).where(Patient.id == patient_id)) is None
    assert db_session.scalars(
        select(Appointment.id).where(Appointment.patient_id == patient_id)
    ).all() == []


DELETED_MODELS = (
    Patient, Appointment, FollowUp, Consultation, Exam, PatientPreventiveCare,
    PatientFileReference, ConsultationMedication, ConsultationStudyRequest,
)


def _snapshot_tenant(db, tenant_id):
    """Read persisted columns, avoiding relationship caches and serializers."""
    return {
        model.__tablename__: db.execute(
            select(model.__table__).where(model.tenant_id == tenant_id).order_by(model.id)
        ).all()
        for model in (*DELETED_MODELS, InventoryMovement, InventoryItem, Sale)
    }


def _create_complete_history(client, db, tenant, name="Luna"):
    patient = _create_patient_for_tenant(client, tenant, name)
    patient_id = uuid.UUID(patient["id"])
    appointment = _create_appointment(client, tenant, patient["id"])
    consultation = _create_consultation(client, tenant, patient["id"])
    consultation_id = uuid.UUID(consultation["id"])
    _create_exam(client, tenant, patient["id"], consultation["id"])
    _create_preventive_care(client, tenant, patient["id"])
    _create_file_reference(client, tenant, patient["id"])
    item = InventoryItem(
        tenant_id=tenant.id, internal_code=uuid.uuid4().hex[:12], name="Insumo",
        category="supply", unit="unit", current_stock=Decimal("9"),
        purchase_tax_rate_percentage=Decimal("0"),
        profit_margin_percentage=Decimal("0"), sale_tax_rate_percentage=Decimal("0"),
    )
    db.add(item)
    db.flush()
    # Cover patient-only, consultation-only and combined inventory links.
    movements = [
        InventoryMovement(
            tenant_id=tenant.id, inventory_item_id=item.id, movement_type="out",
            quantity=Decimal("1"), stock_before=Decimal("10"), stock_after=Decimal("9"),
            related_patient_id=patient_id if patient_link else None,
            related_consultation_id=consultation_id if consultation_link else None,
        )
        for patient_link, consultation_link in ((True, False), (False, True), (True, True))
    ]
    db.add_all(movements)
    db.flush()
    db.add_all([
        FollowUp(
            tenant_id=tenant.id, patient_id=patient_id,
            appointment_id=uuid.UUID(appointment["id"]), title="Seguimiento",
            follow_up_type="consultation", due_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        ),
        ConsultationMedication(
            tenant_id=tenant.id, consultation_id=consultation_id,
            medication_name="Medicación", inventory_item_id=item.id,
            inventory_movement_id=movements[-1].id,
        ),
        ConsultationStudyRequest(
            tenant_id=tenant.id, consultation_id=consultation_id,
            name="Hemograma", study_type="laboratory",
        ),
        Sale(
            tenant_id=tenant.id, patient_id=patient_id,
            owner_id=uuid.UUID(patient["owner_id"]), patient_name_snapshot=name,
            patient_species_snapshot="Canine", sale_date=date(2026, 5, 10), currency="ARS",
        ),
    ])
    db.commit()
    return patient_id


def test_delete_complete_history_preserves_other_patients_and_tenants(
    client, db_session, tenant, other_tenant,
):
    patient_id = _create_complete_history(client, db_session, tenant)
    _create_complete_history(client, db_session, tenant, "Otro paciente")
    _create_complete_history(client, db_session, other_tenant, "Paciente ajeno")
    before = _snapshot_tenant(db_session, tenant.id)
    foreign_before = _snapshot_tenant(db_session, other_tenant.id)
    patient_ids = {row.id for row in before["patients"] if row.id != patient_id}

    response = client.delete(
        f"/api/v1/patients/{patient_id}", headers=veterinarian_headers(tenant)
    )

    assert response.status_code == 204, response.text
    after = _snapshot_tenant(db_session, tenant.id)
    assert _snapshot_tenant(db_session, other_tenant.id) == foreign_before
    consultation_ids = {
        row.id for row in before["consultations"] if row.patient_id == patient_id
    }
    for model in DELETED_MODELS:
        table = model.__tablename__
        if model is Patient:
            expected = [row for row in before[table] if row.id in patient_ids]
        elif model in (ConsultationMedication, ConsultationStudyRequest):
            expected = [row for row in before[table] if row.consultation_id not in consultation_ids]
        else:
            expected = [row for row in before[table] if row.patient_id != patient_id]
        assert after[table] == expected, table

    assert after["inventory_items"] == before["inventory_items"]
    for old, new in zip(before["inventory_movements"], after["inventory_movements"], strict=True):
        if old.related_patient_id == patient_id or old.related_consultation_id in consultation_ids:
            assert new.related_patient_id is None
            assert new.related_consultation_id is None
            # Only association fields and the automatic timestamp may change.
            excluded = {"related_patient_id", "related_consultation_id", "updated_at"}
            assert {k: v for k, v in new._mapping.items() if k not in excluded} == {
                k: v for k, v in old._mapping.items() if k not in excluded
            }
        else:
            assert new == old
    for old, new in zip(before["sales"], after["sales"], strict=True):
        assert dict(new._mapping) == {
            **dict(old._mapping), "patient_id": None if old.patient_id == patient_id else old.patient_id,
        }


@pytest.mark.parametrize("failure_at", ["intermediate_delete", "patient_flush", "commit"])
def test_delete_patient_rolls_back_every_database_change(
    client, db_session, tenant, monkeypatch, failure_at,
):
    patient_id = _create_complete_history(client, db_session, tenant)
    headers = veterinarian_headers(tenant)
    before = _snapshot_tenant(db_session, tenant.id)

    def fail(*args, **kwargs):
        raise RuntimeError("injected deletion failure")

    with monkeypatch.context() as patch:
        if failure_at == "intermediate_delete":
            execute = db_session.execute

            def fail_at_exam(statement, *args, **kwargs):
                if getattr(statement, "is_delete", False) and statement.table.name == "exams":
                    fail()
                return execute(statement, *args, **kwargs)

            patch.setattr(db_session, "execute", fail_at_exam)
        elif failure_at == "patient_flush":
            delete_patient = PatientRepository.delete

            def fail_after_flush(repository, patient):
                delete_patient(repository, patient)
                fail()

            patch.setattr(PatientRepository, "delete", fail_after_flush)
        else:
            patch.setattr(db_session, "commit", fail)

        with pytest.raises(RuntimeError, match="injected deletion failure"):
            client.delete(f"/api/v1/patients/{patient_id}", headers=headers)

    # No test-side rollback: the service must restore rows and leave a usable session.
    assert _snapshot_tenant(db_session, tenant.id) == before


def test_delete_foreign_patient_returns_404_without_changing_data(
    client, db_session, tenant, other_tenant,
):
    patient_id = _create_complete_history(client, db_session, other_tenant)
    before = _snapshot_tenant(db_session, other_tenant.id)
    response = client.delete(
        f"/api/v1/patients/{patient_id}", headers=veterinarian_headers(tenant)
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "patient_not_found"
    assert _snapshot_tenant(db_session, other_tenant.id) == before


def test_appointment_bulk_delete_filters_both_tenant_and_patient(
    client, db_session, tenant, other_tenant,
):
    patient = _create_patient_for_tenant(client, tenant)
    other_patient = _create_patient_for_tenant(client, tenant, "Otro")
    foreign_patient = _create_patient_for_tenant(client, other_tenant)
    target = _create_appointment(client, tenant, patient["id"])
    same_tenant = _create_appointment(client, tenant, other_patient["id"])
    foreign = _create_appointment(client, other_tenant, foreign_patient["id"])
    # Simulate a legacy inconsistent FK to prove tenant_id is enforced independently.
    foreign_row = db_session.scalar(
        select(Appointment).where(Appointment.id == uuid.UUID(foreign["id"]))
    )
    foreign_row.patient_id = uuid.UUID(patient["id"])
    db_session.commit()

    AppointmentRepository(db_session).delete_for_patient(tenant.id, uuid.UUID(patient["id"]))

    remaining = set(db_session.scalars(select(Appointment.id)).all())
    assert uuid.UUID(target["id"]) not in remaining
    assert {uuid.UUID(same_tenant["id"]), uuid.UUID(foreign["id"])} <= remaining

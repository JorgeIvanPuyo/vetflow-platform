"""Dashboard patient links must survive historically inconsistent tenant FKs."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.appointment import Appointment
from app.models.consultation import Consultation
from app.models.follow_up import FollowUp
from app.models.patient import Patient
from app.models.patient_file_reference import PatientFileReference
from app.models.patient_preventive_care import PatientPreventiveCare
from app.models.user import User
from app.repositories.dashboard import DashboardRepository
from app.tests.test_dashboard import _create_owner, _create_patient, _get_summary


WINDOW = {"date_from": "2026-04-24", "date_to": "2026-04-24"}
NOW = datetime(2026, 4, 24, 12, tzinfo=UTC)
WIDGETS = [
    ("upcoming_preventive_care", "preventive_care_upcoming", PatientPreventiveCare),
    ("recent_files", "files_recent", PatientFileReference),
]


@pytest.fixture()
def dashboard_case(db_session, tenant, other_tenant):
    owner = _create_owner(db_session, tenant, full_name="LOCAL OWNER")
    foreign_owner = _create_owner(db_session, other_tenant, full_name="FOREIGN OWNER")
    patient = _create_patient(db_session, tenant, owner, name="LOCAL PATIENT")
    foreign_patient = _create_patient(db_session, other_tenant, foreign_owner, name="FOREIGN PATIENT")
    local_user = User(
        tenant_id=tenant.id, email="local-dashboard@example.invalid",
        full_name="LOCAL INACTIVE AUTHOR", role="medico_veterinario", is_active=False,
    )
    foreign_user = User(
        tenant_id=other_tenant.id, email="foreign-dashboard@example.invalid",
        full_name="FOREIGN AUTHOR", role="medico_veterinario", is_active=True,
    )
    db_session.add_all([local_user, foreign_user])
    db_session.flush()
    local = {}; foreign = {}; corrupt = {}
    for key, _, model in WIDGETS:
        def make(row_tenant, row_patient, index, author):
            event = NOW + timedelta(minutes=index)
            fields = dict(
                tenant_id=row_tenant, patient_id=row_patient,
                created_by_user_id=author, name=f"Record {index}",
            )
            if model is PatientPreventiveCare:
                fields.update(care_type="other", applied_at=NOW, next_due_at=event)
            else:
                fields.update(file_type="other", uploaded_at=event, created_at=event)
            return model(**fields)

        local[key] = [make(tenant.id, patient.id, i, foreign_user.id if i == 0 else local_user.id) for i in range(3)]
        foreign[key] = make(other_tenant.id, foreign_patient.id, 3, foreign_user.id)
        corrupt[key] = make(tenant.id, foreign_patient.id, 4, foreign_user.id)
        # Root filtering and patient filtering must hold independently in both directions.
        foreign_root_local_patient = make(other_tenant.id, patient.id, 5, foreign_user.id)
        db_session.add_all([*local[key], foreign[key], corrupt[key], foreign_root_local_patient])
    db_session.commit()
    case = {
        "tenant_id": tenant.id, "patient_id": patient.id, "owner_id": owner.id,
        "foreign_tenant_id": other_tenant.id,
        "foreign_patient_id": foreign_patient.id, "foreign_owner_id": foreign_owner.id,
        "foreign_user_id": foreign_user.id, "local_user_id": local_user.id,
        "local": {key: [row.id for row in rows] for key, rows in local.items()},
        "foreign": {key: row.id for key, row in foreign.items()},
        "corrupt": {key: row.id for key, row in corrupt.items()},
    }
    db_session.expunge_all()
    return case


@pytest.mark.parametrize("widget,card,model", WIDGETS)
def test_widgets_exclude_corrupt_patient_links_and_keep_multiple_local_records(
    client, tenant, dashboard_case, widget, card, model,
):
    response = _get_summary(client, tenant, **WINDOW)
    assert response.status_code == 200
    data = response.json()["data"]
    expected = dashboard_case["local"][widget]
    if widget == "recent_files":
        expected = list(reversed(expected))
    assert [row["id"] for row in data[widget]] == list(map(str, expected))
    assert data["cards"][card] == 3
    assert all(row["patient_id"] == str(dashboard_case["patient_id"]) for row in data[widget])
    assert all(row["patient_name"] == "LOCAL PATIENT" for row in data[widget])
    assert "FOREIGN" not in response.text
    for key in ["foreign_patient_id", "foreign_owner_id", "foreign_user_id"]:
        assert str(dashboard_case[key]) not in response.text
    assert str(dashboard_case["corrupt"][widget]) not in response.text
    assert response.json()["meta"] == {}  # This endpoint has no pagination contract.


@pytest.mark.parametrize("widget,card,model", WIDGETS)
def test_other_tenant_cannot_see_local_roots_or_local_patient_links(
    client, dashboard_case, widget, card, model,
):
    response = client.get(
        "/api/v1/dashboard/summary",
        headers={"X-Tenant-Id": str(dashboard_case["foreign_tenant_id"])},
        params=WINDOW,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert [row["id"] for row in data[widget]] == [str(dashboard_case["foreign"][widget])]
    assert data["cards"][card] == 1
    assert data[widget][0]["patient_id"] == str(dashboard_case["foreign_patient_id"])
    assert str(dashboard_case["patient_id"]) not in response.text
    assert all(str(identity) not in response.text for identity in dashboard_case["local"][widget])


@pytest.mark.parametrize("widget,card,model", WIDGETS)
def test_scoped_repository_replaces_preloaded_foreign_authors(
    db_session, dashboard_case, widget, card, model,
):
    row = db_session.scalar(select(model).where(model.id == dashboard_case["local"][widget][0]))
    assert row.created_by_user.tenant_id != dashboard_case["tenant_id"]
    reader = DashboardRepository(db_session)
    method = reader.list_upcoming_preventive_care if model is PatientPreventiveCare else reader.list_recent_files
    rows = method(dashboard_case["tenant_id"], range_start=NOW - timedelta(hours=1), range_end=NOW + timedelta(hours=1))
    assert {record.id for record in rows} == set(dashboard_case["local"][widget])
    assert all(record.patient.tenant_id == dashboard_case["tenant_id"] for record in rows)
    assert next(record for record in rows if record.id == row.id).created_by_user is None
    assert all(record.created_by_user is None or record.created_by_user.tenant_id == dashboard_case["tenant_id"] for record in rows)


@pytest.mark.parametrize("widget,card,model", WIDGETS)
def test_same_tenant_inactive_author_and_archived_owner_remain_visible(
    client, db_session, tenant, dashboard_case, widget, card, model,
):
    from app.models.owner import Owner

    owner = db_session.scalar(select(Owner).where(Owner.id == dashboard_case["owner_id"], Owner.tenant_id == tenant.id))
    owner.is_active = False
    db_session.commit()
    response = _get_summary(client, tenant, **WINDOW)
    assert response.status_code == 200
    rows = response.json()["data"][widget]
    assert len(rows) == 3
    assert sum(row["created_by_user_name"] == "LOCAL INACTIVE AUTHOR" for row in rows) == 2
    assert sum(row["created_by_user_name"] is None for row in rows) == 1


def test_recent_files_keep_created_at_fallback_and_descending_order(client, db_session, tenant, dashboard_case):
    fallback = PatientFileReference(
        tenant_id=tenant.id, patient_id=dashboard_case["patient_id"], name="Fallback file",
        file_type="other", uploaded_at=None, created_at=NOW - timedelta(hours=1),
    )
    outside = PatientFileReference(
        tenant_id=tenant.id, patient_id=dashboard_case["patient_id"], name="Outside range",
        file_type="other", uploaded_at=None, created_at=NOW - timedelta(days=1),
    )
    db_session.add_all([fallback, outside]); db_session.commit()
    response = _get_summary(client, tenant, **WINDOW)
    assert response.status_code == 200
    data = response.json()["data"]
    assert [row["id"] for row in data["recent_files"]] == [*map(str, reversed(dashboard_case["local"]["recent_files"])), str(fallback.id)]
    assert data["recent_files"][-1]["uploaded_at"].startswith("2026-04-24T11:00:00")
    assert data["cards"]["files_recent"] == 4


def test_preventive_care_keeps_due_date_window_and_ascending_order(client, db_session, tenant, dashboard_case):
    db_session.add_all([
        PatientPreventiveCare(tenant_id=tenant.id, patient_id=dashboard_case["patient_id"], name="No due date", care_type="other", applied_at=NOW, next_due_at=None),
        PatientPreventiveCare(tenant_id=tenant.id, patient_id=dashboard_case["patient_id"], name="Outside range", care_type="other", applied_at=NOW, next_due_at=NOW + timedelta(days=1)),
    ])
    db_session.commit()
    response = _get_summary(client, tenant, **WINDOW)
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["data"]["upcoming_preventive_care"]] == list(map(str, dashboard_case["local"]["upcoming_preventive_care"]))
    assert response.json()["data"]["cards"]["preventive_care_upcoming"] == 3


def test_file_without_patient_keeps_required_patient_contract(client, db_session, tenant, dashboard_case):
    assert PatientFileReference.__table__.c.patient_id.nullable is False
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(PatientFileReference(tenant_id=tenant.id, patient_id=None, name="Invalid file", file_type="other"))
        db_session.flush()
    response = client.post(
        f"/api/v1/patients/{uuid.uuid4()}/file-references",
        headers={"X-Tenant-Id": str(tenant.id)}, json={"name": "Unlinked file", "file_type": "other"},
    )
    assert response.status_code == 404
    summary = _get_summary(client, tenant, **WINDOW)
    assert summary.status_code == 200
    assert summary.json()["data"]["cards"]["files_recent"] == 3


def test_all_dashboard_navigation_ids_and_labels_stay_in_tenant(client, db_session, tenant, dashboard_case):
    own_user = User(tenant_id=tenant.id, email="active-vet@example.invalid", full_name="LOCAL ACTIVE VET", role="medico_veterinario", is_active=True)
    db_session.add(own_user); db_session.flush()
    own_consultation = Consultation(tenant_id=tenant.id, patient_id=dashboard_case["patient_id"], reason="Local consultation", visit_date=NOW)
    invalid_consultation = Consultation(tenant_id=tenant.id, patient_id=dashboard_case["foreign_patient_id"], reason="Invalid consultation", visit_date=NOW)
    appointment = Appointment(tenant_id=tenant.id, patient_id=dashboard_case["foreign_patient_id"], owner_id=dashboard_case["foreign_owner_id"], assigned_user_id=dashboard_case["foreign_user_id"], title="Local appointment", appointment_type="consultation", start_at=NOW, end_at=NOW + timedelta(hours=1))
    follow_up = FollowUp(tenant_id=tenant.id, patient_id=dashboard_case["foreign_patient_id"], owner_id=dashboard_case["foreign_owner_id"], assigned_user_id=dashboard_case["foreign_user_id"], title="Local follow-up", follow_up_type="other", due_at=NOW)
    db_session.add_all([own_consultation, invalid_consultation, appointment, follow_up]); db_session.commit()
    response = _get_summary(client, tenant, **WINDOW)
    assert response.status_code == 200
    data = response.json()["data"]
    permitted = {str(dashboard_case["patient_id"]), str(own_user.id), str(own_consultation.id), str(appointment.id), str(follow_up.id)}
    permitted.update(str(identity) for values in dashboard_case["local"].values() for identity in values)
    for key in ["appointments_today", "upcoming_follow_ups", "overdue_follow_ups", "recent_consultations", "upcoming_preventive_care", "recent_files", "activity_by_veterinarian"]:
        for row in data[key]:
            assert all(value in permitted for field, value in row.items() if (field == "id" or field.endswith("_id")) and value is not None)
    assert [row["id"] for row in data["recent_consultations"]] == [str(own_consultation.id)]
    assert "FOREIGN" not in response.text
    for key in ["foreign_patient_id", "foreign_owner_id", "foreign_user_id"]:
        assert str(dashboard_case[key]) not in response.text

import uuid
from datetime import UTC, datetime, timedelta

from app.models.appointment import Appointment
from app.models.consultation import Consultation
from app.models.follow_up import FollowUp
from app.models.owner import Owner
from app.models.patient import Patient
from app.models.patient_file_reference import PatientFileReference
from app.models.patient_preventive_care import PatientPreventiveCare
from app.models.user import User


def _headers(tenant) -> dict[str, str]:
    return {"X-Tenant-Id": str(tenant.id)}


def _create_user(
    db_session,
    tenant,
    *,
    email: str,
    full_name: str,
    is_active: bool = True,
) -> User:
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=email,
        full_name=full_name,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_owner(
    db_session,
    tenant,
    *,
    full_name: str = "Owner Dashboard",
) -> Owner:
    owner = Owner(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        full_name=full_name,
        phone="555-1000",
    )
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)
    return owner


def _create_patient(
    db_session,
    tenant,
    owner,
    *,
    name: str = "Luna",
) -> Patient:
    patient = Patient(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        owner_id=owner.id,
        name=name,
        species="Canine",
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _get_summary(client, tenant, **params):
    return client.get(
        "/api/v1/dashboard/summary",
        headers=_headers(tenant),
        params=params,
    )


def test_dashboard_summary_success_with_empty_data(client, tenant):
    response = _get_summary(client, tenant)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["cards"] == {
        "appointments_today": 0,
        "follow_ups_upcoming": 0,
        "follow_ups_overdue": 0,
        "consultations_recent": 0,
        "preventive_care_upcoming": 0,
        "files_recent": 0,
    }
    assert payload["appointments_today"] == []
    assert payload["upcoming_follow_ups"] == []
    assert payload["overdue_follow_ups"] == []
    assert payload["recent_consultations"] == []
    assert payload["upcoming_preventive_care"] == []
    assert payload["recent_files"] == []
    assert payload["activity_by_veterinarian"] == []


def test_dashboard_summary_includes_appointments_today(client, db_session, tenant):
    now = datetime.now(UTC)
    owner = _create_owner(db_session, tenant)
    patient = _create_patient(db_session, tenant, owner)
    vet = _create_user(
        db_session,
        tenant,
        email="agenda@example.com",
        full_name="Agenda Vet",
    )
    appointment = Appointment(
        tenant_id=tenant.id,
        patient_id=patient.id,
        owner_id=owner.id,
        assigned_user_id=vet.id,
        title="Control de hoy",
        reason="Seguimiento",
        appointment_type="consultation",
        status="scheduled",
        start_at=now + timedelta(hours=1),
        end_at=now + timedelta(hours=2),
    )
    db_session.add(appointment)
    db_session.commit()

    response = _get_summary(client, tenant)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["cards"]["appointments_today"] == 1
    assert payload["appointments_today"][0]["title"] == "Control de hoy"
    assert payload["appointments_today"][0]["patient_name"] == "Luna"
    assert payload["appointments_today"][0]["owner_name"] == "Owner Dashboard"
    assert payload["appointments_today"][0]["assigned_user_name"] == "Agenda Vet"


def test_dashboard_summary_includes_upcoming_follow_ups(client, db_session, tenant):
    now = datetime.now(UTC)
    owner = _create_owner(db_session, tenant)
    patient = _create_patient(db_session, tenant, owner)
    vet = _create_user(
        db_session,
        tenant,
        email="followup@example.com",
        full_name="Follow-up Vet",
    )
    follow_up = FollowUp(
        tenant_id=tenant.id,
        patient_id=patient.id,
        owner_id=owner.id,
        assigned_user_id=vet.id,
        title="Próxima vacuna",
        follow_up_type="vaccine",
        status="scheduled",
        due_at=now + timedelta(days=2),
    )
    db_session.add(follow_up)
    db_session.commit()

    response = _get_summary(client, tenant)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["cards"]["follow_ups_upcoming"] == 1
    assert payload["upcoming_follow_ups"][0]["title"] == "Próxima vacuna"
    assert payload["upcoming_follow_ups"][0]["patient_name"] == "Luna"
    assert payload["upcoming_follow_ups"][0]["assigned_user_name"] == "Follow-up Vet"


def test_dashboard_summary_includes_overdue_follow_ups(client, db_session, tenant):
    now = datetime.now(UTC)
    owner = _create_owner(db_session, tenant)
    patient = _create_patient(db_session, tenant, owner)
    follow_up = FollowUp(
        tenant_id=tenant.id,
        patient_id=patient.id,
        owner_id=owner.id,
        title="Control vencido",
        follow_up_type="consultation_control",
        status="pending",
        due_at=now - timedelta(days=1),
    )
    db_session.add(follow_up)
    db_session.commit()

    response = _get_summary(client, tenant)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["cards"]["follow_ups_overdue"] == 1
    assert payload["overdue_follow_ups"][0]["title"] == "Control vencido"


def test_dashboard_summary_includes_recent_consultations(client, db_session, tenant):
    now = datetime.now(UTC)
    owner = _create_owner(db_session, tenant)
    patient = _create_patient(db_session, tenant, owner)
    created_by = _create_user(
        db_session,
        tenant,
        email="created@example.com",
        full_name="Created Vet",
    )
    attending = _create_user(
        db_session,
        tenant,
        email="attending@example.com",
        full_name="Attending Vet",
    )
    consultation = Consultation(
        tenant_id=tenant.id,
        patient_id=patient.id,
        created_by_user_id=created_by.id,
        attending_user_id=attending.id,
        visit_date=now - timedelta(days=2),
        reason="Consulta reciente",
        status="completed",
    )
    db_session.add(consultation)
    db_session.commit()

    response = _get_summary(client, tenant)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["cards"]["consultations_recent"] == 1
    assert payload["recent_consultations"][0]["reason"] == "Consulta reciente"
    assert payload["recent_consultations"][0]["attending_user_name"] == "Attending Vet"
    assert payload["recent_consultations"][0]["created_by_user_name"] == "Created Vet"


def test_dashboard_summary_includes_upcoming_preventive_care(client, db_session, tenant):
    now = datetime.now(UTC)
    owner = _create_owner(db_session, tenant)
    patient = _create_patient(db_session, tenant, owner)
    created_by = _create_user(
        db_session,
        tenant,
        email="preventive@example.com",
        full_name="Preventive Vet",
    )
    record = PatientPreventiveCare(
        tenant_id=tenant.id,
        patient_id=patient.id,
        created_by_user_id=created_by.id,
        name="Vacuna anual",
        care_type="vaccine",
        applied_at=now - timedelta(days=30),
        next_due_at=now + timedelta(days=10),
    )
    db_session.add(record)
    db_session.commit()

    response = _get_summary(client, tenant)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["cards"]["preventive_care_upcoming"] == 1
    assert payload["upcoming_preventive_care"][0]["name"] == "Vacuna anual"
    assert payload["upcoming_preventive_care"][0]["created_by_user_name"] == "Preventive Vet"


def test_dashboard_summary_includes_recent_files(client, db_session, tenant):
    now = datetime.now(UTC)
    owner = _create_owner(db_session, tenant)
    patient = _create_patient(db_session, tenant, owner)
    created_by = _create_user(
        db_session,
        tenant,
        email="files@example.com",
        full_name="Files Vet",
    )
    file_reference = PatientFileReference(
        tenant_id=tenant.id,
        patient_id=patient.id,
        created_by_user_id=created_by.id,
        name="Radiografía tórax",
        file_type="radiography",
        uploaded_at=now - timedelta(days=1),
    )
    db_session.add(file_reference)
    db_session.commit()

    response = _get_summary(client, tenant)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["cards"]["files_recent"] == 1
    assert payload["recent_files"][0]["name"] == "Radiografía tórax"
    assert payload["recent_files"][0]["created_by_user_name"] == "Files Vet"


def test_dashboard_summary_filters_by_assigned_user_id(client, db_session, tenant):
    now = datetime.now(UTC)
    owner = _create_owner(db_session, tenant)
    patient = _create_patient(db_session, tenant, owner)
    target_vet = _create_user(
        db_session,
        tenant,
        email="target@example.com",
        full_name="Target Vet",
    )
    other_vet = _create_user(
        db_session,
        tenant,
        email="other@example.com",
        full_name="Other Vet",
    )
    db_session.add_all(
        [
            Appointment(
                tenant_id=tenant.id,
                patient_id=patient.id,
                owner_id=owner.id,
                assigned_user_id=target_vet.id,
                title="Turno target",
                appointment_type="consultation",
                status="scheduled",
                start_at=now + timedelta(hours=2),
                end_at=now + timedelta(hours=3),
            ),
            Appointment(
                tenant_id=tenant.id,
                patient_id=patient.id,
                owner_id=owner.id,
                assigned_user_id=other_vet.id,
                title="Turno other",
                appointment_type="consultation",
                status="scheduled",
                start_at=now + timedelta(hours=4),
                end_at=now + timedelta(hours=5),
            ),
            FollowUp(
                tenant_id=tenant.id,
                patient_id=patient.id,
                owner_id=owner.id,
                assigned_user_id=target_vet.id,
                title="Seguimiento target",
                follow_up_type="other",
                status="pending",
                due_at=now + timedelta(days=1),
            ),
            FollowUp(
                tenant_id=tenant.id,
                patient_id=patient.id,
                owner_id=owner.id,
                assigned_user_id=other_vet.id,
                title="Seguimiento other",
                follow_up_type="other",
                status="pending",
                due_at=now + timedelta(days=1),
            ),
            Consultation(
                tenant_id=tenant.id,
                patient_id=patient.id,
                created_by_user_id=target_vet.id,
                attending_user_id=target_vet.id,
                visit_date=now - timedelta(days=1),
                reason="Consulta target",
                status="completed",
            ),
            Consultation(
                tenant_id=tenant.id,
                patient_id=patient.id,
                created_by_user_id=other_vet.id,
                attending_user_id=other_vet.id,
                visit_date=now - timedelta(days=1),
                reason="Consulta other",
                status="completed",
            ),
        ]
    )
    db_session.commit()

    response = _get_summary(client, tenant, assigned_user_id=str(target_vet.id))

    assert response.status_code == 200
    payload = response.json()["data"]
    assert [item["title"] for item in payload["appointments_today"]] == ["Turno target"]
    assert [item["title"] for item in payload["upcoming_follow_ups"]] == ["Seguimiento target"]
    assert [item["reason"] for item in payload["recent_consultations"]] == ["Consulta target"]
    assert payload["activity_by_veterinarian"][0]["full_name"] == "Target Vet"


def test_dashboard_summary_rejects_assigned_user_from_other_tenant(
    client,
    db_session,
    tenant,
    other_tenant,
):
    foreign_user = _create_user(
        db_session,
        other_tenant,
        email="foreign@example.com",
        full_name="Foreign Vet",
    )

    response = _get_summary(client, tenant, assigned_user_id=str(foreign_user.id))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_cross_tenant_access"


def test_dashboard_summary_does_not_leak_cross_tenant_data(
    client,
    db_session,
    tenant,
    other_tenant,
):
    now = datetime.now(UTC)
    owner = _create_owner(db_session, other_tenant, full_name="Foreign Owner")
    patient = _create_patient(db_session, other_tenant, owner, name="Foreign Pet")
    vet = _create_user(
        db_session,
        other_tenant,
        email="foreign-dashboard@example.com",
        full_name="Foreign Dashboard Vet",
    )
    db_session.add_all(
        [
            Appointment(
                tenant_id=other_tenant.id,
                patient_id=patient.id,
                owner_id=owner.id,
                assigned_user_id=vet.id,
                title="Turno ajeno",
                appointment_type="consultation",
                status="scheduled",
                start_at=now + timedelta(hours=1),
                end_at=now + timedelta(hours=2),
            ),
            FollowUp(
                tenant_id=other_tenant.id,
                patient_id=patient.id,
                owner_id=owner.id,
                assigned_user_id=vet.id,
                title="Seguimiento ajeno",
                follow_up_type="other",
                status="pending",
                due_at=now + timedelta(days=1),
            ),
        ]
    )
    db_session.commit()

    response = _get_summary(client, tenant)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["cards"]["appointments_today"] == 0
    assert payload["cards"]["follow_ups_upcoming"] == 0
    assert payload["appointments_today"] == []
    assert payload["upcoming_follow_ups"] == []


def test_dashboard_summary_cards_contain_expected_counters(client, db_session, tenant):
    now = datetime.now(UTC)
    owner = _create_owner(db_session, tenant)
    patient = _create_patient(db_session, tenant, owner)
    vet = _create_user(
        db_session,
        tenant,
        email="cards@example.com",
        full_name="Cards Vet",
    )
    db_session.add_all(
        [
            Appointment(
                tenant_id=tenant.id,
                patient_id=patient.id,
                owner_id=owner.id,
                assigned_user_id=vet.id,
                title="Turno cards",
                appointment_type="consultation",
                status="scheduled",
                start_at=now + timedelta(hours=2),
                end_at=now + timedelta(hours=3),
            ),
            FollowUp(
                tenant_id=tenant.id,
                patient_id=patient.id,
                owner_id=owner.id,
                assigned_user_id=vet.id,
                title="Seguimiento próximo",
                follow_up_type="other",
                status="pending",
                due_at=now + timedelta(days=2),
            ),
            FollowUp(
                tenant_id=tenant.id,
                patient_id=patient.id,
                owner_id=owner.id,
                assigned_user_id=vet.id,
                title="Seguimiento vencido",
                follow_up_type="other",
                status="scheduled",
                due_at=now - timedelta(days=2),
            ),
            Consultation(
                tenant_id=tenant.id,
                patient_id=patient.id,
                created_by_user_id=vet.id,
                attending_user_id=vet.id,
                visit_date=now - timedelta(days=1),
                reason="Consulta cards",
                status="completed",
            ),
            PatientPreventiveCare(
                tenant_id=tenant.id,
                patient_id=patient.id,
                created_by_user_id=vet.id,
                name="Vacuna cards",
                care_type="vaccine",
                applied_at=now - timedelta(days=60),
                next_due_at=now + timedelta(days=15),
            ),
            PatientFileReference(
                tenant_id=tenant.id,
                patient_id=patient.id,
                created_by_user_id=vet.id,
                name="Archivo cards",
                file_type="document",
                uploaded_at=now - timedelta(days=1),
            ),
        ]
    )
    db_session.commit()

    response = _get_summary(client, tenant)

    assert response.status_code == 200
    cards = response.json()["data"]["cards"]
    assert cards == {
        "appointments_today": 1,
        "follow_ups_upcoming": 1,
        "follow_ups_overdue": 1,
        "consultations_recent": 1,
        "preventive_care_upcoming": 1,
        "files_recent": 1,
    }


def test_dashboard_summary_activity_by_veterinarian_includes_same_tenant_users_only(
    client,
    db_session,
    tenant,
    other_tenant,
):
    now = datetime.now(UTC)
    owner = _create_owner(db_session, tenant)
    patient = _create_patient(db_session, tenant, owner)
    active_vet = _create_user(
        db_session,
        tenant,
        email="activity@example.com",
        full_name="Activity Vet",
    )
    _create_user(
        db_session,
        other_tenant,
        email="outside@example.com",
        full_name="Outside Vet",
    )
    db_session.add_all(
        [
            Appointment(
                tenant_id=tenant.id,
                patient_id=patient.id,
                owner_id=owner.id,
                assigned_user_id=active_vet.id,
                title="Turno actividad",
                appointment_type="consultation",
                status="scheduled",
                start_at=now + timedelta(hours=1),
                end_at=now + timedelta(hours=2),
            ),
            Consultation(
                tenant_id=tenant.id,
                patient_id=patient.id,
                created_by_user_id=active_vet.id,
                attending_user_id=active_vet.id,
                visit_date=now - timedelta(days=1),
                reason="Consulta actividad",
                status="completed",
            ),
            FollowUp(
                tenant_id=tenant.id,
                patient_id=patient.id,
                owner_id=owner.id,
                assigned_user_id=active_vet.id,
                title="Seguimiento actividad",
                follow_up_type="other",
                status="pending",
                due_at=now + timedelta(days=1),
            ),
        ]
    )
    db_session.commit()

    response = _get_summary(client, tenant)

    assert response.status_code == 200
    activity = response.json()["data"]["activity_by_veterinarian"]
    assert len(activity) == 1
    assert activity[0]["full_name"] == "Activity Vet"
    assert activity[0]["email"] == "activity@example.com"
    assert activity[0]["appointments_today_count"] == 1
    assert activity[0]["consultations_recent_count"] == 1
    assert activity[0]["follow_ups_pending_count"] == 1

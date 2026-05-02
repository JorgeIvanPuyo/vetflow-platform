import uuid

from app.models.appointment import Appointment
from app.models.user import User


def _headers(tenant) -> dict[str, str]:
    return {"X-Tenant-Id": str(tenant.id)}


def _auth_headers(email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {email}"}


def _setup_auth(monkeypatch) -> None:
    import app.core.tenant as tenant_core

    monkeypatch.setattr(
        tenant_core,
        "verify_id_token",
        lambda token: {"email": token},
    )


def _create_user(db_session, tenant, email: str, full_name: str) -> User:
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=email,
        full_name=full_name,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_owner(client, tenant, full_name: str = "Follow-up Owner") -> dict:
    response = client.post(
        "/api/v1/owners",
        headers=_headers(tenant),
        json={"full_name": full_name, "phone": "555-1000"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_patient(client, tenant, owner_id: str, name: str = "Luna") -> dict:
    response = client.post(
        "/api/v1/patients",
        headers=_headers(tenant),
        json={"owner_id": owner_id, "name": name, "species": "Canine"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_patient_for_tenant(client, tenant, name: str = "Luna") -> tuple[dict, dict]:
    owner = _create_owner(client, tenant, f"{name} Owner")
    patient = _create_patient(client, tenant, owner["id"], name)
    return owner, patient


def _follow_up_payload(**overrides) -> dict:
    payload = {
        "title": "Próximo control",
        "description": "Revisión clínica en dos semanas",
        "follow_up_type": "consultation_control",
        "due_at": "2026-05-20T09:00:00Z",
        "notes": "Traer estudios previos",
    }
    payload.update(overrides)
    return payload


def _create_follow_up(client, tenant, **overrides) -> dict:
    response = client.post(
        "/api/v1/follow-ups",
        headers=_headers(tenant),
        json=_follow_up_payload(**overrides),
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_create_follow_up_successfully(client, tenant):
    owner, patient = _create_patient_for_tenant(client, tenant)

    response = client.post(
        "/api/v1/follow-ups",
        headers=_headers(tenant),
        json=_follow_up_payload(patient_id=patient["id"], owner_id=owner["id"]),
    )

    assert response.status_code == 201
    follow_up = response.json()["data"]
    assert follow_up["tenant_id"] == str(tenant.id)
    assert follow_up["patient_id"] == patient["id"]
    assert follow_up["owner_id"] == owner["id"]
    assert follow_up["status"] == "pending"
    assert follow_up["patient_name"] == "Luna"
    assert follow_up["owner_name"] == "Luna Owner"


def test_create_follow_up_with_appointment(client, db_session, tenant):
    owner, patient = _create_patient_for_tenant(client, tenant)
    vet = _create_user(db_session, tenant, "agenda@example.com", "Agenda Vet")

    response = client.post(
        "/api/v1/follow-ups",
        headers=_headers(tenant),
        json=_follow_up_payload(
            patient_id=patient["id"],
            owner_id=owner["id"],
            assigned_user_id=str(vet.id),
            create_appointment=True,
            appointment_duration_minutes=45,
        ),
    )

    assert response.status_code == 201
    follow_up = response.json()["data"]
    assert follow_up["status"] == "scheduled"
    assert follow_up["appointment_id"] is not None
    appointment = db_session.get(Appointment, uuid.UUID(follow_up["appointment_id"]))
    assert appointment is not None
    assert appointment.title == "Próximo control"


def test_created_appointment_has_correct_patient_user_type_and_date(
    client,
    db_session,
    tenant,
):
    owner, patient = _create_patient_for_tenant(client, tenant)
    vet = _create_user(db_session, tenant, "vet@example.com", "Follow-up Vet")

    follow_up = _create_follow_up(
        client,
        tenant,
        patient_id=patient["id"],
        owner_id=owner["id"],
        assigned_user_id=str(vet.id),
        follow_up_type="exam_review",
        due_at="2026-05-21T10:00:00Z",
        create_appointment=True,
        appointment_duration_minutes=30,
    )

    appointment = db_session.get(Appointment, uuid.UUID(follow_up["appointment_id"]))
    assert appointment is not None
    assert appointment.patient_id == uuid.UUID(patient["id"])
    assert appointment.owner_id == uuid.UUID(owner["id"])
    assert appointment.assigned_user_id == vet.id
    assert appointment.appointment_type == "exam"
    assert appointment.start_at.isoformat().startswith("2026-05-21T10:00:00")
    assert appointment.end_at.isoformat().startswith("2026-05-21T10:30:00")


def test_reject_patient_from_other_tenant(client, tenant, other_tenant):
    foreign_owner, foreign_patient = _create_patient_for_tenant(client, other_tenant, "Nina")

    response = client.post(
        "/api/v1/follow-ups",
        headers=_headers(tenant),
        json=_follow_up_payload(
            patient_id=foreign_patient["id"],
            owner_id=foreign_owner["id"],
        ),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_cross_tenant_access"


def test_reject_assigned_user_id_from_other_tenant(
    client,
    db_session,
    tenant,
    other_tenant,
):
    owner, patient = _create_patient_for_tenant(client, tenant)
    foreign_vet = _create_user(
        db_session,
        other_tenant,
        "foreign@example.com",
        "Foreign Vet",
    )

    response = client.post(
        "/api/v1/follow-ups",
        headers=_headers(tenant),
        json=_follow_up_payload(
            patient_id=patient["id"],
            owner_id=owner["id"],
            assigned_user_id=str(foreign_vet.id),
        ),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_cross_tenant_access"


def test_list_follow_ups_by_date_range(client, tenant):
    owner, patient = _create_patient_for_tenant(client, tenant)
    included = _create_follow_up(
        client,
        tenant,
        patient_id=patient["id"],
        owner_id=owner["id"],
        due_at="2026-05-20T09:00:00Z",
    )
    _create_follow_up(
        client,
        tenant,
        patient_id=patient["id"],
        owner_id=owner["id"],
        due_at="2026-06-20T09:00:00Z",
        title="Fuera de rango",
    )

    response = client.get(
        "/api/v1/follow-ups",
        headers=_headers(tenant),
        params={
            "date_from": "2026-05-01T00:00:00Z",
            "date_to": "2026-05-31T23:59:59Z",
        },
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == [included["id"]]


def test_list_follow_ups_by_assigned_user_id(client, db_session, tenant):
    owner, patient = _create_patient_for_tenant(client, tenant)
    included_vet = _create_user(db_session, tenant, "included@example.com", "Included Vet")
    excluded_vet = _create_user(db_session, tenant, "excluded@example.com", "Excluded Vet")
    included = _create_follow_up(
        client,
        tenant,
        patient_id=patient["id"],
        owner_id=owner["id"],
        assigned_user_id=str(included_vet.id),
    )
    _create_follow_up(
        client,
        tenant,
        patient_id=patient["id"],
        owner_id=owner["id"],
        assigned_user_id=str(excluded_vet.id),
        title="Seguimiento alterno",
    )

    response = client.get(
        "/api/v1/follow-ups",
        headers=_headers(tenant),
        params={"assigned_user_id": str(included_vet.id)},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == [included["id"]]


def test_get_follow_up_by_id(client, tenant):
    owner, patient = _create_patient_for_tenant(client, tenant)
    follow_up = _create_follow_up(
        client,
        tenant,
        patient_id=patient["id"],
        owner_id=owner["id"],
    )

    response = client.get(
        f"/api/v1/follow-ups/{follow_up['id']}",
        headers=_headers(tenant),
    )

    assert response.status_code == 200
    assert response.json()["data"]["id"] == follow_up["id"]


def test_update_follow_up_status(client, tenant):
    owner, patient = _create_patient_for_tenant(client, tenant)
    follow_up = _create_follow_up(
        client,
        tenant,
        patient_id=patient["id"],
        owner_id=owner["id"],
    )

    response = client.patch(
        f"/api/v1/follow-ups/{follow_up['id']}",
        headers=_headers(tenant),
        json={"status": "scheduled"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "scheduled"


def test_complete_follow_up_sets_completed_at(client, tenant):
    owner, patient = _create_patient_for_tenant(client, tenant)
    follow_up = _create_follow_up(
        client,
        tenant,
        patient_id=patient["id"],
        owner_id=owner["id"],
    )

    response = client.post(
        f"/api/v1/follow-ups/{follow_up['id']}/complete",
        headers=_headers(tenant),
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "completed"
    assert body["completed_at"] is not None


def test_cancel_follow_up_sets_cancelled_at(client, tenant):
    owner, patient = _create_patient_for_tenant(client, tenant)
    follow_up = _create_follow_up(
        client,
        tenant,
        patient_id=patient["id"],
        owner_id=owner["id"],
    )

    response = client.post(
        f"/api/v1/follow-ups/{follow_up['id']}/cancel",
        headers=_headers(tenant),
        json={"notes": "Paciente reagendado"},
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "cancelled"
    assert body["cancelled_at"] is not None
    assert "Paciente reagendado" in (body["notes"] or "")


def test_delete_follow_up_preserves_linked_appointment(client, db_session, tenant):
    owner, patient = _create_patient_for_tenant(client, tenant)
    follow_up = _create_follow_up(
        client,
        tenant,
        patient_id=patient["id"],
        owner_id=owner["id"],
        create_appointment=True,
    )

    appointment_id = uuid.UUID(follow_up["appointment_id"])
    response = client.delete(
        f"/api/v1/follow-ups/{follow_up['id']}",
        headers=_headers(tenant),
    )

    assert response.status_code == 204
    assert db_session.get(Appointment, appointment_id) is not None


def test_prevent_cross_tenant_read_update_delete(client, tenant, other_tenant):
    foreign_owner, foreign_patient = _create_patient_for_tenant(client, other_tenant, "Nina")
    foreign_follow_up = _create_follow_up(
        client,
        other_tenant,
        patient_id=foreign_patient["id"],
        owner_id=foreign_owner["id"],
    )

    get_response = client.get(
        f"/api/v1/follow-ups/{foreign_follow_up['id']}",
        headers=_headers(tenant),
    )
    patch_response = client.patch(
        f"/api/v1/follow-ups/{foreign_follow_up['id']}",
        headers=_headers(tenant),
        json={"title": "Hack"},
    )
    delete_response = client.delete(
        f"/api/v1/follow-ups/{foreign_follow_up['id']}",
        headers=_headers(tenant),
    )

    assert get_response.status_code == 404
    assert patch_response.status_code == 404
    assert delete_response.status_code == 404


def test_clinical_history_includes_follow_up(client, tenant):
    owner, patient = _create_patient_for_tenant(client, tenant)
    follow_up = _create_follow_up(
        client,
        tenant,
        patient_id=patient["id"],
        owner_id=owner["id"],
        follow_up_type="vaccine",
        due_at="2026-05-18T08:00:00Z",
        description="Aplicar refuerzo anual",
    )

    response = client.get(
        f"/api/v1/patients/{patient['id']}/clinical-history",
        headers=_headers(tenant),
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["follow_ups"][0]["id"] == follow_up["id"]
    assert any(
        item["type"] == "follow_up"
        and item["id"] == follow_up["id"]
        and item["title"] == "Próximo control"
        and item["summary"] == "Aplicar refuerzo anual"
        for item in body["timeline"]
    )


def test_clinical_history_does_not_leak_cross_tenant_follow_ups(
    client,
    tenant,
    other_tenant,
):
    owner, patient = _create_patient_for_tenant(client, tenant)
    foreign_owner, foreign_patient = _create_patient_for_tenant(client, other_tenant, "Nina")
    local_follow_up = _create_follow_up(
        client,
        tenant,
        patient_id=patient["id"],
        owner_id=owner["id"],
    )
    foreign_follow_up = _create_follow_up(
        client,
        other_tenant,
        patient_id=foreign_patient["id"],
        owner_id=foreign_owner["id"],
    )

    response = client.get(
        f"/api/v1/patients/{patient['id']}/clinical-history",
        headers=_headers(tenant),
    )

    assert response.status_code == 200
    timeline_ids = [item["id"] for item in response.json()["data"]["timeline"]]
    assert local_follow_up["id"] in timeline_ids
    assert foreign_follow_up["id"] not in timeline_ids


def test_response_includes_patient_and_user_display_fields_when_available(
    client,
    db_session,
    tenant,
    monkeypatch,
):
    _setup_auth(monkeypatch)
    vet = _create_user(db_session, tenant, "followup@example.com", "Follow-up Vet")
    owner_response = client.post(
        "/api/v1/owners",
        headers=_auth_headers(vet.email),
        json={"full_name": "Display Owner", "phone": "555-1000"},
    )
    assert owner_response.status_code == 201
    owner = owner_response.json()["data"]

    patient_response = client.post(
        "/api/v1/patients",
        headers=_auth_headers(vet.email),
        json={"owner_id": owner["id"], "name": "Mora", "species": "Feline"},
    )
    assert patient_response.status_code == 201
    patient = patient_response.json()["data"]

    response = client.post(
        "/api/v1/follow-ups",
        headers=_auth_headers(vet.email),
        json=_follow_up_payload(
            patient_id=patient["id"],
            owner_id=owner["id"],
            assigned_user_id=str(vet.id),
        ),
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["patient_name"] == "Mora"
    assert body["owner_name"] == "Display Owner"
    assert body["assigned_user_name"] == "Follow-up Vet"
    assert body["assigned_user_email"] == "followup@example.com"
    assert body["created_by_user_id"] == str(vet.id)
    assert body["created_by_user_name"] == "Follow-up Vet"
    assert body["created_by_user_email"] == "followup@example.com"

import uuid

from app.core.tenant import get_tenant_context
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


def _create_owner(client, tenant, full_name: str = "Agenda Owner") -> dict:
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


def _appointment_payload(**overrides) -> dict:
    payload = {
        "title": "Control general",
        "reason": "Seguimiento clínico",
        "appointment_type": "consultation",
        "status": "scheduled",
        "start_at": "2026-05-10T10:00:00Z",
        "end_at": "2026-05-10T10:30:00Z",
        "notes": "Traer resultados previos",
    }
    payload.update(overrides)
    return payload


def _create_appointment(client, tenant, **overrides) -> dict:
    response = client.post(
        "/api/v1/appointments",
        headers=_headers(tenant),
        json=_appointment_payload(**overrides),
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_create_appointment_successfully(client, tenant):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])

    response = client.post(
        "/api/v1/appointments",
        headers=_headers(tenant),
        json=_appointment_payload(patient_id=patient["id"], owner_id=owner["id"]),
    )

    assert response.status_code == 201
    appointment = response.json()["data"]
    assert appointment["tenant_id"] == str(tenant.id)
    assert appointment["patient_id"] == patient["id"]
    assert appointment["owner_id"] == owner["id"]
    assert appointment["title"] == "Control general"
    assert appointment["status"] == "scheduled"
    assert appointment["patient_name"] == "Luna"
    assert appointment["owner_name"] == "Agenda Owner"


def test_create_appointment_assigned_to_same_tenant_veterinarian(
    client,
    db_session,
    tenant,
):
    vet = _create_user(db_session, tenant, "vet@example.com", "Agenda Vet")

    response = client.post(
        "/api/v1/appointments",
        headers=_headers(tenant),
        json=_appointment_payload(assigned_user_id=str(vet.id)),
    )

    assert response.status_code == 201
    appointment = response.json()["data"]
    assert appointment["assigned_user_id"] == str(vet.id)
    assert appointment["assigned_user_name"] == "Agenda Vet"
    assert appointment["assigned_user_email"] == "vet@example.com"


def test_create_appointment_rejects_assigned_user_from_other_tenant(
    client,
    db_session,
    tenant,
    other_tenant,
):
    foreign_vet = _create_user(
        db_session,
        other_tenant,
        "foreign-vet@example.com",
        "Foreign Vet",
    )

    response = client.post(
        "/api/v1/appointments",
        headers=_headers(tenant),
        json=_appointment_payload(assigned_user_id=str(foreign_vet.id)),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_cross_tenant_access"


def test_create_appointment_rejects_patient_from_other_tenant(
    client,
    tenant,
    other_tenant,
):
    foreign_owner = _create_owner(client, other_tenant, "Foreign Owner")
    foreign_patient = _create_patient(client, other_tenant, foreign_owner["id"], "Nina")

    response = client.post(
        "/api/v1/appointments",
        headers=_headers(tenant),
        json=_appointment_payload(patient_id=foreign_patient["id"]),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_cross_tenant_access"


def test_create_appointment_rejects_owner_from_other_tenant(
    client,
    tenant,
    other_tenant,
):
    foreign_owner = _create_owner(client, other_tenant, "Foreign Owner")

    response = client.post(
        "/api/v1/appointments",
        headers=_headers(tenant),
        json=_appointment_payload(owner_id=foreign_owner["id"]),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_cross_tenant_access"


def test_create_appointment_rejects_end_before_start(client, tenant):
    response = client.post(
        "/api/v1/appointments",
        headers=_headers(tenant),
        json=_appointment_payload(end_at="2026-05-10T09:30:00Z"),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_appointment_time"


def test_list_appointments_by_date_range(client, tenant):
    included = _create_appointment(
        client,
        tenant,
        title="Cita incluida",
        start_at="2026-05-10T10:00:00Z",
        end_at="2026-05-10T10:30:00Z",
    )
    _create_appointment(
        client,
        tenant,
        title="Cita fuera de rango",
        start_at="2026-06-10T10:00:00Z",
        end_at="2026-06-10T10:30:00Z",
    )

    response = client.get(
        "/api/v1/appointments",
        headers=_headers(tenant),
        params={
            "date_from": "2026-05-01T00:00:00Z",
            "date_to": "2026-05-31T23:59:59Z",
        },
    )

    assert response.status_code == 200
    appointments = response.json()["data"]
    assert [appointment["id"] for appointment in appointments] == [included["id"]]
    assert response.json()["meta"]["total"] == 1


def test_list_appointments_by_assigned_user_id(client, db_session, tenant):
    vet = _create_user(db_session, tenant, "assigned@example.com", "Assigned Vet")
    other_vet = _create_user(db_session, tenant, "other@example.com", "Other Vet")
    included = _create_appointment(
        client,
        tenant,
        assigned_user_id=str(vet.id),
        title="Cita de vet asignado",
    )
    _create_appointment(
        client,
        tenant,
        assigned_user_id=str(other_vet.id),
        title="Cita de otro vet",
    )

    response = client.get(
        "/api/v1/appointments",
        headers=_headers(tenant),
        params={
            "assigned_user_id": str(vet.id),
            "date_from": "2026-05-01T00:00:00Z",
            "date_to": "2026-05-31T23:59:59Z",
        },
    )

    assert response.status_code == 200
    appointments = response.json()["data"]
    assert [appointment["id"] for appointment in appointments] == [included["id"]]


def test_update_appointment_status(client, tenant):
    appointment = _create_appointment(client, tenant)

    response = client.patch(
        f"/api/v1/appointments/{appointment['id']}",
        headers=_headers(tenant),
        json={"status": "completed"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "completed"


def test_delete_appointment(client, tenant):
    appointment = _create_appointment(client, tenant)

    delete_response = client.delete(
        f"/api/v1/appointments/{appointment['id']}",
        headers=_headers(tenant),
    )
    get_response = client.get(
        f"/api/v1/appointments/{appointment['id']}",
        headers=_headers(tenant),
    )

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


def test_prevent_cross_tenant_read_update_delete(client, tenant, other_tenant):
    foreign_appointment = _create_appointment(client, other_tenant)

    get_response = client.get(
        f"/api/v1/appointments/{foreign_appointment['id']}",
        headers=_headers(tenant),
    )
    patch_response = client.patch(
        f"/api/v1/appointments/{foreign_appointment['id']}",
        headers=_headers(tenant),
        json={"status": "cancelled"},
    )
    delete_response = client.delete(
        f"/api/v1/appointments/{foreign_appointment['id']}",
        headers=_headers(tenant),
    )

    assert get_response.status_code == 404
    assert patch_response.status_code == 404
    assert delete_response.status_code == 404


def test_response_includes_display_names_when_available(
    client,
    db_session,
    tenant,
    monkeypatch,
):
    _setup_auth(monkeypatch)
    created_by = _create_user(db_session, tenant, "creator@example.com", "Creator Vet")
    assigned = _create_user(db_session, tenant, "assigned2@example.com", "Assigned Vet")
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])

    response = client.post(
        "/api/v1/appointments",
        headers=_auth_headers(created_by.email),
        json=_appointment_payload(
            patient_id=patient["id"],
            owner_id=owner["id"],
            assigned_user_id=str(assigned.id),
        ),
    )

    assert response.status_code == 201
    appointment = response.json()["data"]
    assert appointment["patient_name"] == "Luna"
    assert appointment["owner_name"] == "Agenda Owner"
    assert appointment["assigned_user_id"] == str(assigned.id)
    assert appointment["assigned_user_name"] == "Assigned Vet"
    assert appointment["assigned_user_email"] == "assigned2@example.com"
    assert appointment["created_by_user_id"] == str(created_by.id)
    assert appointment["created_by_user_name"] == "Creator Vet"
    assert appointment["created_by_user_email"] == "creator@example.com"

    client.app.dependency_overrides.pop(get_tenant_context, None)

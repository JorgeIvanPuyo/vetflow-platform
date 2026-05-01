import uuid

from app.models.patient import Patient
from app.models.user import User


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


def _auth_headers(email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {email}"}


def _setup_auth(monkeypatch) -> None:
    import app.core.tenant as tenant_core

    monkeypatch.setattr(
        tenant_core,
        "verify_id_token",
        lambda token: {"email": token},
    )


def _create_owner(client, email: str) -> dict:
    response = client.post(
        "/api/v1/owners",
        headers=_auth_headers(email),
        json={"full_name": "Trace Owner", "phone": "555-1000"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_patient(client, email: str, owner_id: str, name: str = "Luna") -> dict:
    response = client.post(
        "/api/v1/patients",
        headers=_auth_headers(email),
        json={"owner_id": owner_id, "name": name, "species": "Canine"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_preventive_care_creation_stores_and_returns_creator_display_data(
    client,
    db_session,
    tenant,
    monkeypatch,
):
    _setup_auth(monkeypatch)
    vet = _create_user(db_session, tenant, "care@example.com", "Care Vet")
    owner = _create_owner(client, vet.email)
    patient = _create_patient(client, vet.email, owner["id"])

    response = client.post(
        f"/api/v1/patients/{patient['id']}/preventive-care",
        headers=_auth_headers(vet.email),
        json={
            "name": "Rabia anual",
            "care_type": "vaccine",
            "applied_at": "2026-04-24T10:30:00Z",
        },
    )

    assert response.status_code == 201
    record = response.json()["data"]
    assert record["created_by_user_id"] == str(vet.id)
    assert record["created_by_user_name"] == "Care Vet"
    assert record["created_by_user_email"] == "care@example.com"


def test_file_reference_creation_stores_and_returns_creator_display_data(
    client,
    db_session,
    tenant,
    monkeypatch,
):
    _setup_auth(monkeypatch)
    vet = _create_user(db_session, tenant, "files@example.com", "Files Vet")
    owner = _create_owner(client, vet.email)
    patient = _create_patient(client, vet.email, owner["id"])

    response = client.post(
        f"/api/v1/patients/{patient['id']}/file-references",
        headers=_auth_headers(vet.email),
        json={
            "name": "Radiografía lateral",
            "file_type": "radiography",
            "external_url": "https://example.com/rx",
        },
    )

    assert response.status_code == 201
    file_reference = response.json()["data"]
    assert file_reference["created_by_user_id"] == str(vet.id)
    assert file_reference["created_by_user_name"] == "Files Vet"
    assert file_reference["created_by_user_email"] == "files@example.com"


def test_clinical_history_timeline_includes_user_traceability(
    client,
    db_session,
    tenant,
    monkeypatch,
):
    _setup_auth(monkeypatch)
    vet = _create_user(db_session, tenant, "history@example.com", "History Vet")
    owner = _create_owner(client, vet.email)
    patient = _create_patient(client, vet.email, owner["id"])

    consultation = client.post(
        "/api/v1/consultations",
        headers=_auth_headers(vet.email),
        json={
            "patient_id": patient["id"],
            "visit_date": "2026-04-24T10:30:00Z",
            "reason": "Control",
        },
    ).json()["data"]
    preventive_care = client.post(
        f"/api/v1/patients/{patient['id']}/preventive-care",
        headers=_auth_headers(vet.email),
        json={
            "name": "Rabia anual",
            "care_type": "vaccine",
            "applied_at": "2026-04-23T10:30:00Z",
        },
    ).json()["data"]
    file_reference = client.post(
        f"/api/v1/patients/{patient['id']}/file-references",
        headers=_auth_headers(vet.email),
        json={"name": "Informe externo", "file_type": "pdf"},
    ).json()["data"]
    exam = client.post(
        "/api/v1/exams",
        headers=_auth_headers(vet.email),
        json={
            "patient_id": patient["id"],
            "exam_type": "Hemograma",
            "requested_at": "2026-04-22T10:30:00Z",
        },
    ).json()["data"]

    response = client.get(
        f"/api/v1/patients/{patient['id']}/clinical-history",
        headers=_auth_headers(vet.email),
    )

    assert response.status_code == 200
    timeline_by_id = {item["id"]: item for item in response.json()["data"]["timeline"]}

    consultation_item = timeline_by_id[consultation["id"]]
    assert consultation_item["created_by"] == {
        "id": str(vet.id),
        "full_name": "History Vet",
        "email": "history@example.com",
    }
    assert consultation_item["attended_by"] == {
        "id": str(vet.id),
        "full_name": "History Vet",
        "email": "history@example.com",
    }

    preventive_item = timeline_by_id[preventive_care["id"]]
    assert preventive_item["created_by"] == {
        "id": str(vet.id),
        "full_name": "History Vet",
        "email": "history@example.com",
    }

    file_item = timeline_by_id[file_reference["id"]]
    assert file_item["created_by"] == {
        "id": str(vet.id),
        "full_name": "History Vet",
        "email": "history@example.com",
    }

    exam_item = timeline_by_id[exam["id"]]
    assert exam_item["requested_by"] == {
        "id": str(vet.id),
        "full_name": "History Vet",
        "email": "history@example.com",
    }


def test_traceability_display_never_leaks_users_from_another_tenant(
    client,
    db_session,
    tenant,
    other_tenant,
):
    owner_response = client.post(
        "/api/v1/owners",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"full_name": "Tenant Owner", "phone": "555-1000"},
    )
    assert owner_response.status_code == 201
    owner = owner_response.json()["data"]

    patient_response = client.post(
        "/api/v1/patients",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"owner_id": owner["id"], "name": "Mora", "species": "Feline"},
    )
    assert patient_response.status_code == 201
    patient_id = patient_response.json()["data"]["id"]

    foreign_user = _create_user(
        db_session,
        other_tenant,
        "foreign@example.com",
        "Foreign Vet",
    )
    patient = db_session.get(Patient, uuid.UUID(patient_id))
    assert patient is not None
    patient.created_by_user_id = foreign_user.id
    db_session.add(patient)
    db_session.commit()

    response = client.get(
        f"/api/v1/patients/{patient_id}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["created_by_user_id"] is None
    assert body["created_by_user_name"] is None
    assert body["created_by_user_email"] is None

import uuid

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


def _create_owner(client, email: str) -> dict:
    response = client.post(
        "/api/v1/owners",
        headers=_auth_headers(email),
        json={"full_name": "Shared Owner", "phone": "555-1000"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_two_users_in_same_tenant_share_patients_and_trace_creator(
    client,
    db_session,
    tenant,
    other_tenant,
    monkeypatch,
):
    import app.core.tenant as tenant_core

    creator = _create_user(db_session, tenant, "creator@example.com", "Creator Vet")
    colleague = _create_user(db_session, tenant, "colleague@example.com", "Colleague Vet")
    outsider = _create_user(db_session, other_tenant, "outsider@example.com", "Other Vet")

    monkeypatch.setattr(
        tenant_core,
        "verify_id_token",
        lambda token: {"email": token},
    )

    owner = _create_owner(client, creator.email)
    patient_response = client.post(
        "/api/v1/patients",
        headers=_auth_headers(creator.email),
        json={"owner_id": owner["id"], "name": "Luna", "species": "Canine"},
    )

    assert patient_response.status_code == 201
    patient = patient_response.json()["data"]
    assert patient["tenant_id"] == str(tenant.id)
    assert patient["created_by_user_id"] == str(creator.id)
    assert patient["created_by_user_name"] == "Creator Vet"
    assert patient["created_by_user_email"] == "creator@example.com"

    colleague_detail = client.get(
        f"/api/v1/patients/{patient['id']}",
        headers=_auth_headers(colleague.email),
    )
    colleague_list = client.get(
        "/api/v1/patients",
        headers=_auth_headers(colleague.email),
    )
    outsider_detail = client.get(
        f"/api/v1/patients/{patient['id']}",
        headers=_auth_headers(outsider.email),
    )

    assert colleague_detail.status_code == 200
    assert colleague_detail.json()["data"]["id"] == patient["id"]
    assert colleague_list.status_code == 200
    assert [item["id"] for item in colleague_list.json()["data"]] == [patient["id"]]
    assert outsider_detail.status_code == 404


def test_authenticated_consultation_and_exam_record_user_traceability(
    client,
    db_session,
    tenant,
    monkeypatch,
):
    import app.core.tenant as tenant_core

    vet = _create_user(db_session, tenant, "vet@example.com", "Tracing Vet")
    monkeypatch.setattr(
        tenant_core,
        "verify_id_token",
        lambda token: {"email": token},
    )

    owner = _create_owner(client, vet.email)
    patient_response = client.post(
        "/api/v1/patients",
        headers=_auth_headers(vet.email),
        json={"owner_id": owner["id"], "name": "Nina", "species": "Feline"},
    )
    assert patient_response.status_code == 201
    patient = patient_response.json()["data"]

    consultation_response = client.post(
        "/api/v1/consultations",
        headers=_auth_headers(vet.email),
        json={
            "patient_id": patient["id"],
            "visit_date": "2026-04-24T10:30:00Z",
            "reason": "Annual check",
        },
    )
    exam_response = client.post(
        "/api/v1/exams",
        headers=_auth_headers(vet.email),
        json={
            "patient_id": patient["id"],
            "exam_type": "Blood test",
            "requested_at": "2026-04-24T10:30:00Z",
        },
    )

    assert consultation_response.status_code == 201
    consultation = consultation_response.json()["data"]
    assert consultation["created_by_user_id"] == str(vet.id)
    assert consultation["created_by_user_name"] == "Tracing Vet"
    assert consultation["created_by_user_email"] == "vet@example.com"
    assert consultation["attending_user_id"] == str(vet.id)
    assert consultation["attending_user_name"] == "Tracing Vet"
    assert consultation["attending_user_email"] == "vet@example.com"

    assert exam_response.status_code == 201
    exam = exam_response.json()["data"]
    assert exam["requested_by_user_id"] == str(vet.id)
    assert exam["requested_by_user_name"] == "Tracing Vet"
    assert exam["requested_by_user_email"] == "vet@example.com"

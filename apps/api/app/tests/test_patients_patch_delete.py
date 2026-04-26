import uuid


def _create_owner(client, tenant, full_name="Owner"):
    response = client.post(
        "/api/v1/owners",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"full_name": full_name, "phone": "555-1000"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_patient(client, tenant, owner_id, name="Luna"):
    response = client.post(
        "/api/v1/patients",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"owner_id": owner_id, "name": name, "species": "Canine"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_patient_for_tenant(client, tenant, name="Luna"):
    owner = _create_owner(client, tenant, f"{name} Owner")
    return _create_patient(client, tenant, owner["id"], name)


def _create_consultation(client, tenant, patient_id):
    response = client.post(
        "/api/v1/consultations",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "patient_id": patient_id,
            "visit_date": "2026-04-24T10:30:00Z",
            "reason": "Control",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_exam(client, tenant, patient_id, consultation_id=None):
    payload = {
        "patient_id": patient_id,
        "exam_type": "Hemograma",
        "requested_at": "2026-04-24T10:30:00Z",
    }
    if consultation_id:
        payload["consultation_id"] = consultation_id

    response = client.post(
        "/api/v1/exams",
        headers={"X-Tenant-Id": str(tenant.id)},
        json=payload,
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_preventive_care(client, tenant, patient_id):
    response = client.post(
        f"/api/v1/patients/{patient_id}/preventive-care",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "name": "Rabia anual",
            "care_type": "vaccine",
            "applied_at": "2026-04-24T10:30:00Z",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_file_reference(client, tenant, patient_id):
    response = client.post(
        f"/api/v1/patients/{patient_id}/file-references",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"name": "Radiografía", "file_type": "radiography"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_update_patient_general_fields(client, tenant):
    owner = _create_owner(client, tenant, "Owner One")
    new_owner = _create_owner(client, tenant, "Owner Two")
    patient = _create_patient(client, tenant, owner["id"])

    response = client.patch(
        f"/api/v1/patients/{patient['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "owner_id": new_owner["id"],
            "name": "Nina",
            "species": "Feline",
            "breed": "Persa",
            "sex": "Hembra",
            "estimated_age": "3 años",
            "weight_kg": "4.25",
            "allergies": "Penicilina",
            "chronic_conditions": "Dermatitis",
        },
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["owner_id"] == new_owner["id"]
    assert body["name"] == "Nina"
    assert body["species"] == "Feline"
    assert body["breed"] == "Persa"
    assert body["sex"] == "Hembra"
    assert body["estimated_age"] == "3 años"
    assert body["weight_kg"] == "4.25"
    assert body["allergies"] == "Penicilina"
    assert body["chronic_conditions"] == "Dermatitis"
    assert body["tenant_id"] == str(tenant.id)


def test_prevent_changing_patient_owner_to_other_tenant(client, tenant, other_tenant):
    owner = _create_owner(client, tenant, "Owner One")
    foreign_owner = _create_owner(client, other_tenant, "Foreign Owner")
    patient = _create_patient(client, tenant, owner["id"])

    response = client.patch(
        f"/api/v1/patients/{patient['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"owner_id": foreign_owner["id"]},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_cross_tenant_access"


def test_delete_patient_without_associated_records(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)

    response = client.delete(
        f"/api/v1/patients/{patient['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 204

    get_response = client.get(
        f"/api/v1/patients/{patient['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert get_response.status_code == 404
    assert get_response.json()["error"]["code"] == "patient_not_found"


def test_delete_patient_with_all_associated_records(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    consultation = _create_consultation(client, tenant, patient["id"])
    exam = _create_exam(client, tenant, patient["id"], consultation["id"])
    preventive_care = _create_preventive_care(client, tenant, patient["id"])
    file_reference = _create_file_reference(client, tenant, patient["id"])

    response = client.delete(
        f"/api/v1/patients/{patient['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 204

    assert client.get(
        f"/api/v1/patients/{patient['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    ).status_code == 404
    assert client.get(
        f"/api/v1/consultations/{consultation['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    ).status_code == 404
    assert client.get(
        f"/api/v1/exams/{exam['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    ).status_code == 404
    assert client.get(
        f"/api/v1/preventive-care/{preventive_care['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    ).status_code == 404
    assert client.get(
        f"/api/v1/file-references/{file_reference['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    ).status_code == 404


def test_delete_patient_does_not_remove_other_tenant_records(
    client, tenant, other_tenant
):
    patient = _create_patient_for_tenant(client, tenant, "Luna")
    _create_consultation(client, tenant, patient["id"])
    _create_preventive_care(client, tenant, patient["id"])
    _create_file_reference(client, tenant, patient["id"])

    foreign_patient = _create_patient_for_tenant(client, other_tenant, "Mora")
    foreign_consultation = _create_consultation(
        client,
        other_tenant,
        foreign_patient["id"],
    )
    foreign_exam = _create_exam(
        client,
        other_tenant,
        foreign_patient["id"],
        foreign_consultation["id"],
    )
    foreign_preventive_care = _create_preventive_care(
        client,
        other_tenant,
        foreign_patient["id"],
    )
    foreign_file_reference = _create_file_reference(
        client,
        other_tenant,
        foreign_patient["id"],
    )

    response = client.delete(
        f"/api/v1/patients/{patient['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 204

    assert client.get(
        f"/api/v1/patients/{foreign_patient['id']}",
        headers={"X-Tenant-Id": str(other_tenant.id)},
    ).status_code == 200
    assert client.get(
        f"/api/v1/consultations/{foreign_consultation['id']}",
        headers={"X-Tenant-Id": str(other_tenant.id)},
    ).status_code == 200
    assert client.get(
        f"/api/v1/exams/{foreign_exam['id']}",
        headers={"X-Tenant-Id": str(other_tenant.id)},
    ).status_code == 200
    assert client.get(
        f"/api/v1/preventive-care/{foreign_preventive_care['id']}",
        headers={"X-Tenant-Id": str(other_tenant.id)},
    ).status_code == 200
    assert client.get(
        f"/api/v1/file-references/{foreign_file_reference['id']}",
        headers={"X-Tenant-Id": str(other_tenant.id)},
    ).status_code == 200


def test_unknown_patient_returns_not_found_for_patch_and_delete(client, tenant):
    unknown_patient_id = uuid.uuid4()

    patch_response = client.patch(
        f"/api/v1/patients/{unknown_patient_id}",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"name": "Nina"},
    )
    delete_response = client.delete(
        f"/api/v1/patients/{unknown_patient_id}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert patch_response.status_code == 404
    assert patch_response.json()["error"]["code"] == "patient_not_found"
    assert delete_response.status_code == 404
    assert delete_response.json()["error"]["code"] == "patient_not_found"

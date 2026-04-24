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


def _create_consultation(client, tenant, patient_id, **overrides):
    payload = {
        "patient_id": patient_id,
        "visit_date": "2026-04-24T10:30:00Z",
        "reason": "Skin irritation",
    }
    payload.update(overrides)
    response = client.post(
        "/api/v1/consultations",
        headers={"X-Tenant-Id": str(tenant.id)},
        json=payload,
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_exam(client, tenant, patient_id, **overrides):
    payload = {
        "patient_id": patient_id,
        "exam_type": "Blood test",
        "requested_at": "2026-04-24T10:30:00Z",
        "observations": "Check infection markers",
    }
    payload.update(overrides)
    response = client.post(
        "/api/v1/exams",
        headers={"X-Tenant-Id": str(tenant.id)},
        json=payload,
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_create_exam_for_patient(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)

    exam = _create_exam(client, tenant, patient["id"])

    assert exam["tenant_id"] == str(tenant.id)
    assert exam["patient_id"] == patient["id"]
    assert exam["consultation_id"] is None
    assert exam["status"] == "requested"
    assert exam["exam_type"] == "Blood test"

    response = client.get(
        f"/api/v1/exams/{exam['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 200
    assert response.json()["data"]["id"] == exam["id"]


def test_create_exam_linked_to_consultation(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    consultation = _create_consultation(client, tenant, patient["id"])

    exam = _create_exam(
        client,
        tenant,
        patient["id"],
        consultation_id=consultation["id"],
    )

    assert exam["consultation_id"] == consultation["id"]


def test_prevent_exam_for_patient_from_another_tenant(client, tenant, other_tenant):
    foreign_patient = _create_patient_for_tenant(client, other_tenant, "Foreign")

    response = client.post(
        "/api/v1/exams",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "patient_id": foreign_patient["id"],
            "exam_type": "Blood test",
            "requested_at": "2026-04-24T10:30:00Z",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_cross_tenant_access"


def test_prevent_linking_exam_to_consultation_from_another_patient(client, tenant):
    patient = _create_patient_for_tenant(client, tenant, "Luna")
    other_patient = _create_patient_for_tenant(client, tenant, "Nina")
    other_consultation = _create_consultation(client, tenant, other_patient["id"])

    response = client.post(
        "/api/v1/exams",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "patient_id": patient["id"],
            "consultation_id": other_consultation["id"],
            "exam_type": "Blood test",
            "requested_at": "2026-04-24T10:30:00Z",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "consultation_patient_mismatch"


def test_list_exams_by_patient(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    older = _create_exam(
        client,
        tenant,
        patient["id"],
        requested_at="2026-04-20T10:30:00Z",
        exam_type="Older blood test",
    )
    newer = _create_exam(
        client,
        tenant,
        patient["id"],
        requested_at="2026-04-24T10:30:00Z",
        exam_type="Newer blood test",
    )

    response = client.get(
        f"/api/v1/patients/{patient['id']}/exams",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 2
    assert [item["id"] for item in body["data"]] == [newer["id"], older["id"]]


def test_list_exams_by_consultation(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    consultation = _create_consultation(client, tenant, patient["id"])
    linked_exam = _create_exam(
        client,
        tenant,
        patient["id"],
        consultation_id=consultation["id"],
    )
    _create_exam(client, tenant, patient["id"], exam_type="Unlinked exam")

    response = client.get(
        f"/api/v1/consultations/{consultation['id']}/exams",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["id"] == linked_exam["id"]


def test_update_exam_with_result_fields(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    exam = _create_exam(client, tenant, patient["id"])

    response = client.patch(
        f"/api/v1/exams/{exam['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "status": "result_loaded",
            "performed_at": "2026-04-25T11:00:00Z",
            "result_summary": "Mild leukocytosis",
            "result_detail": "White blood cell count slightly elevated.",
            "observations": "Monitor clinical response",
        },
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "result_loaded"
    assert body["result_summary"] == "Mild leukocytosis"
    assert body["result_detail"] == "White blood cell count slightly elevated."


def test_reject_invalid_exam_status(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    exam = _create_exam(client, tenant, patient["id"])

    response = client.patch(
        f"/api/v1/exams/{exam['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"status": "archived"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_exam_status"


def test_clinical_history_includes_exam_timeline_item(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    consultation = _create_consultation(
        client,
        tenant,
        patient["id"],
        visit_date="2026-04-23T10:30:00Z",
    )
    exam = _create_exam(
        client,
        tenant,
        patient["id"],
        requested_at="2026-04-24T10:30:00Z",
    )

    response = client.get(
        f"/api/v1/patients/{patient['id']}/clinical-history",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["exams"][0]["id"] == exam["id"]
    assert body["timeline"][0] == {
        "type": "exam",
        "id": exam["id"],
        "date": "2026-04-24T10:30:00",
        "title": "Blood test",
        "summary": "Requested",
    }
    assert body["timeline"][1]["type"] == "consultation"
    assert body["timeline"][1]["id"] == consultation["id"]


def test_clinical_history_does_not_leak_cross_tenant_exams(
    client, tenant, other_tenant
):
    patient = _create_patient_for_tenant(client, tenant, "Luna")
    foreign_patient = _create_patient_for_tenant(client, other_tenant, "Nina")
    exam = _create_exam(client, tenant, patient["id"])
    foreign_exam = _create_exam(client, other_tenant, foreign_patient["id"])

    response = client.get(
        f"/api/v1/patients/{patient['id']}/clinical-history",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 200
    body = response.json()["data"]
    exam_ids = [item["id"] for item in body["exams"]]
    timeline_ids = [item["id"] for item in body["timeline"]]
    assert exam["id"] in exam_ids
    assert foreign_exam["id"] not in exam_ids
    assert exam["id"] in timeline_ids
    assert foreign_exam["id"] not in timeline_ids

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


def _create_consultation(client, tenant, patient_id, **overrides):
    payload = {
        "patient_id": patient_id,
        "visit_date": "2026-04-24T10:30:00Z",
        "reason": "Skin irritation",
        "anamnesis": "Owner reports itching for 3 days",
        "clinical_exam": "Mild redness",
        "presumptive_diagnosis": "Allergic dermatitis",
        "diagnostic_plan": "Skin scraping if symptoms persist",
        "therapeutic_plan": "Topical treatment",
        "final_diagnosis": None,
        "indications": "Return if symptoms worsen",
    }
    payload.update(overrides)
    response = client.post(
        "/api/v1/consultations",
        headers={"X-Tenant-Id": str(tenant.id)},
        json=payload,
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_create_and_get_consultation(client, tenant):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])

    consultation = _create_consultation(client, tenant, patient["id"])

    assert consultation["tenant_id"] == str(tenant.id)
    assert consultation["patient_id"] == patient["id"]
    assert consultation["reason"] == "Skin irritation"
    assert consultation["final_diagnosis"] is None

    response = client.get(
        f"/api/v1/consultations/{consultation['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 200
    assert response.json()["data"]["id"] == consultation["id"]


def test_prevent_consultation_creation_for_patient_in_another_tenant(
    client, tenant, other_tenant
):
    owner = _create_owner(client, other_tenant, "Foreign Owner")
    patient = _create_patient(client, other_tenant, owner["id"], "Nina")

    response = client.post(
        "/api/v1/consultations",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "patient_id": patient["id"],
            "visit_date": "2026-04-24T10:30:00Z",
            "reason": "Skin irritation",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_cross_tenant_access"


def test_list_patient_consultations_ordered_by_visit_date_desc(client, tenant):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])

    older = _create_consultation(
        client,
        tenant,
        patient["id"],
        visit_date="2026-04-20T10:30:00Z",
        reason="Older visit",
    )
    newer = _create_consultation(
        client,
        tenant,
        patient["id"],
        visit_date="2026-04-24T10:30:00Z",
        reason="Newer visit",
    )

    response = client.get(
        f"/api/v1/patients/{patient['id']}/consultations",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 2
    assert [item["id"] for item in body["data"]] == [newer["id"], older["id"]]


def test_patch_consultation_clinical_fields(client, tenant):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])
    consultation = _create_consultation(client, tenant, patient["id"])

    response = client.patch(
        f"/api/v1/consultations/{consultation['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "clinical_exam": "Redness improved",
            "final_diagnosis": "Contact dermatitis",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["clinical_exam"] == "Redness improved"
    assert body["data"]["final_diagnosis"] == "Contact dermatitis"
    assert body["data"]["anamnesis"] == "Owner reports itching for 3 days"


def test_clinical_history_returns_patient_and_consultations(client, tenant):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])
    consultation = _create_consultation(client, tenant, patient["id"])

    response = client.get(
        f"/api/v1/patients/{patient['id']}/clinical-history",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["patient"]["id"] == patient["id"]
    assert body["data"]["consultations"][0]["id"] == consultation["id"]

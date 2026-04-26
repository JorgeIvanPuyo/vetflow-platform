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


def _create_preventive_care(client, tenant, patient_id, **overrides):
    payload = {
        "name": "Rabia anual",
        "care_type": "vaccine",
        "applied_at": "2026-04-24T10:30:00Z",
        "next_due_at": "2027-04-24T10:30:00Z",
        "lot_number": "LOT-123",
        "notes": "Aplicada sin reacción",
    }
    payload.update(overrides)
    response = client.post(
        f"/api/v1/patients/{patient_id}/preventive-care",
        headers={"X-Tenant-Id": str(tenant.id)},
        json=payload,
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_file_reference(client, tenant, patient_id, **overrides):
    payload = {
        "name": "Radiografía lateral",
        "file_type": "radiography",
        "description": "Referencia externa del estudio",
        "external_url": "https://example.com/luna-rx",
    }
    payload.update(overrides)
    response = client.post(
        f"/api/v1/patients/{patient_id}/file-references",
        headers={"X-Tenant-Id": str(tenant.id)},
        json=payload,
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_create_preventive_care_for_patient(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)

    record = _create_preventive_care(client, tenant, patient["id"])

    assert record["tenant_id"] == str(tenant.id)
    assert record["patient_id"] == patient["id"]
    assert record["name"] == "Rabia anual"
    assert record["care_type"] == "vaccine"
    assert record["lot_number"] == "LOT-123"


def test_list_preventive_care_by_patient(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    older = _create_preventive_care(
        client,
        tenant,
        patient["id"],
        name="Desparasitación",
        care_type="deworming",
        applied_at="2026-04-20T10:30:00Z",
    )
    newer = _create_preventive_care(
        client,
        tenant,
        patient["id"],
        name="Vacuna múltiple",
        applied_at="2026-04-24T10:30:00Z",
    )

    response = client.get(
        f"/api/v1/patients/{patient['id']}/preventive-care",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 2
    assert [item["id"] for item in body["data"]] == [newer["id"], older["id"]]


def test_get_preventive_care_by_id(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    record = _create_preventive_care(client, tenant, patient["id"])

    response = client.get(
        f"/api/v1/preventive-care/{record['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 200
    assert response.json()["data"]["id"] == record["id"]


def test_update_preventive_care(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    record = _create_preventive_care(client, tenant, patient["id"])

    response = client.patch(
        f"/api/v1/preventive-care/{record['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"name": "Rabia actualizada", "care_type": "other"},
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["name"] == "Rabia actualizada"
    assert body["care_type"] == "other"


def test_delete_preventive_care(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    record = _create_preventive_care(client, tenant, patient["id"])

    response = client.delete(
        f"/api/v1/preventive-care/{record['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 204

    get_response = client.get(
        f"/api/v1/preventive-care/{record['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert get_response.status_code == 404
    assert get_response.json()["error"]["code"] == "preventive_care_not_found"


def test_prevent_cross_tenant_preventive_care_creation_and_access(
    client, tenant, other_tenant
):
    foreign_patient = _create_patient_for_tenant(client, other_tenant, "Nina")
    foreign_record = _create_preventive_care(
        client,
        other_tenant,
        foreign_patient["id"],
    )

    create_response = client.post(
        f"/api/v1/patients/{foreign_patient['id']}/preventive-care",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "name": "Rabia",
            "care_type": "vaccine",
            "applied_at": "2026-04-24T10:30:00Z",
        },
    )
    assert create_response.status_code == 409
    assert create_response.json()["error"]["code"] == "invalid_cross_tenant_access"

    get_response = client.get(
        f"/api/v1/preventive-care/{foreign_record['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert get_response.status_code == 404


def test_create_file_reference_for_patient(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)

    file_reference = _create_file_reference(client, tenant, patient["id"])

    assert file_reference["tenant_id"] == str(tenant.id)
    assert file_reference["patient_id"] == patient["id"]
    assert file_reference["name"] == "Radiografía lateral"
    assert file_reference["file_type"] == "radiography"


def test_list_file_references_by_patient(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    first = _create_file_reference(client, tenant, patient["id"], name="Archivo A")
    second = _create_file_reference(client, tenant, patient["id"], name="Archivo B")

    response = client.get(
        f"/api/v1/patients/{patient['id']}/file-references",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 2
    assert {item["id"] for item in body["data"]} == {first["id"], second["id"]}


def test_get_file_reference_by_id(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    file_reference = _create_file_reference(client, tenant, patient["id"])

    response = client.get(
        f"/api/v1/file-references/{file_reference['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 200
    assert response.json()["data"]["id"] == file_reference["id"]


def test_update_file_reference(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    file_reference = _create_file_reference(client, tenant, patient["id"])

    response = client.patch(
        f"/api/v1/file-references/{file_reference['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"name": "Laboratorio externo", "file_type": "lab_result"},
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["name"] == "Laboratorio externo"
    assert body["file_type"] == "lab_result"


def test_delete_file_reference(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    file_reference = _create_file_reference(client, tenant, patient["id"])

    response = client.delete(
        f"/api/v1/file-references/{file_reference['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 204

    get_response = client.get(
        f"/api/v1/file-references/{file_reference['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert get_response.status_code == 404
    assert get_response.json()["error"]["code"] == "file_reference_not_found"


def test_prevent_cross_tenant_file_reference_creation_and_access(
    client, tenant, other_tenant
):
    foreign_patient = _create_patient_for_tenant(client, other_tenant, "Nina")
    foreign_file_reference = _create_file_reference(
        client,
        other_tenant,
        foreign_patient["id"],
    )

    create_response = client.post(
        f"/api/v1/patients/{foreign_patient['id']}/file-references",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"name": "Archivo", "file_type": "pdf"},
    )
    assert create_response.status_code == 409
    assert create_response.json()["error"]["code"] == "invalid_cross_tenant_access"

    get_response = client.get(
        f"/api/v1/file-references/{foreign_file_reference['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert get_response.status_code == 404


def test_clinical_history_includes_preventive_care_timeline_item(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    record = _create_preventive_care(client, tenant, patient["id"])

    response = client.get(
        f"/api/v1/patients/{patient['id']}/clinical-history",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["preventive_care"][0]["id"] == record["id"]
    assert {
        "type": "preventive_care",
        "id": record["id"],
        "date": "2026-04-24T10:30:00",
        "title": "Rabia anual",
        "summary": "LOT-123",
    } in body["timeline"]


def test_clinical_history_includes_file_reference_timeline_item(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    file_reference = _create_file_reference(client, tenant, patient["id"])

    response = client.get(
        f"/api/v1/patients/{patient['id']}/clinical-history",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["file_references"][0]["id"] == file_reference["id"]
    assert any(
        item["type"] == "file_reference"
        and item["id"] == file_reference["id"]
        and item["title"] == "Radiografía lateral"
        and item["summary"] == "radiography"
        for item in body["timeline"]
    )


def test_clinical_history_does_not_leak_cross_tenant_detail_records(
    client, tenant, other_tenant
):
    patient = _create_patient_for_tenant(client, tenant, "Luna")
    foreign_patient = _create_patient_for_tenant(client, other_tenant, "Nina")
    record = _create_preventive_care(client, tenant, patient["id"])
    file_reference = _create_file_reference(client, tenant, patient["id"])
    foreign_record = _create_preventive_care(
        client,
        other_tenant,
        foreign_patient["id"],
    )
    foreign_file_reference = _create_file_reference(
        client,
        other_tenant,
        foreign_patient["id"],
    )

    response = client.get(
        f"/api/v1/patients/{patient['id']}/clinical-history",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 200
    body = response.json()["data"]
    timeline_ids = [item["id"] for item in body["timeline"]]
    assert record["id"] in timeline_ids
    assert file_reference["id"] in timeline_ids
    assert foreign_record["id"] not in timeline_ids
    assert foreign_file_reference["id"] not in timeline_ids

import uuid


def test_create_owner(client, tenant):
    response = client.post(
        "/api/v1/owners",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "full_name": "Maria Perez",
            "phone": "555-1000",
            "document_id": "8-123-456",
            "email": "maria@example.com",
            "address": "Main Street",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["data"]["full_name"] == "Maria Perez"
    assert body["data"]["tenant_id"] == str(tenant.id)


def test_list_owners_filtered_by_tenant(client, tenant, other_tenant):
    client.post(
        "/api/v1/owners",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"full_name": "Owner One", "phone": "111"},
    )
    client.post(
        "/api/v1/owners",
        headers={"X-Tenant-Id": str(other_tenant.id)},
        json={"full_name": "Owner Two", "phone": "222"},
    )

    response = client.get(
        "/api/v1/owners",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    assert len(body["data"]) == 1
    assert body["data"][0]["full_name"] == "Owner One"


def test_list_owners_supports_tenant_safe_search_and_pagination(
    client, tenant, other_tenant
):
    headers = {"X-Tenant-Id": str(tenant.id)}
    for index in range(3):
        client.post(
            "/api/v1/owners",
            headers=headers,
            json={"full_name": f"Familia Vetflow {index}", "phone": f"100{index}"},
        )
    client.post(
        "/api/v1/owners",
        headers={"X-Tenant-Id": str(other_tenant.id)},
        json={"full_name": "Familia Vetflow Externa", "phone": "999"},
    )

    response = client.get(
        "/api/v1/owners",
        params={"search": "Vetflow", "page": 2, "page_size": 2},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"] == {"page": 2, "page_size": 2, "total": 3}
    assert len(body["data"]) == 1
    assert all(owner["tenant_id"] == str(tenant.id) for owner in body["data"])


def test_list_patients_supports_tenant_safe_search_and_pagination(
    client, tenant, other_tenant
):
    headers = {"X-Tenant-Id": str(tenant.id)}
    owner = client.post(
        "/api/v1/owners",
        headers=headers,
        json={"full_name": "Paciente Owner", "phone": "555"},
    ).json()["data"]
    for index in range(3):
        client.post(
            "/api/v1/patients",
            headers=headers,
            json={
                "owner_id": owner["id"],
                "name": f"Mascota Vetflow {index}",
                "species": "Canine",
            },
        )

    other_headers = {"X-Tenant-Id": str(other_tenant.id)}
    other_owner = client.post(
        "/api/v1/owners",
        headers=other_headers,
        json={"full_name": "Other Owner", "phone": "777"},
    ).json()["data"]
    client.post(
        "/api/v1/patients",
        headers=other_headers,
        json={
            "owner_id": other_owner["id"],
            "name": "Mascota Vetflow Externa",
            "species": "Feline",
        },
    )

    response = client.get(
        "/api/v1/patients",
        params={"search": "Vetflow", "page": 2, "page_size": 2},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"] == {"page": 2, "page_size": 2, "total": 3}
    assert len(body["data"]) == 1
    assert all(patient["tenant_id"] == str(tenant.id) for patient in body["data"])


def test_owner_and_patient_lists_remain_unpaginated_without_page_size(client, tenant):
    headers = {"X-Tenant-Id": str(tenant.id)}
    for index in range(3):
        owner = client.post(
            "/api/v1/owners",
            headers=headers,
            json={"full_name": f"Owner {index}", "phone": f"200{index}"},
        ).json()["data"]
        client.post(
            "/api/v1/patients",
            headers=headers,
            json={
                "owner_id": owner["id"],
                "name": f"Patient {index}",
                "species": "Canine",
            },
        )

    owners_response = client.get("/api/v1/owners", headers=headers)
    patients_response = client.get("/api/v1/patients", headers=headers)

    assert owners_response.status_code == 200
    assert owners_response.json()["meta"] == {"page": 1, "page_size": 3, "total": 3}
    assert len(owners_response.json()["data"]) == 3
    assert patients_response.status_code == 200
    assert patients_response.json()["meta"] == {"page": 1, "page_size": 3, "total": 3}
    assert len(patients_response.json()["data"]) == 3


def test_create_patient_under_owner(client, tenant):
    owner_response = client.post(
        "/api/v1/owners",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"full_name": "Owner Patient", "phone": "333"},
    )
    owner_id = owner_response.json()["data"]["id"]

    response = client.post(
        "/api/v1/patients",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "owner_id": owner_id,
            "name": "Luna",
            "species": "Canine",
            "breed": "Mixed",
            "estimated_age": "2 years",
            "allergies": "Chicken",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["data"]["name"] == "Luna"
    assert body["data"]["owner_id"] == owner_id
    assert body["data"]["tenant_id"] == str(tenant.id)
    assert body["data"]["estimated_age"] == "2 years"


def test_prevent_patient_creation_if_owner_belongs_to_another_tenant(
    client, tenant, other_tenant
):
    owner_response = client.post(
        "/api/v1/owners",
        headers={"X-Tenant-Id": str(other_tenant.id)},
        json={"full_name": "Foreign Owner", "phone": "444"},
    )
    foreign_owner_id = owner_response.json()["data"]["id"]

    response = client.post(
        "/api/v1/patients",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "owner_id": foreign_owner_id,
            "name": "Toby",
            "species": "Feline",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_cross_tenant_access"


def test_delete_owner_without_patients(client, tenant):
    owner_response = client.post(
        "/api/v1/owners",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"full_name": "Owner Without Pets", "phone": "555"},
    )
    owner_id = owner_response.json()["data"]["id"]

    response = client.delete(
        f"/api/v1/owners/{owner_id}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 204

    get_response = client.get(
        f"/api/v1/owners/{owner_id}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert get_response.status_code == 404
    assert get_response.json()["error"]["code"] == "owner_not_found"


def test_delete_owner_with_patients_deletes_associated_patients(client, tenant):
    owner_response = client.post(
        "/api/v1/owners",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"full_name": "Cascade Owner", "phone": "555"},
    )
    owner_id = owner_response.json()["data"]["id"]

    patient_response = client.post(
        "/api/v1/patients",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"owner_id": owner_id, "name": "Nina", "species": "Canine"},
    )
    patient_id = patient_response.json()["data"]["id"]

    consultation_response = client.post(
        "/api/v1/consultations",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "patient_id": patient_id,
            "visit_date": "2026-04-24T10:30:00Z",
            "reason": "Control",
        },
    )
    consultation_id = consultation_response.json()["data"]["id"]

    client.post(
        "/api/v1/exams",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "patient_id": patient_id,
            "consultation_id": consultation_id,
            "exam_type": "Hemograma",
            "requested_at": "2026-04-24T10:30:00Z",
        },
    )

    response = client.delete(
        f"/api/v1/owners/{owner_id}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 204

    owner_lookup = client.get(
        f"/api/v1/owners/{owner_id}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert owner_lookup.status_code == 404

    patient_lookup = client.get(
        f"/api/v1/patients/{patient_id}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert patient_lookup.status_code == 404

    owner_patients = client.get(
        f"/api/v1/patients?owner_id={owner_id}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert owner_patients.status_code == 200
    assert owner_patients.json()["meta"]["total"] == 0


def test_delete_owner_does_not_remove_other_tenant_patients(
    client, tenant, other_tenant
):
    owner_response = client.post(
        "/api/v1/owners",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"full_name": "Tenant Owner", "phone": "555"},
    )
    owner_id = owner_response.json()["data"]["id"]
    client.post(
        "/api/v1/patients",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"owner_id": owner_id, "name": "Nina", "species": "Canine"},
    )

    other_owner_response = client.post(
        "/api/v1/owners",
        headers={"X-Tenant-Id": str(other_tenant.id)},
        json={"full_name": "Other Tenant Owner", "phone": "777"},
    )
    other_owner_id = other_owner_response.json()["data"]["id"]
    other_patient_response = client.post(
        "/api/v1/patients",
        headers={"X-Tenant-Id": str(other_tenant.id)},
        json={"owner_id": other_owner_id, "name": "Mora", "species": "Feline"},
    )
    other_patient_id = other_patient_response.json()["data"]["id"]

    response = client.delete(
        f"/api/v1/owners/{owner_id}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 204

    other_patient_lookup = client.get(
        f"/api/v1/patients/{other_patient_id}",
        headers={"X-Tenant-Id": str(other_tenant.id)},
    )
    assert other_patient_lookup.status_code == 200
    assert other_patient_lookup.json()["data"]["id"] == other_patient_id


def test_delete_unknown_owner_returns_not_found(client, tenant):
    unknown_owner_id = uuid.uuid4()

    response = client.delete(
        f"/api/v1/owners/{unknown_owner_id}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "owner_not_found"

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


def test_prevent_owner_deletion_when_patients_exist(client, tenant):
    owner_response = client.post(
        "/api/v1/owners",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"full_name": "Protected Owner", "phone": "555"},
    )
    owner_id = owner_response.json()["data"]["id"]

    client.post(
        "/api/v1/patients",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"owner_id": owner_id, "name": "Nina", "species": "Canine"},
    )

    response = client.delete(
        f"/api/v1/owners/{owner_id}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "owner_has_patients"

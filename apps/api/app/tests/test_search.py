def test_search_returns_owners_by_full_name(client, tenant):
    client.post(
        "/api/v1/owners",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"full_name": "Jane Doe", "phone": "111"},
    )

    response = client.get(
        "/api/v1/search",
        headers={"X-Tenant-Id": str(tenant.id)},
        params={"q": "jane"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["query"] == "jane"
    assert body["data"][0]["type"] == "owner"
    assert body["data"][0]["title"] == "Jane Doe"


def test_search_returns_owners_by_phone(client, tenant):
    client.post(
        "/api/v1/owners",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"full_name": "Phone Match", "phone": "507-555-0001"},
    )

    response = client.get(
        "/api/v1/search",
        headers={"X-Tenant-Id": str(tenant.id)},
        params={"q": "0001"},
    )

    assert response.status_code == 200
    body = response.json()
    assert any(item["title"] == "Phone Match" for item in body["data"])


def test_search_returns_patients_by_name(client, tenant):
    owner_response = client.post(
        "/api/v1/owners",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"full_name": "Milo Owner", "phone": "333"},
    )
    owner_id = owner_response.json()["data"]["id"]

    client.post(
        "/api/v1/patients",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"owner_id": owner_id, "name": "Milo", "species": "Canine"},
    )

    response = client.get(
        "/api/v1/search",
        headers={"X-Tenant-Id": str(tenant.id)},
        params={"q": "mil"},
    )

    assert response.status_code == 200
    body = response.json()
    patient_items = [item for item in body["data"] if item["type"] == "patient"]
    assert len(patient_items) == 1
    assert patient_items[0]["title"] == "Milo"
    assert patient_items[0]["owner_id"] == owner_id


def test_search_does_not_leak_results_across_tenants(client, tenant, other_tenant):
    other_owner_response = client.post(
        "/api/v1/owners",
        headers={"X-Tenant-Id": str(other_tenant.id)},
        json={"full_name": "Hidden Owner", "phone": "999"},
    )
    other_owner_id = other_owner_response.json()["data"]["id"]

    client.post(
        "/api/v1/patients",
        headers={"X-Tenant-Id": str(other_tenant.id)},
        json={"owner_id": other_owner_id, "name": "Hidden Patient", "species": "Feline"},
    )

    response = client.get(
        "/api/v1/search",
        headers={"X-Tenant-Id": str(tenant.id)},
        params={"q": "hidden"},
    )

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_search_blank_query_returns_400(client, tenant):
    response = client.get(
        "/api/v1/search",
        headers={"X-Tenant-Id": str(tenant.id)},
        params={"q": "   "},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "empty_search_query"

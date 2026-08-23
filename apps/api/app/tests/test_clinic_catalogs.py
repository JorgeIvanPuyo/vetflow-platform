import uuid

from app.models.user import User


def _headers(tenant) -> dict[str, str]:
    return {"X-Tenant-Id": str(tenant.id)}


def _user_headers(email: str) -> dict[str, str]:
    return {"X-User-Email": email}


def _create_user(db_session, tenant, email: str, full_name: str, role: str) -> User:
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=email,
        full_name=full_name,
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _item_payload(**overrides) -> dict:
    payload = {
        "name": "Rosas",
        "description": None,
        "sort_order": 10,
    }
    payload.update(overrides)
    return payload


def _create_item(client, admin, catalog_type: str = "mucous_membrane", **overrides) -> dict:
    response = client.post(
        f"/api/v1/clinic/catalogs/{catalog_type}",
        headers=_user_headers(admin.email),
        json=_item_payload(**overrides),
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_clinic_admin_can_create_and_list_catalog_items(client, db_session, tenant):
    admin = _create_user(db_session, tenant, "cat-admin@example.com", "Clinic Admin", "clinic_admin")

    created = _create_item(client, admin, name="Rosas pálidas")
    response = client.get(
        "/api/v1/clinic/catalogs/mucous_membrane",
        headers=_headers(tenant),
    )

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == created["id"]
    assert response.json()["data"][0]["tenant_id"] == str(tenant.id)
    assert response.json()["data"][0]["catalog_type"] == "mucous_membrane"
    assert response.json()["data"][0]["normalized_name"] == "rosas palidas"
    assert response.json()["data"][0]["created_by_user_id"] == str(admin.id)


def test_non_clinic_admin_cannot_mutate_catalog_items(client, db_session, tenant):
    vet = _create_user(
        db_session,
        tenant,
        "cat-vet@example.com",
        "Regular Vet",
        "medico_veterinario",
    )

    response = client.post(
        "/api/v1/clinic/catalogs/mucous_membrane",
        headers=_user_headers(vet.email),
        json=_item_payload(),
    )
    read_response = client.get(
        "/api/v1/clinic/catalogs/mucous_membrane",
        headers=_headers(tenant),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert read_response.status_code == 200


def test_invalid_catalog_type_is_rejected(client, db_session, tenant):
    admin = _create_user(db_session, tenant, "cat-admin2@example.com", "Clinic Admin", "clinic_admin")

    list_response = client.get(
        "/api/v1/clinic/catalogs/unknown_type",
        headers=_headers(tenant),
    )
    create_response = client.post(
        "/api/v1/clinic/catalogs/unknown_type",
        headers=_user_headers(admin.email),
        json=_item_payload(),
    )

    assert list_response.status_code == 422
    assert list_response.json()["error"]["code"] == "invalid_catalog_type"
    assert create_response.status_code == 422
    assert create_response.json()["error"]["code"] == "invalid_catalog_type"


def test_duplicate_active_item_name_is_normalized_per_tenant_and_type(
    client,
    db_session,
    tenant,
    other_tenant,
):
    admin = _create_user(db_session, tenant, "cat-admin3@example.com", "Clinic Admin", "clinic_admin")
    other_admin = _create_user(
        db_session,
        other_tenant,
        "cat-other-admin@example.com",
        "Other Admin",
        "clinic_admin",
    )
    _create_item(client, admin, name="Rosas   Pálidas")

    duplicate = client.post(
        "/api/v1/clinic/catalogs/mucous_membrane",
        headers=_user_headers(admin.email),
        json=_item_payload(name=" rosas palidas "),
    )
    same_name_other_type = client.post(
        "/api/v1/clinic/catalogs/hydration",
        headers=_user_headers(admin.email),
        json=_item_payload(name="rosas palidas"),
    )
    same_name_other_tenant = client.post(
        "/api/v1/clinic/catalogs/mucous_membrane",
        headers=_user_headers(other_admin.email),
        json=_item_payload(name="rosas palidas"),
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "catalog_item_duplicate_name"
    assert same_name_other_type.status_code == 201
    assert same_name_other_tenant.status_code == 201


def test_deactivate_activate_and_include_inactive(client, db_session, tenant):
    admin = _create_user(db_session, tenant, "cat-admin4@example.com", "Clinic Admin", "clinic_admin")
    item = _create_item(client, admin)

    deactivate = client.post(
        f"/api/v1/clinic/catalogs/mucous_membrane/{item['id']}/deactivate",
        headers=_user_headers(admin.email),
    )
    active_list = client.get(
        "/api/v1/clinic/catalogs/mucous_membrane",
        headers=_headers(tenant),
    )
    inactive_list = client.get(
        "/api/v1/clinic/catalogs/mucous_membrane",
        headers=_headers(tenant),
        params={"include_inactive": True},
    )
    activate = client.post(
        f"/api/v1/clinic/catalogs/mucous_membrane/{item['id']}/activate",
        headers=_user_headers(admin.email),
    )

    assert deactivate.status_code == 200
    assert deactivate.json()["data"]["is_active"] is False
    assert active_list.json()["data"] == []
    assert inactive_list.json()["data"][0]["id"] == item["id"]
    assert activate.status_code == 200
    assert activate.json()["data"]["is_active"] is True


def test_reactivate_blocked_when_active_duplicate_exists(client, db_session, tenant):
    admin = _create_user(db_session, tenant, "cat-admin5@example.com", "Clinic Admin", "clinic_admin")
    original = _create_item(client, admin, name="Congestionadas")

    deactivate = client.post(
        f"/api/v1/clinic/catalogs/mucous_membrane/{original['id']}/deactivate",
        headers=_user_headers(admin.email),
    )
    replacement = _create_item(client, admin, name="congestionadas")
    reactivate = client.post(
        f"/api/v1/clinic/catalogs/mucous_membrane/{original['id']}/activate",
        headers=_user_headers(admin.email),
    )

    assert deactivate.status_code == 200
    assert replacement["normalized_name"] == "congestionadas"
    assert reactivate.status_code == 409
    assert reactivate.json()["error"]["code"] == "catalog_item_duplicate_name"


def test_update_item_renames_and_renormalizes(client, db_session, tenant):
    admin = _create_user(db_session, tenant, "cat-admin6@example.com", "Clinic Admin", "clinic_admin")
    item = _create_item(client, admin, name="Cianóticas")

    response = client.patch(
        f"/api/v1/clinic/catalogs/mucous_membrane/{item['id']}",
        headers=_user_headers(admin.email),
        json={"name": "  Ictéricas  "},
    )

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Ictéricas"
    assert response.json()["data"]["normalized_name"] == "ictericas"


def test_reorder_items_is_tenant_and_type_scoped(client, db_session, tenant, other_tenant):
    admin = _create_user(db_session, tenant, "cat-admin7@example.com", "Clinic Admin", "clinic_admin")
    other_admin = _create_user(
        db_session,
        other_tenant,
        "cat-admin8@example.com",
        "Other Admin",
        "clinic_admin",
    )
    first = _create_item(client, admin, name="A", sort_order=10)
    second = _create_item(client, admin, name="B", sort_order=20)
    foreign = _create_item(client, other_admin, name="F")
    other_type = _create_item(client, admin, catalog_type="hydration", name="Normal")

    response = client.patch(
        "/api/v1/clinic/catalogs/mucous_membrane/reorder",
        headers=_user_headers(admin.email),
        json={
            "items": [
                {"id": second["id"], "sort_order": 1},
                {"id": first["id"], "sort_order": 2},
            ]
        },
    )
    cross_tenant = client.patch(
        "/api/v1/clinic/catalogs/mucous_membrane/reorder",
        headers=_user_headers(admin.email),
        json={"items": [{"id": foreign["id"], "sort_order": 1}]},
    )
    cross_type = client.patch(
        "/api/v1/clinic/catalogs/mucous_membrane/reorder",
        headers=_user_headers(admin.email),
        json={"items": [{"id": other_type["id"], "sort_order": 1}]},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"][:2]] == [second["id"], first["id"]]
    assert cross_tenant.status_code == 404
    assert cross_type.status_code == 404


def test_configuration_includes_grouped_active_catalogs(client, db_session, tenant):
    admin = _create_user(db_session, tenant, "cat-admin9@example.com", "Clinic Admin", "clinic_admin")
    mucous = _create_item(client, admin, name="Rosas")
    hydration = _create_item(client, admin, catalog_type="hydration", name="Normal")
    inactive = _create_item(client, admin, name="Pálidas")
    client.post(
        f"/api/v1/clinic/catalogs/mucous_membrane/{inactive['id']}/deactivate",
        headers=_user_headers(admin.email),
    )

    catalogs_only = client.get(
        "/api/v1/clinic/configuration",
        headers=_headers(tenant),
        params={"include": "catalogs"},
    )
    combined = client.get(
        "/api/v1/clinic/configuration",
        headers=_headers(tenant),
        params={"include": "preferences,services,catalogs"},
    )

    assert catalogs_only.status_code == 200
    catalogs = catalogs_only.json()["data"]["catalogs"]
    assert [item["id"] for item in catalogs["mucous_membrane"]] == [mucous["id"]]
    assert [item["id"] for item in catalogs["hydration"]] == [hydration["id"]]
    assert catalogs_only.json()["data"]["preferences"] is None
    assert catalogs_only.json()["data"]["services"] is None
    assert combined.status_code == 200
    assert combined.json()["data"]["preferences"] is not None
    assert combined.json()["data"]["services"] is not None
    assert combined.json()["data"]["catalogs"] is not None

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


def _service_payload(**overrides) -> dict:
    payload = {
        "code": "CONSULTA",
        "name": "Consulta general",
        "description": "Atencion clinica general",
        "kind": "consultation",
        "default_duration_minutes": 30,
        "calendar_color": "#2563eb",
        "is_bookable": True,
        "sort_order": 10,
    }
    payload.update(overrides)
    return payload


def _create_service(client, tenant, admin, **overrides) -> dict:
    response = client.post(
        "/api/v1/services",
        headers=_user_headers(admin.email),
        json=_service_payload(**overrides),
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_clinic_admin_can_create_and_list_services(client, db_session, tenant):
    admin = _create_user(db_session, tenant, "admin@example.com", "Clinic Admin", "clinic_admin")

    created = _create_service(client, tenant, admin)
    response = client.get("/api/v1/services", headers=_headers(tenant))

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == created["id"]
    assert response.json()["data"][0]["tenant_id"] == str(tenant.id)
    assert response.json()["data"][0]["normalized_name"] == "consulta general"
    assert response.json()["data"][0]["created_by_user_id"] == str(admin.id)


def test_non_clinic_admin_cannot_mutate_services(client, db_session, tenant):
    vet = _create_user(
        db_session,
        tenant,
        "vet@example.com",
        "Regular Vet",
        "medico_veterinario",
    )

    response = client.post(
        "/api/v1/services",
        headers=_user_headers(vet.email),
        json=_service_payload(),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_duplicate_active_service_name_is_normalized_per_tenant(
    client,
    db_session,
    tenant,
    other_tenant,
):
    admin = _create_user(db_session, tenant, "admin2@example.com", "Clinic Admin", "clinic_admin")
    other_admin = _create_user(
        db_session,
        other_tenant,
        "other-admin@example.com",
        "Other Admin",
        "clinic_admin",
    )
    _create_service(client, tenant, admin, name="Consulta   Médica")

    duplicate = client.post(
        "/api/v1/services",
        headers=_user_headers(admin.email),
        json=_service_payload(code="CONSULTA2", name=" consulta medica "),
    )
    other_tenant_response = client.post(
        "/api/v1/services",
        headers=_user_headers(other_admin.email),
        json=_service_payload(code="CONSULTA2", name="consulta medica"),
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "service_duplicate_name"
    assert other_tenant_response.status_code == 201


def test_deactivate_activate_and_include_inactive(client, db_session, tenant):
    admin = _create_user(db_session, tenant, "admin3@example.com", "Clinic Admin", "clinic_admin")
    service = _create_service(client, tenant, admin)

    deactivate = client.post(
        f"/api/v1/services/{service['id']}/deactivate",
        headers=_user_headers(admin.email),
    )
    active_list = client.get("/api/v1/services", headers=_headers(tenant))
    inactive_list = client.get(
        "/api/v1/services",
        headers=_headers(tenant),
        params={"include_inactive": True},
    )
    activate = client.post(
        f"/api/v1/services/{service['id']}/activate",
        headers=_user_headers(admin.email),
    )

    assert deactivate.status_code == 200
    assert deactivate.json()["data"]["is_active"] is False
    assert active_list.json()["data"] == []
    assert inactive_list.json()["data"][0]["id"] == service["id"]
    assert activate.status_code == 200
    assert activate.json()["data"]["is_active"] is True


def test_reorder_services_is_tenant_scoped(client, db_session, tenant, other_tenant):
    admin = _create_user(db_session, tenant, "admin4@example.com", "Clinic Admin", "clinic_admin")
    other_admin = _create_user(
        db_session,
        other_tenant,
        "admin5@example.com",
        "Other Admin",
        "clinic_admin",
    )
    first = _create_service(client, tenant, admin, code="A", name="A", sort_order=10)
    second = _create_service(client, tenant, admin, code="B", name="B", sort_order=20)
    foreign = _create_service(client, other_tenant, other_admin, code="F", name="F")

    response = client.patch(
        "/api/v1/services/reorder",
        headers=_user_headers(admin.email),
        json={
            "items": [
                {"id": second["id"], "sort_order": 1},
                {"id": first["id"], "sort_order": 2},
            ]
        },
    )
    cross_tenant = client.patch(
        "/api/v1/services/reorder",
        headers=_user_headers(admin.email),
        json={"items": [{"id": foreign["id"], "sort_order": 1}]},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"][:2]] == [second["id"], first["id"]]
    assert cross_tenant.status_code == 404


def test_restore_defaults_creates_missing_and_reactivates_without_overwriting(
    client, db_session, tenant
):
    admin = _create_user(db_session, tenant, "restore-admin1@example.com", "Clinic Admin", "clinic_admin")

    seeded = client.post(
        "/api/v1/services/restore-defaults",
        headers=_user_headers(admin.email),
    ).json()["data"]
    assert {service["code"] for service in seeded} == {
        "CONSULTA",
        "SEGUIMIENTO",
        "VACUNA",
        "DESPARASITACION",
        "EXAMEN",
    }

    consulta = next(service for service in seeded if service["code"] == "CONSULTA")
    client.patch(
        f"/api/v1/services/{consulta['id']}",
        headers=_user_headers(admin.email),
        json={"default_duration_minutes": 45},
    )
    seguimiento = next(service for service in seeded if service["code"] == "SEGUIMIENTO")
    client.post(
        f"/api/v1/services/{seguimiento['id']}/deactivate",
        headers=_user_headers(admin.email),
    )

    response = client.post(
        "/api/v1/services/restore-defaults",
        headers=_user_headers(admin.email),
    )

    assert response.status_code == 200
    services = response.json()["data"]
    assert len(services) == 5
    restored_consulta = next(service for service in services if service["id"] == consulta["id"])
    assert restored_consulta["default_duration_minutes"] == 45
    restored_seguimiento = next(
        service for service in services if service["id"] == seguimiento["id"]
    )
    assert restored_seguimiento["is_active"] is True


def test_bookable_only_filters_services(client, db_session, tenant):
    admin = _create_user(db_session, tenant, "admin6@example.com", "Clinic Admin", "clinic_admin")
    bookable = _create_service(client, tenant, admin, code="BOOK", name="Bookable")
    _create_service(
        client,
        tenant,
        admin,
        code="NOBK",
        name="No bookable",
        is_bookable=False,
    )

    response = client.get(
        "/api/v1/services",
        headers=_headers(tenant),
        params={"bookable_only": True},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == [bookable["id"]]

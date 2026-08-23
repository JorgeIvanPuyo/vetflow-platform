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


def test_get_preferences_creates_default_for_tenant(client, tenant):
    response = client.get("/api/v1/clinic/preferences", headers=_headers(tenant))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["tenant_id"] == str(tenant.id)
    assert data["currency_code"] == "USD"
    assert data["locale"] == "es-PA"
    assert data["default_appointment_duration_minutes"] == 30
    assert data["appointment_duration_options"] == [15, 30, 45, 60]
    assert data["default_purchase_tax_rate"] == "0.00"
    assert data["default_sale_tax_rate"] == "0.00"
    assert data["default_profit_margin"] == "35.00"
    assert data["money_rounding_increment"] == "10.00"


def test_clinic_admin_can_patch_money_preferences(client, db_session, tenant):
    admin = _create_user(
        db_session, tenant, "money-admin@example.com", "Clinic Admin", "clinic_admin"
    )

    response = client.patch(
        "/api/v1/clinic/preferences",
        headers=_user_headers(admin.email),
        json={
            "default_purchase_tax_rate": 21,
            "default_sale_tax_rate": 21,
            "default_profit_margin": 50,
            "money_rounding_increment": 5,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["default_purchase_tax_rate"] == "21.00"
    assert data["default_sale_tax_rate"] == "21.00"
    assert data["default_profit_margin"] == "50.00"
    assert data["money_rounding_increment"] == "5.00"


def test_patch_money_preferences_validates_bounds(client, db_session, tenant):
    admin = _create_user(
        db_session, tenant, "money-admin2@example.com", "Clinic Admin", "clinic_admin"
    )

    invalid_tax_rate = client.patch(
        "/api/v1/clinic/preferences",
        headers=_user_headers(admin.email),
        json={"default_sale_tax_rate": 150},
    )
    negative_margin = client.patch(
        "/api/v1/clinic/preferences",
        headers=_user_headers(admin.email),
        json={"default_profit_margin": -5},
    )
    zero_rounding = client.patch(
        "/api/v1/clinic/preferences",
        headers=_user_headers(admin.email),
        json={"money_rounding_increment": 0},
    )

    assert invalid_tax_rate.status_code == 422
    assert negative_margin.status_code == 422
    assert zero_rounding.status_code == 422


def test_clinic_admin_can_patch_preferences(client, db_session, tenant):
    admin = _create_user(db_session, tenant, "admin@example.com", "Clinic Admin", "clinic_admin")

    response = client.patch(
        "/api/v1/clinic/preferences",
        headers=_user_headers(admin.email),
        json={
            "currency_code": "ARS",
            "locale": "es-AR",
            "default_appointment_duration_minutes": 45,
            "appointment_duration_options": [15, 30, 45, 60, 90],
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["currency_code"] == "ARS"
    assert data["locale"] == "es-AR"
    assert data["default_appointment_duration_minutes"] == 45
    assert data["appointment_duration_options"] == [15, 30, 45, 60, 90]


def test_non_clinic_admin_cannot_patch_preferences(client, db_session, tenant):
    vet = _create_user(
        db_session,
        tenant,
        "vet@example.com",
        "Regular Vet",
        "medico_veterinario",
    )

    response = client.patch(
        "/api/v1/clinic/preferences",
        headers=_user_headers(vet.email),
        json={"default_appointment_duration_minutes": 45},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_preferences_validate_regional_pair(client, db_session, tenant):
    admin = _create_user(db_session, tenant, "admin2@example.com", "Clinic Admin", "clinic_admin")

    response = client.patch(
        "/api/v1/clinic/preferences",
        headers=_user_headers(admin.email),
        json={"currency_code": "USD", "locale": "es-AR"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_regional_preferences"


def test_preferences_validate_duration_options(client, db_session, tenant):
    admin = _create_user(db_session, tenant, "admin3@example.com", "Clinic Admin", "clinic_admin")

    response = client.patch(
        "/api/v1/clinic/preferences",
        headers=_user_headers(admin.email),
        json={
            "default_appointment_duration_minutes": 45,
            "appointment_duration_options": [15, 30, 60],
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_default_appointment_duration"


def test_configuration_include_preferences_and_services(client, db_session, tenant):
    admin = _create_user(db_session, tenant, "admin4@example.com", "Clinic Admin", "clinic_admin")
    service_response = client.post(
        "/api/v1/services",
        headers=_user_headers(admin.email),
        json={
            "code": "CONSULTA",
            "name": "Consulta",
            "kind": "consultation",
            "default_duration_minutes": 30,
        },
    )
    assert service_response.status_code == 201

    response = client.get(
        "/api/v1/clinic/configuration",
        headers=_headers(tenant),
        params={"include": "preferences,services"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["preferences"]["tenant_id"] == str(tenant.id)
    assert [service["id"] for service in data["services"]] == [
        service_response.json()["data"]["id"]
    ]

import uuid

from app.models.user import User


def _headers(tenant) -> dict[str, str]:
    return {"X-Tenant-Id": str(tenant.id)}


def _user_headers(email: str) -> dict[str, str]:
    return {"X-User-Email": email}


def _create_admin(db_session, tenant, email: str, full_name: str = "Clinic Admin") -> User:
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=email,
        full_name=full_name,
        role="clinic_admin",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_catalog_item(client, admin, catalog_type: str, **overrides) -> dict:
    payload = {"name": "Item", "sort_order": 10}
    payload.update(overrides)
    response = client.post(
        f"/api/v1/clinic/catalogs/{catalog_type}",
        headers=_user_headers(admin.email),
        json=payload,
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_owner(client, tenant, full_name="Owner") -> dict:
    response = client.post(
        "/api/v1/owners",
        headers=_headers(tenant),
        json={"full_name": full_name, "phone": "555-1000"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_patient(client, tenant, name="Luna") -> dict:
    owner = _create_owner(client, tenant, f"{name} Owner")
    response = client.post(
        "/api/v1/patients",
        headers=_headers(tenant),
        json={"owner_id": owner["id"], "name": name, "species": "Canine"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_consultation(client, tenant, patient_id, **overrides) -> dict:
    payload = {
        "patient_id": patient_id,
        "visit_date": "2026-04-24T10:30:00Z",
        "reason": "Skin irritation",
    }
    payload.update(overrides)
    response = client.post(
        "/api/v1/consultations",
        headers=_headers(tenant),
        json=payload,
    )
    assert response.status_code == 201
    return response.json()["data"]


# --- catalog_items parent_id (inventory_subcategory -> inventory_category) ---


def test_subcategory_accepts_parent_of_matching_type(client, db_session, tenant):
    admin = _create_admin(db_session, tenant, "cat-admin-1@example.com")
    category = _create_catalog_item(client, admin, "inventory_category", name="Medicamento")

    subcategory = _create_catalog_item(
        client,
        admin,
        "inventory_subcategory",
        name="Antibioticos",
        parent_id=category["id"],
    )

    assert subcategory["parent_id"] == category["id"]


def test_subcategory_rejects_parent_of_wrong_type(client, db_session, tenant):
    admin = _create_admin(db_session, tenant, "cat-admin-2@example.com")
    wrong_type_parent = _create_catalog_item(client, admin, "mucous_membrane", name="Rosas")

    response = client.post(
        "/api/v1/clinic/catalogs/inventory_subcategory",
        headers=_user_headers(admin.email),
        json={"name": "Antibioticos", "parent_id": wrong_type_parent["id"]},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "catalog_item_not_found"


def test_catalog_type_without_parent_support_rejects_parent_id(client, db_session, tenant):
    admin = _create_admin(db_session, tenant, "cat-admin-3@example.com")
    other_item = _create_catalog_item(client, admin, "mucous_membrane", name="Rosas")

    response = client.post(
        "/api/v1/clinic/catalogs/mucous_membrane",
        headers=_user_headers(admin.email),
        json={"name": "Palidas", "parent_id": other_item["id"]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_catalog_parent"


def test_subcategory_rejects_parent_from_another_tenant(
    client, db_session, tenant, other_tenant
):
    admin = _create_admin(db_session, tenant, "cat-admin-4@example.com")
    other_admin = _create_admin(db_session, other_tenant, "cat-admin-5@example.com")
    foreign_category = _create_catalog_item(
        client, other_admin, "inventory_category", name="Vacuna"
    )

    response = client.post(
        "/api/v1/clinic/catalogs/inventory_subcategory",
        headers=_user_headers(admin.email),
        json={"name": "Refuerzos", "parent_id": foreign_category["id"]},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "catalog_item_not_found"


# --- inventory_items.category_catalog_item_id ---


def test_create_inventory_item_with_category_catalog_item_id_resolves_name(
    client, db_session, tenant
):
    admin = _create_admin(db_session, tenant, "inv-cat-admin-1@example.com")
    category = _create_catalog_item(
        client, admin, "inventory_category", name="Antiparasitarios"
    )

    response = client.post(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        json={
            "name": "Ivermectina",
            "category": "medication",
            "category_catalog_item_id": category["id"],
            "unit": "tablet",
        },
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["category_catalog_item_id"] == category["id"]
    assert body["category_catalog_item_name"] == "Antiparasitarios"


def test_create_inventory_item_with_cross_tenant_category_catalog_item_is_rejected(
    client, db_session, tenant, other_tenant
):
    other_admin = _create_admin(db_session, other_tenant, "inv-cat-admin-2@example.com")
    foreign_category = _create_catalog_item(
        client, other_admin, "inventory_category", name="Otro"
    )

    response = client.post(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        json={
            "name": "Ivermectina",
            "category": "medication",
            "category_catalog_item_id": foreign_category["id"],
            "unit": "tablet",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_cross_tenant_access"


def test_create_inventory_item_with_wrong_catalog_type_for_category_is_rejected(
    client, db_session, tenant
):
    admin = _create_admin(db_session, tenant, "inv-cat-admin-3@example.com")
    wrong_type_item = _create_catalog_item(client, admin, "document_type", name="Documento")

    response = client.post(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        json={
            "name": "Ivermectina",
            "category": "medication",
            "category_catalog_item_id": wrong_type_item["id"],
            "unit": "tablet",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_catalog_item_type"


def test_create_inventory_item_with_unknown_category_catalog_item_id_returns_404(
    client, tenant
):
    response = client.post(
        "/api/v1/inventory/items",
        headers=_headers(tenant),
        json={
            "name": "Ivermectina",
            "category": "medication",
            "category_catalog_item_id": str(uuid.uuid4()),
            "unit": "tablet",
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "catalog_item_not_found"


# --- exams.exam_catalog_item_id ---


def test_create_exam_with_exam_catalog_item_id_resolves_name(client, db_session, tenant):
    admin = _create_admin(db_session, tenant, "exam-cat-admin-1@example.com")
    exam_type_item = _create_catalog_item(client, admin, "exam_type", name="Hemograma")
    patient = _create_patient(client, tenant)

    response = client.post(
        "/api/v1/exams",
        headers=_headers(tenant),
        json={
            "patient_id": patient["id"],
            "exam_type": "Hemograma",
            "exam_catalog_item_id": exam_type_item["id"],
            "requested_at": "2026-04-24T10:30:00Z",
        },
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["exam_catalog_item_id"] == exam_type_item["id"]
    assert body["exam_catalog_item_name"] == "Hemograma"


def test_create_exam_with_cross_tenant_catalog_item_is_rejected(
    client, db_session, tenant, other_tenant
):
    other_admin = _create_admin(db_session, other_tenant, "exam-cat-admin-2@example.com")
    foreign_item = _create_catalog_item(client, other_admin, "exam_type", name="Hemograma")
    patient = _create_patient(client, tenant)

    response = client.post(
        "/api/v1/exams",
        headers=_headers(tenant),
        json={
            "patient_id": patient["id"],
            "exam_type": "Hemograma",
            "exam_catalog_item_id": foreign_item["id"],
            "requested_at": "2026-04-24T10:30:00Z",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_cross_tenant_access"


# --- consultation_study_requests.exam_catalog_item_id ---


def test_create_study_request_with_exam_catalog_item_id_resolves_name(
    client, db_session, tenant
):
    admin = _create_admin(db_session, tenant, "study-cat-admin-1@example.com")
    exam_type_item = _create_catalog_item(client, admin, "exam_type", name="Urianalisis")
    patient = _create_patient(client, tenant)
    consultation = _create_consultation(client, tenant, patient["id"])

    response = client.post(
        f"/api/v1/consultations/{consultation['id']}/study-requests",
        headers=_headers(tenant),
        json={
            "name": "Urianalisis",
            "study_type": "laboratory",
            "exam_catalog_item_id": exam_type_item["id"],
        },
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["exam_catalog_item_id"] == exam_type_item["id"]
    assert body["exam_catalog_item_name"] == "Urianalisis"


# --- patient_preventive_care.catalog_item_id ---


def test_create_preventive_care_with_catalog_item_id_resolves_name(client, db_session, tenant):
    admin = _create_admin(db_session, tenant, "prev-cat-admin-1@example.com")
    catalog_item = _create_catalog_item(
        client, admin, "preventive_care_type", name="Vacuna antirrabica"
    )
    patient = _create_patient(client, tenant)

    response = client.post(
        f"/api/v1/patients/{patient['id']}/preventive-care",
        headers=_headers(tenant),
        json={
            "name": "Vacuna antirrabica",
            "care_type": "vaccine",
            "catalog_item_id": catalog_item["id"],
            "applied_at": "2026-04-24T10:30:00Z",
        },
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["catalog_item_id"] == catalog_item["id"]
    assert body["catalog_item_name"] == "Vacuna antirrabica"


def test_create_preventive_care_with_cross_tenant_catalog_item_is_rejected(
    client, db_session, tenant, other_tenant
):
    other_admin = _create_admin(db_session, other_tenant, "prev-cat-admin-2@example.com")
    foreign_item = _create_catalog_item(
        client, other_admin, "preventive_care_type", name="Vacuna antirrabica"
    )
    patient = _create_patient(client, tenant)

    response = client.post(
        f"/api/v1/patients/{patient['id']}/preventive-care",
        headers=_headers(tenant),
        json={
            "name": "Vacuna antirrabica",
            "care_type": "vaccine",
            "catalog_item_id": foreign_item["id"],
            "applied_at": "2026-04-24T10:30:00Z",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_cross_tenant_access"


# --- patient_file_references.file_type_catalog_item_id ---


def test_create_file_reference_with_catalog_item_id_resolves_name(client, db_session, tenant):
    admin = _create_admin(db_session, tenant, "file-cat-admin-1@example.com")
    catalog_item = _create_catalog_item(client, admin, "document_type", name="Radiografia")
    patient = _create_patient(client, tenant)

    response = client.post(
        f"/api/v1/patients/{patient['id']}/file-references",
        headers=_headers(tenant),
        json={
            "name": "Radiografia lateral",
            "file_type": "radiography",
            "file_type_catalog_item_id": catalog_item["id"],
        },
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["file_type_catalog_item_id"] == catalog_item["id"]
    assert body["file_type_catalog_item_name"] == "Radiografia"


def test_create_file_reference_with_cross_tenant_catalog_item_is_rejected(
    client, db_session, tenant, other_tenant
):
    other_admin = _create_admin(db_session, other_tenant, "file-cat-admin-2@example.com")
    foreign_item = _create_catalog_item(client, other_admin, "document_type", name="Documento")
    patient = _create_patient(client, tenant)

    response = client.post(
        f"/api/v1/patients/{patient['id']}/file-references",
        headers=_headers(tenant),
        json={
            "name": "Radiografia lateral",
            "file_type": "radiography",
            "file_type_catalog_item_id": foreign_item["id"],
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_cross_tenant_access"

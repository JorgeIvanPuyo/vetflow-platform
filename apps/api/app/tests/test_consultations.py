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


def _create_inventory_item(client, tenant, **overrides):
    payload = {
        "name": "Amoxicilina stock",
        "category": "medication",
        "unit": "tablet",
        "current_stock": "10",
        "minimum_stock": "2",
        "sale_price_ars": "1500",
    }
    payload.update(overrides)
    response = client.post(
        "/api/v1/inventory/items",
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
    body = response.json()["data"]
    assert body["id"] == consultation["id"]
    assert body["status"] == "draft"
    assert body["medications"] == []
    assert body["study_requests"] == []


def test_create_consultation_as_draft(client, tenant):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])

    consultation = _create_consultation(
        client,
        tenant,
        patient["id"],
        status="draft",
        current_step=1,
        symptoms="Itching and redness",
    )

    assert consultation["status"] == "draft"
    assert consultation["current_step"] == 1
    assert consultation["symptoms"] == "Itching and redness"


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


def test_partial_update_step_1_data(client, tenant):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])
    consultation = _create_consultation(client, tenant, patient["id"])

    response = client.patch(
        f"/api/v1/consultations/{consultation['id']}/step",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "current_step": 1,
            "symptoms": "Vomiting",
            "symptom_duration": "2 days",
            "relevant_history": "Previous gastritis",
            "habits_and_diet": "New treats",
        },
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "draft"
    assert body["current_step"] == 1
    assert body["symptoms"] == "Vomiting"
    assert body["symptom_duration"] == "2 days"
    assert body["reason"] == "Skin irritation"


def test_partial_update_clinical_exam_numeric_fields(client, tenant):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])
    consultation = _create_consultation(client, tenant, patient["id"])

    response = client.patch(
        f"/api/v1/consultations/{consultation['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "temperature_c": 39.2,
            "current_weight_kg": 12.5,
            "heart_rate": 120,
            "respiratory_rate": 28,
            "mucous_membranes": "Pink",
            "hydration": "Normal",
            "physical_exam_findings": "Mild abdominal discomfort",
        },
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["temperature_c"] == 39.2
    assert body["current_weight_kg"] == 12.5
    assert body["heart_rate"] == 120
    assert body["respiratory_rate"] == 28
    assert body["physical_exam_findings"] == "Mild abdominal discomfort"


def test_update_diagnostic_plan_with_study_request(client, tenant):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])
    consultation = _create_consultation(client, tenant, patient["id"])

    update_response = client.patch(
        f"/api/v1/consultations/{consultation['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "diagnostic_tags": ["dermatology", "allergy"],
            "diagnostic_plan_notes": "Rule out parasites",
        },
    )
    study_response = client.post(
        f"/api/v1/consultations/{consultation['id']}/study-requests",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "name": "Skin scraping",
            "study_type": "laboratory",
            "notes": "If pruritus persists",
        },
    )

    assert update_response.status_code == 200
    assert study_response.status_code == 201
    study_request = study_response.json()["data"]
    assert study_request["tenant_id"] == str(tenant.id)
    assert study_request["consultation_id"] == consultation["id"]
    assert study_request["name"] == "Skin scraping"
    assert study_request["study_type"] == "laboratory"

    detail_response = client.get(
        f"/api/v1/consultations/{consultation['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    detail = detail_response.json()["data"]
    assert detail["diagnostic_tags"] == ["dermatology", "allergy"]
    assert detail["study_requests"][0]["id"] == study_request["id"]


def test_add_and_delete_medication_entry(client, tenant):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])
    consultation = _create_consultation(client, tenant, patient["id"])

    create_response = client.post(
        f"/api/v1/consultations/{consultation['id']}/medications",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "medication_name": "Cephalexin",
            "dose_or_quantity": "250 mg",
            "instructions": "Every 12 hours for 7 days",
        },
    )

    assert create_response.status_code == 201
    medication = create_response.json()["data"]
    assert medication["tenant_id"] == str(tenant.id)
    assert medication["consultation_id"] == consultation["id"]
    assert medication["medication_name"] == "Cephalexin"

    detail_response = client.get(
        f"/api/v1/consultations/{consultation['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert detail_response.json()["data"]["medications"][0]["id"] == medication["id"]

    delete_response = client.delete(
        f"/api/v1/consultation-medications/{medication['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert delete_response.status_code == 204

    missing_response = client.delete(
        f"/api/v1/consultation-medications/{medication['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "consultation_medication_not_found"


def test_add_medication_from_inventory_creates_movement_and_decreases_stock(client, tenant):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])
    consultation = _create_consultation(client, tenant, patient["id"])
    item = _create_inventory_item(client, tenant, current_stock="10", sale_price_ars="1200")

    response = client.post(
        f"/api/v1/consultations/{consultation['id']}/medications",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "inventory_item_id": item["id"],
            "quantity_used": "3",
            "dose_or_quantity": "3 comprimidos",
            "instructions": "Cada 12 horas",
        },
    )

    assert response.status_code == 201
    medication = response.json()["data"]
    assert medication["medication_name"] == "Amoxicilina stock"
    assert medication["inventory_item_id"] == item["id"]
    assert medication["inventory_item_name"] == "Amoxicilina stock"
    assert medication["inventory_movement_id"] is not None
    assert medication["supplied_by_clinic"] is True
    assert medication["quantity_used"] == "3.00"
    assert medication["inventory_unit"] == "tablet"
    assert medication["unit_sale_price_ars"] == "1200.00"
    assert medication["total_sale_price_ars"] == "3600.00"

    item_response = client.get(
        f"/api/v1/inventory/items/{item['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert item_response.status_code == 200
    assert item_response.json()["data"]["current_stock"] == "7.00"

    movements_response = client.get(
        f"/api/v1/inventory/items/{item['id']}/movements",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert movements_response.status_code == 200
    movement = movements_response.json()["data"][0]
    assert movement["id"] == medication["inventory_movement_id"]
    assert movement["movement_type"] == "exit"
    assert movement["reason"] == "consultation_use"
    assert movement["quantity"] == "3.00"
    assert movement["related_patient_id"] == patient["id"]
    assert movement["related_consultation_id"] == consultation["id"]


def test_add_inventory_medication_allows_manual_name_override(client, tenant):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])
    consultation = _create_consultation(client, tenant, patient["id"])
    item = _create_inventory_item(client, tenant, name="Meloxicam frasco")

    response = client.post(
        f"/api/v1/consultations/{consultation['id']}/medications",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "inventory_item_id": item["id"],
            "medication_name": "Meloxicam dosis clínica",
            "quantity_used": "1",
        },
    )

    assert response.status_code == 201
    assert response.json()["data"]["medication_name"] == "Meloxicam dosis clínica"


def test_inventory_medication_rejects_insufficient_stock(client, tenant):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])
    consultation = _create_consultation(client, tenant, patient["id"])
    item = _create_inventory_item(client, tenant, current_stock="2")

    response = client.post(
        f"/api/v1/consultations/{consultation['id']}/medications",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"inventory_item_id": item["id"], "quantity_used": "5"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_stock"


def test_inventory_medication_requires_quantity_used(client, tenant):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])
    consultation = _create_consultation(client, tenant, patient["id"])
    item = _create_inventory_item(client, tenant)

    response = client.post(
        f"/api/v1/consultations/{consultation['id']}/medications",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"inventory_item_id": item["id"]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_stock_quantity"


def test_inventory_medication_rejects_item_from_another_tenant(
    client,
    tenant,
    other_tenant,
):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])
    consultation = _create_consultation(client, tenant, patient["id"])
    foreign_item = _create_inventory_item(client, other_tenant)

    response = client.post(
        f"/api/v1/consultations/{consultation['id']}/medications",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"inventory_item_id": foreign_item["id"], "quantity_used": "1"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "inventory_item_not_found"


def test_deleting_inventory_medication_preserves_movement_and_stock(client, tenant):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])
    consultation = _create_consultation(client, tenant, patient["id"])
    item = _create_inventory_item(client, tenant, current_stock="10")

    create_response = client.post(
        f"/api/v1/consultations/{consultation['id']}/medications",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"inventory_item_id": item["id"], "quantity_used": "4"},
    )
    assert create_response.status_code == 201
    medication = create_response.json()["data"]

    delete_response = client.delete(
        f"/api/v1/consultation-medications/{medication['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert delete_response.status_code == 204

    movements_response = client.get(
        f"/api/v1/inventory/items/{item['id']}/movements",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert movements_response.status_code == 200
    assert movements_response.json()["data"][0]["id"] == medication["inventory_movement_id"]

    item_response = client.get(
        f"/api/v1/inventory/items/{item['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert item_response.status_code == 200
    assert item_response.json()["data"]["current_stock"] == "6.00"


def test_complete_consultation_with_status_completed(client, tenant):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])
    consultation = _create_consultation(client, tenant, patient["id"])

    response = client.patch(
        f"/api/v1/consultations/{consultation['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "status": "completed",
            "current_step": 8,
            "final_diagnosis": "Contact dermatitis",
            "consultation_summary": "Responded well to treatment",
            "next_control_date": "2026-05-01",
            "reminder_requested": True,
        },
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "completed"
    assert body["current_step"] == 8
    assert body["next_control_date"] == "2026-05-01"
    assert body["reminder_requested"] is True


def test_delete_consultation_safely_unlinks_exams_and_removes_dependents(
    client,
    tenant,
):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])
    consultation = _create_consultation(client, tenant, patient["id"])
    medication_response = client.post(
        f"/api/v1/consultations/{consultation['id']}/medications",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"medication_name": "Meloxicam"},
    )
    study_response = client.post(
        f"/api/v1/consultations/{consultation['id']}/study-requests",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"name": "CBC", "study_type": "laboratory"},
    )
    exam_response = client.post(
        "/api/v1/exams",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={
            "patient_id": patient["id"],
            "consultation_id": consultation["id"],
            "exam_type": "Blood test",
            "requested_at": "2026-04-24T10:30:00Z",
        },
    )
    assert medication_response.status_code == 201
    assert study_response.status_code == 201
    assert exam_response.status_code == 201

    delete_response = client.delete(
        f"/api/v1/consultations/{consultation['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert delete_response.status_code == 204
    get_response = client.get(
        f"/api/v1/consultations/{consultation['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert get_response.status_code == 404

    exam_detail = client.get(
        f"/api/v1/exams/{exam_response.json()['data']['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert exam_detail.status_code == 200
    assert exam_detail.json()["data"]["consultation_id"] is None

    medication_id = medication_response.json()["data"]["id"]
    study_request_id = study_response.json()["data"]["id"]
    assert client.delete(
        f"/api/v1/consultation-medications/{medication_id}",
        headers={"X-Tenant-Id": str(tenant.id)},
    ).status_code == 404
    assert client.delete(
        f"/api/v1/consultation-study-requests/{study_request_id}",
        headers={"X-Tenant-Id": str(tenant.id)},
    ).status_code == 404


def test_prevent_cross_tenant_consultation_access(client, tenant, other_tenant):
    owner = _create_owner(client, other_tenant, "Foreign Owner")
    patient = _create_patient(client, other_tenant, owner["id"], "Nina")
    consultation = _create_consultation(client, other_tenant, patient["id"])

    get_response = client.get(
        f"/api/v1/consultations/{consultation['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    patch_response = client.patch(
        f"/api/v1/consultations/{consultation['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"current_step": 2},
    )
    delete_response = client.delete(
        f"/api/v1/consultations/{consultation['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert get_response.status_code == 404
    assert patch_response.status_code == 404
    assert delete_response.status_code == 404


def test_prevent_cross_tenant_medication_and_study_access(
    client,
    tenant,
    other_tenant,
):
    foreign_owner = _create_owner(client, other_tenant, "Foreign Owner")
    foreign_patient = _create_patient(client, other_tenant, foreign_owner["id"], "Nina")
    foreign_consultation = _create_consultation(
        client,
        other_tenant,
        foreign_patient["id"],
    )
    medication = client.post(
        f"/api/v1/consultations/{foreign_consultation['id']}/medications",
        headers={"X-Tenant-Id": str(other_tenant.id)},
        json={"medication_name": "Foreign medication"},
    ).json()["data"]
    study_request = client.post(
        f"/api/v1/consultations/{foreign_consultation['id']}/study-requests",
        headers={"X-Tenant-Id": str(other_tenant.id)},
        json={"name": "Foreign study", "study_type": "other"},
    ).json()["data"]

    create_med_response = client.post(
        f"/api/v1/consultations/{foreign_consultation['id']}/medications",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"medication_name": "Blocked medication"},
    )
    delete_med_response = client.delete(
        f"/api/v1/consultation-medications/{medication['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    create_study_response = client.post(
        f"/api/v1/consultations/{foreign_consultation['id']}/study-requests",
        headers={"X-Tenant-Id": str(tenant.id)},
        json={"name": "Blocked study", "study_type": "other"},
    )
    delete_study_response = client.delete(
        f"/api/v1/consultation-study-requests/{study_request['id']}",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert create_med_response.status_code == 404
    assert delete_med_response.status_code == 404
    assert create_study_response.status_code == 404
    assert delete_study_response.status_code == 404


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


def test_clinical_history_consultation_item_uses_expected_summary_fallback(
    client,
    tenant,
):
    owner = _create_owner(client, tenant)
    patient = _create_patient(client, tenant, owner["id"])
    consultation = _create_consultation(
        client,
        tenant,
        patient["id"],
        final_diagnosis=None,
        presumptive_diagnosis=None,
        consultation_summary="Stable after treatment",
    )

    response = client.get(
        f"/api/v1/patients/{patient['id']}/clinical-history",
        headers={"X-Tenant-Id": str(tenant.id)},
    )

    assert response.status_code == 200
    timeline_item = response.json()["data"]["timeline"][0]
    assert timeline_item == {
        "type": "consultation",
        "id": consultation["id"],
        "date": "2026-04-24T10:30:00",
        "title": "Skin irritation",
        "summary": "Stable after treatment",
    }

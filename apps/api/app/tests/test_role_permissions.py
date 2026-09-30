"""Role policy: shared operations, veterinary responsibility, tenant boundaries."""
import uuid

import pytest

from app.models.user import User
from app.tests.test_secretary_role import actors, data, headers
from app.tests.test_fiscal_issuers import _payload as issuer_payload
from app.tests.test_sales import _payload as sale_payload
from app.tests.test_sale_fiscal_documents import _storage, PDF

ROLES = ("clinic_admin", "medico_veterinario", "contador", "secretaria")
NON_CLINICAL = ("clinic_admin", "contador", "secretaria")


@pytest.fixture()
def patient(client, actors):
    auth = headers(actors["medico_veterinario"])
    owner = data(client.post("/api/v1/owners", headers=auth,
                            json={"full_name": "Cliente", "phone": "555"}), 201)
    return data(client.post("/api/v1/patients", headers=auth,
                           json={"owner_id": owner["id"], "name": "Luna", "species": "canine"}), 201)


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("catalog_type", ["mucous_membrane", "inventory_category"])
def test_clinic_operators_manage_catalogs(client, actors, tenant, role, catalog_type):
    auth = headers(actors[role])
    base = f"/api/v1/clinic/catalogs/{catalog_type}"
    item = data(client.post(base, headers=auth, json={"name": "Operativo"}), 201)
    assert item["tenant_id"] == str(tenant.id)
    assert item["created_by_user_id"] == str(actors[role].id)
    url = f"{base}/{item['id']}"
    assert data(client.patch(url, headers=auth, json={"name": "Editado"}))["name"] == "Editado"
    for action, active in [("deactivate", False), ("activate", True)]:
        assert data(client.post(f"{url}/{action}", headers=auth))["is_active"] is active
    data(client.patch(base + "/reorder", headers=auth, json={"items": [{"id": item["id"], "sort_order": 2}]}))
    data(client.post(base + "/restore-defaults", headers=auth))


@pytest.mark.parametrize("role", ROLES)
def test_payment_methods_and_operational_settings(client, actors, role):
    auth = headers(actors[role])
    method = data(client.post("/api/v1/payment-methods", headers=auth,
                              json={"label": "Efectivo", "type": "cash"}), 201)
    for active in [False, True]:
        result = data(client.patch(f"/api/v1/payment-methods/{method['id']}", headers=auth,
                                   json={"label": "Caja", "is_active": active}))
        assert result["is_active"] is active
        assert result["label"] == "Caja"
    data(client.patch("/api/v1/clinic/profile", headers=auth, json={"display_name": "Clínica"}))
    data(client.patch("/api/v1/clinic/preferences", headers=auth, json={"locale": "es-PA"}))
    # Team editing is display-name only; no role/tenant/security fields are exposed.
    data(client.patch(f"/api/v1/clinic/team/{actors[role].id}", headers=auth, json={"full_name": "Operador"}))
    assert client.get("/api/v1/admin/users", headers=auth).status_code == 403
    assert client.get("/api/v1/admin/tenants", headers=auth).status_code == 403


@pytest.mark.parametrize("role", ROLES)
def test_veterinarian_selector_and_assignment(client, actors, patient, role):
    auth = headers(actors[role])
    vet_id = str(actors["medico_veterinario"].id)
    team = data(client.get("/api/v1/clinic/team?responsible_only=true", headers=auth))
    assert [row["id"] for row in team] == [vet_id]
    payload = {"title": "Cita", "patient_id": patient["id"], "appointment_type": "consultation",
               "assigned_user_id": vet_id, "start_at": "2026-09-29T10:00:00Z",
               "end_at": "2026-09-29T10:30:00Z"}
    appointment = data(client.post("/api/v1/appointments", headers=auth, json=payload), 201)
    assert appointment["created_by_user_id"] == str(actors[role].id)
    for invalid_role in (*NON_CLINICAL, "superadmin"):
        invalid = str(actors[invalid_role].id)
        response = client.post("/api/v1/appointments", headers=auth, json={**payload, "assigned_user_id": invalid})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_responsible_user"
        assert client.patch(f"/api/v1/appointments/{appointment['id']}", headers=auth,
                            json={"assigned_user_id": invalid}).status_code == 422


@pytest.mark.parametrize("role", NON_CLINICAL)
def test_non_veterinarians_read_but_cannot_author_clinical_acts(client, actors, patient, role):
    auth = headers(actors[role])
    vet_auth = headers(actors["medico_veterinario"])
    clinical = {"patient_id": patient["id"], "reason": "Control", "visit_date": "2026-09-29T10:00:00Z"}
    consultation = data(client.post("/api/v1/consultations", headers=vet_auth, json=clinical), 201)
    data(client.get(f"/api/v1/consultations/{consultation['id']}", headers=auth))
    for method, url, payload in [
        ("post", "/consultations", clinical),
        ("patch", f"/consultations/{consultation['id']}", {"status": "completed"}),
        ("patch", f"/consultations/{consultation['id']}/step", {"current_step": 2}),
        ("delete", f"/consultations/{consultation['id']}", None),
        ("post", "/exams", {"patient_id": patient["id"], "exam_type": "Control", "requested_at": "2026-09-29T10:00:00Z"}),
        ("patch", f"/exams/{uuid.uuid4()}", {"status": "result_loaded"}),
        ("post", f"/patients/{patient['id']}/preventive-care", {}),
        ("post", "/follow-ups", {}),
    ]:
        assert client.request(method, "/api/v1" + url, headers=auth, json=payload).status_code == 403
    for field, value in [("allergies", "Clinical"), ("chronic_conditions", None), ("weight_kg", 5)]:
        assert client.patch(f"/api/v1/patients/{patient['id']}", headers=auth, json={field: value}).status_code == 403
    data(client.patch(f"/api/v1/patients/{patient['id']}", headers=auth, json={"name": "Luna II"}))
    assert client.delete(f"/api/v1/patients/{patient['id']}", headers=auth).status_code == 403
    empty = data(client.post("/api/v1/patients", headers=auth,
                            json={"owner_id": patient["owner_id"], "name": "Temporal", "species": "canine"}), 201)
    assert client.delete(f"/api/v1/patients/{empty['id']}", headers=auth).status_code == 204


def test_clinical_responsibility_rejects_all_non_vets_and_inactive_vets(client, actors, patient, db_session):
    auth = headers(actors["medico_veterinario"])
    payload = {"patient_id": patient["id"], "reason": "Control", "visit_date": "2026-09-29T10:00:00Z"}
    consultation = data(client.post("/api/v1/consultations", headers=auth, json=payload), 201)
    for role in (*NON_CLINICAL, "superadmin"):
        assigned = {"attending_user_id": str(actors[role].id)}
        assert client.post("/api/v1/consultations", headers=auth, json={**payload, **assigned}).status_code == 422
        assert client.patch(f"/api/v1/consultations/{consultation['id']}", headers=auth, json=assigned).status_code == 422
    data(client.patch(f"/api/v1/consultations/{consultation['id']}", headers=auth, json={"status": "completed"}))
    inactive = actors["contador"]
    inactive.role = "medico_veterinario"
    inactive.is_active = False
    db_session.commit()
    assert client.patch(f"/api/v1/consultations/{consultation['id']}", headers=auth,
                        json={"attending_user_id": str(inactive.id)}).status_code == 404


@pytest.mark.parametrize("role", ROLES)
def test_followup_administration_separate_from_clinical_completion(client, actors, patient, role):
    auth = headers(actors[role])
    follow = data(client.post("/api/v1/follow-ups", headers=headers(actors["medico_veterinario"]), json={
        "patient_id": patient["id"], "title": "Revisión clínica", "follow_up_type": "consultation_control",
        "due_at": "2026-09-30T10:00:00Z", "assigned_user_id": str(actors["medico_veterinario"].id),
    }), 201)
    url = f"/api/v1/follow-ups/{follow['id']}"
    data(client.patch(url, headers=auth, json={"due_at": "2026-10-01T10:00:00Z"}))
    for invalid_role in NON_CLINICAL:
        assert client.patch(url, headers=auth, json={"assigned_user_id": str(actors[invalid_role].id)}).status_code == 422
    expected = 200 if role == "medico_veterinario" else 403
    assert client.post(url + "/complete", headers=auth).status_code == expected
    assert client.patch(url, headers=auth, json={"status": "completed"}).status_code == expected
    data(client.post(url + "/cancel", headers=auth, json={"notes": "Reprogramar"}))


@pytest.mark.parametrize("role", ROLES)
def test_fiscal_configuration_and_operator_are_separate(client, actors, role):
    auth = headers(actors[role])
    for invalid in NON_CLINICAL:
        response = client.post("/api/v1/fiscal-issuers", headers=auth, json=issuer_payload(actors[invalid].id))
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_fiscal_user"
    issuer = data(client.post("/api/v1/fiscal-issuers", headers=auth,
                             json=issuer_payload(actors["medico_veterinario"].id)), 201)
    for invalid in NON_CLINICAL:
        assert client.patch(f"/api/v1/fiscal-issuers/{issuer['id']}", headers=auth,
                            json={"user_id": str(actors[invalid].id)}).status_code == 422
    sale = data(client.post("/api/v1/sales", headers=auth, json=sale_payload()), 201)
    url = f"/api/v1/sales/{sale['id']}"
    confirmed = data(client.post(url + "/confirm", headers=auth, json={"confirm": True}))
    assert confirmed["confirmed_by_user_id"] == str(actors[role].id)
    assert confirmed["fiscal_status"] == "pending"
    method = data(client.post("/api/v1/payment-methods", headers=auth, json={"label": "Caja", "type": "cash"}), 201)
    payment = data(client.post(url + "/payments", headers=auth, json={"payment_method_id": method["id"],
        "amount_ars": "20", "received_at": "2026-09-29T10:00:00Z"}), 201)
    assert payment["created_by_user_id"] == str(actors[role].id)
    _storage(client)
    document = data(client.post(url + "/fiscal-document", headers=auth, data={
        "fiscal_issuer_id": issuer["id"], "document_type": "receipt_c", "document_code": "015",
        "document_number": "0001-123", "issue_date": "2026-09-29",
    }, files={"file": ("receipt.pdf", PDF, "application/pdf")}), 201)
    assert document["fiscal_issuer_id"] == issuer["id"]
    assert document["uploaded_by_user_id"] == str(actors[role].id)
    assert data(client.get(f"/api/v1/fiscal-issuers/{issuer['id']}", headers=auth))["user_id"] == str(actors["medico_veterinario"].id)


def test_fiscal_eligibility_rechecked_after_role_change(client, actors, db_session):
    auth = headers(actors["clinic_admin"])
    vet = actors["medico_veterinario"]
    issuer = data(client.post("/api/v1/fiscal-issuers", headers=auth, json=issuer_payload(vet.id)), 201)
    vet.role = "contador"
    db_session.commit()
    assert data(client.get("/api/v1/fiscal-issuers?active_only=true", headers=auth)) == []
    assert client.patch(f"/api/v1/fiscal-issuers/{issuer['id']}", headers=auth,
                        json={"is_active": True}).status_code == 422
    from app.services.sale_fiscal_document import SaleFiscalDocumentService
    from app.core.errors import AppError
    with pytest.raises(AppError) as error:
        SaleFiscalDocumentService(db_session, storage=_storage(client))._require_issuer(
            vet.tenant_id, uuid.UUID(issuer["id"]), require_active=True)
    assert error.value.code == "invalid_fiscal_user"


def test_operator_cannot_cross_tenant_catalog_payment_or_responsibility(client, actors, other_tenant, db_session, patient):
    foreign = User(id=uuid.uuid4(), tenant_id=other_tenant.id, email="foreign@example.com",
                   full_name="Foreign Vet", role="medico_veterinario", is_active=True)
    db_session.add(foreign); db_session.commit()
    other_auth = headers(foreign)
    auth = {**headers(actors["contador"]), "X-Acting-Tenant-Id": str(other_tenant.id)}
    category = data(client.post("/api/v1/clinic/catalogs/inventory_category", headers=other_auth, json={"name": "Ajena"}), 201)
    assert client.patch(f"/api/v1/clinic/catalogs/inventory_category/{category['id']}", headers=auth, json={"name": "Hack"}).status_code == 404
    assert all(row["id"] != category["id"] for row in data(client.get("/api/v1/clinic/catalogs/inventory_category", headers=auth)))
    method = data(client.post("/api/v1/payment-methods", headers=other_auth, json={"label": "Ajeno", "type": "cash"}), 201)
    assert client.patch(f"/api/v1/payment-methods/{method['id']}", headers=auth, json={"is_active": False}).status_code == 404
    assert client.post("/api/v1/fiscal-issuers", headers=auth, json=issuer_payload(foreign.id)).status_code == 404
    payload = {"patient_id": patient["id"], "reason": "Control", "visit_date": "2026-09-29T10:00:00Z", "attending_user_id": str(foreign.id)}
    assert client.post("/api/v1/consultations", headers=headers(actors["medico_veterinario"]), json=payload).status_code == 404


@pytest.mark.parametrize("role", ROLES)
def test_patient_administrative_crud_and_clinical_fields_are_separate(client, actors, tenant, role):
    actor = actors[role]
    auth = headers(actor)
    owner = data(client.post("/api/v1/owners", headers=auth,
                            json={"full_name": "Propietario", "phone": "555"}), 201)
    payload = {"owner_id": owner["id"], "name": "Administrativo", "species": "canine"}
    patient = data(client.post("/api/v1/patients", headers=auth, json=payload), 201)
    assert patient["tenant_id"] == str(tenant.id)
    assert patient["created_by_user_id"] == str(actor.id)
    url = f"/api/v1/patients/{patient['id']}"
    assert data(client.get(url, headers=auth))["id"] == patient["id"]
    assert data(client.patch(url, headers=auth, json={"name": "Editado"}))["name"] == "Editado"
    assert client.delete(url, headers=auth).status_code == 204

    for field, value, expected in [
        ("weight_kg", 5, "5.00"),
        ("allergies", "Penicilina", "Penicilina"),
        ("chronic_conditions", None, None),
    ]:
        response = client.post("/api/v1/patients", headers=auth, json={**payload, field: value})
        if role == "medico_veterinario":
            assert data(response, 201)[field] == expected
        else:
            assert response.status_code == 403
            assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.parametrize("role", NON_CLINICAL)
@pytest.mark.parametrize("path,payload", [
    ("rewrite-clinical-note", {"field": "anamnesis", "text": "Prurito desde ayer"}),
    ("generate-consultation-summary", {"consultation": {"reason": "Prurito"}}),
])
def test_non_veterinarians_cannot_use_clinical_ai(client, actors, monkeypatch, role, path, payload):
    from app.services.ai_service import AIService

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Clinical AI must reject the actor before invoking the service")

    monkeypatch.setattr(AIService, "rewrite_clinical_note", fail_if_called)
    monkeypatch.setattr(AIService, "generate_consultation_summary", fail_if_called)
    response = client.post(f"/api/v1/ai/{path}", headers=headers(actors[role]), json=payload)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"

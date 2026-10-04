import uuid

import pytest

from app.models.user import User
from app.tests.test_admin_users import _mock_firebase
from app.tests.test_sales import _payload as sale_payload


@pytest.fixture()
def actors(db_session, tenant, monkeypatch):
    import app.core.tenant as tenant_core

    monkeypatch.setattr(tenant_core, "verify_id_token", lambda token: {"email": token})
    users = {}
    for role in ("secretaria", "medico_veterinario", "clinic_admin", "contador", "superadmin"):
        user = User(id=uuid.uuid4(), tenant_id=tenant.id, email=f"{role}@example.com",
                    full_name=role, role=role, is_active=True)
        db_session.add(user)
        users[role] = user
    db_session.commit()
    return users


def headers(user):
    return {"Authorization": f"Bearer {user.email}"}


def data(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


def test_invite_secretary_and_auth_identity(client, actors, tenant, monkeypatch):
    _mock_firebase(monkeypatch)
    invited = data(client.post("/api/v1/admin/users/invite",
        headers=headers(actors["superadmin"]), json={
            "email": "new-secretary@example.com", "full_name": "Secretaria nueva",
            "role": "secretaria", "tenant_id": str(tenant.id),
        }), 201)
    assert invited["user"]["role"] == "secretaria"
    me = data(client.get("/api/v1/auth/me", headers=headers(actors["secretaria"])))
    assert me["role"] == "secretaria"


def test_secretary_administration_agenda_and_isolation(client, actors, tenant, other_tenant):
    secretary = actors["secretaria"]
    auth = {**headers(secretary), "X-Tenant-Id": str(other_tenant.id),
            "X-Acting-Tenant-Id": str(other_tenant.id)}
    owner = data(client.post("/api/v1/owners", headers=auth, json={"full_name": "Cliente", "phone": "555"}), 201)
    assert owner["tenant_id"] == str(tenant.id)
    data(client.patch(f"/api/v1/owners/{owner['id']}", headers=auth, json={"phone": "123"}))
    removable = data(client.post("/api/v1/owners", headers=auth,
                      json={"full_name": "Temporal", "phone": "123"}), 201)
    assert client.delete(f"/api/v1/owners/{removable['id']}", headers=auth).status_code == 204
    patient = data(client.post("/api/v1/patients", headers=auth,
        json={"owner_id": owner["id"], "name": "Luna", "species": "canine"}), 201)
    data(client.patch(f"/api/v1/patients/{patient['id']}", headers=auth, json={"name": "Luna II"}))
    assert client.delete(f"/api/v1/owners/{owner['id']}", headers=auth).status_code == 403
    data(client.get(f"/api/v1/patients/{patient['id']}", headers=auth))
    for field in ("allergies", "chronic_conditions", "weight_kg"):
        value = 5 if field == "weight_kg" else "Diagnóstico"
        assert client.patch(f"/api/v1/patients/{patient['id']}", headers=auth, json={field: value}).status_code == 403

    team = data(client.get("/api/v1/clinic/team?responsible_only=true", headers=auth))
    assert str(secretary.id) not in {row["id"] for row in team}
    assert str(actors["medico_veterinario"].id) in {row["id"] for row in team}
    assert str(secretary.id) in {row["id"] for row in data(client.get("/api/v1/clinic/team", headers=auth))}
    payload = {"title": "Cita", "patient_id": patient["id"], "owner_id": owner["id"],
               "assigned_user_id": str(actors["medico_veterinario"].id),
               "appointment_type": "consultation", "start_at": "2026-09-28T10:00:00Z",
               "end_at": "2026-09-28T10:30:00Z"}
    appointment = data(client.post("/api/v1/appointments", headers=auth, json=payload), 201)
    assert appointment["created_by_user_id"] == str(secretary.id)
    url = f"/api/v1/appointments/{appointment['id']}"
    data(client.patch(url, headers=auth, json={"title": "Reprogramada"}))
    # Nobody, including an admin, can assign a secretary as the clinician.
    for actor in (secretary, actors["clinic_admin"]):
        assert client.patch(url, headers=headers(actor),
                            json={"assigned_user_id": str(secretary.id)}).status_code == 422
    data(client.patch(url, headers=auth, json={"status": "cancelled"}))
    assert client.delete(url, headers=auth).status_code == 204
    foreign = data(client.post("/api/v1/owners", headers={"X-Tenant-Id": str(other_tenant.id)},
                               json={"full_name": "Ajeno", "phone": "999"}), 201)
    assert client.get(f"/api/v1/owners/{foreign['id']}", headers=auth).status_code == 404
    assert client.patch(f"/api/v1/owners/{foreign['id']}", headers=auth, json={"phone": "hack"}).status_code == 404


@pytest.mark.parametrize("method,path", [
    ("post", "/consultations"), ("patch", "/consultations/{id}"),
    ("patch", "/consultations/{id}/step"), ("delete", "/consultations/{id}"),
    ("post", "/exams"), ("patch", "/exams/{id}"),
    ("post", "/patients/{id}/preventive-care"), ("post", "/follow-ups"),
    ("post", "/follow-ups/{id}/complete"),
    ("get", "/admin/users"), ("post", "/admin/users/invite"), ("get", "/admin/tenants"),
    ("post", "/admin/tenants"),
])
def test_secretary_sensitive_requests_are_forbidden(client, actors, method, path):
    response = client.request(method, "/api/v1" + path.format(id=uuid.uuid4()),
                              headers=headers(actors["secretaria"]), json={})
    assert response.status_code == 403, response.text


def test_secretary_commercial_operations_are_not_fiscal(client, actors):
    auth = headers(actors["secretaria"])
    supplier = data(client.post("/api/v1/suppliers", headers=auth, json={"name": "Proveedor"}), 201)
    data(client.patch(f"/api/v1/suppliers/{supplier['id']}", headers=auth, json={"phone": "123"}))
    for operation in ("deactivate", "activate"):
        data(client.post(f"/api/v1/suppliers/{supplier['id']}/{operation}", headers=auth))
    item = data(client.post("/api/v1/inventory/items", headers=auth,
                json={"name": "Alimento", "category": "food", "unit": "unit", "minimum_stock": "0"}), 201)
    data(client.post(f"/api/v1/inventory/items/{item['id']}/movements/entry",
                     headers=auth, json={"quantity": "2"}), 201)
    from app.tests.test_purchases import _payload as purchase_payload
    purchase = data(client.post("/api/v1/purchases", headers=auth,
                    json=purchase_payload(item["id"], supplier["id"])), 201)
    data(client.patch(f"/api/v1/purchases/{purchase['id']}", headers=auth, json={"notes": "Recepción"}))
    data(client.post(f"/api/v1/purchases/{purchase['id']}/receive", headers=auth, json={"confirm": True}))
    data(client.post(f"/api/v1/purchases/{purchase['id']}/reverse-receipt", headers=auth,
                     json={"reason": "Corrección"}))
    owner = data(client.post("/api/v1/owners", headers=auth, json={"full_name": "Cliente venta", "phone": "555"}), 201)
    sale = data(client.post("/api/v1/sales", headers=auth, json={**sale_payload(), "owner_id": owner["id"]}), 201)
    url = f"/api/v1/sales/{sale['id']}"
    confirmed = data(client.post(url + "/confirm", headers=auth, json={"confirm": True}))
    assert confirmed["confirmed_by_user_id"] == str(actors["secretaria"].id)
    assert confirmed["fiscal_status"] == "pending"
    method = data(client.post("/api/v1/payment-methods", headers=headers(actors["clinic_admin"]),
                              json={"label": "Efectivo", "type": "cash"}), 201)
    payment = data(client.post(url + "/payments", headers=auth, json={
        "payment_method_id": method["id"], "amount_ars": "20",
        "received_at": "2026-09-28T10:00:00Z",
    }), 201)
    assert payment["created_by_user_id"] == str(actors["secretaria"].id)
    data(client.post(f"/api/v1/sale-payments/{payment['id']}/void", headers=auth, json={"reason": "Corrección"}))


def test_secretary_cannot_be_assigned_clinical_or_fiscal_responsibility(client, actors):
    auth = headers(actors["medico_veterinario"])
    owner = data(client.post("/api/v1/owners", headers=auth, json={"full_name": "Cliente", "phone": "555"}), 201)
    patient = data(client.post("/api/v1/patients", headers=auth,
                              json={"owner_id": owner["id"], "name": "Luna", "species": "canine"}), 201)
    clinical = {"patient_id": patient["id"], "reason": "Control", "visit_date": "2026-09-28T10:00:00Z",
                "attending_user_id": str(actors["secretaria"].id)}
    rejected = client.post("/api/v1/consultations", headers=auth, json=clinical)
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "invalid_responsible_user"
    clinical["attending_user_id"] = str(actors["medico_veterinario"].id)
    consultation = data(client.post("/api/v1/consultations", headers=auth, json=clinical), 201)
    data(client.get(f"/api/v1/consultations/{consultation['id']}", headers=headers(actors["secretaria"])))
    assert client.delete(f"/api/v1/owners/{owner['id']}", headers=headers(actors["secretaria"])).status_code == 403
    data(client.get(f"/api/v1/consultations/{consultation['id']}", headers=auth))
    response = client.post("/api/v1/fiscal-issuers", headers=auth, json={
        "user_id": str(actors["secretaria"].id), "display_name": "No permitido", "tax_id": "123",
        "can_issue_service_receipt_c": True, "service_document_type": "receipt_c", "service_document_code": "015",
    })
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_fiscal_user"

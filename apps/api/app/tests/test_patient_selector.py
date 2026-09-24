import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models.owner import Owner
from app.models.patient import Patient


@pytest.fixture()
def selector_patients(db_session, tenant, other_tenant):
    owners = [
        Owner(id=uuid.uuid4(), tenant_id=tenant.id, full_name="Ana Perez", phone="111"),
        Owner(id=uuid.uuid4(), tenant_id=tenant.id, full_name="Maria Torres", phone="222"),
        Owner(id=uuid.uuid4(), tenant_id=other_tenant.id, full_name="Private owner", phone="999"),
    ]
    db_session.add_all(owners)
    db_session.flush()
    names = [f"Mascota {i:03d}" for i in range(65)] + ["Luna", "luna", "Zafiro"]
    patients = [Patient(id=uuid.uuid4(), tenant_id=tenant.id, owner_id=owners[i % 2].id,
                        name=name, species="dog") for i, name in enumerate(names)]
    db_session.add_all(patients + [
        Patient(tenant_id=other_tenant.id, owner_id=owners[2].id, name="Zafiro", species="dog"),
    ])
    db_session.commit()
    return patients, owners


def test_patient_selector_paginates_in_stable_name_order(client, tenant, selector_patients):
    patients, owners = selector_patients
    found = []
    for page in range(1, 4):
        response = client.get("/api/v1/patients", headers={"X-Tenant-Id": str(tenant.id)},
                              params={"sort_by": "name", "page_size": 30, "page": page})
        assert response.status_code == 200
        body = response.json()
        assert body["meta"] == {"page": page, "page_size": 30, "total": len(patients)}
        assert all(row["tenant_id"] == str(tenant.id) for row in body["data"])
        assert all(row["owner_name"] in {owner.full_name for owner in owners[:2]} for row in body["data"])
        found.extend(row["id"] for row in body["data"])
    expected = sorted(patients, key=lambda patient: (patient.name.lower(), str(patient.id)))
    assert found == [str(patient.id) for patient in expected]
    assert len(set(found)) == len(patients)


@pytest.mark.parametrize("search", ["zaf", "AFIR", "Zafiro"])
def test_patient_selector_partial_search_beyond_page_one_is_tenant_scoped(client, tenant, selector_patients, search):
    patients, _ = selector_patients
    headers = {"X-Tenant-Id": str(tenant.id)}
    params = {"sort_by": "name", "page_size": 30}
    first = client.get("/api/v1/patients", headers=headers, params=params).json()
    assert str(patients[-1].id) not in [row["id"] for row in first["data"]]
    result = client.get("/api/v1/patients", headers=headers, params={**params, "search": search}).json()
    assert result["meta"]["total"] == 1
    assert [row["id"] for row in result["data"]] == [str(patients[-1].id)]
    empty = client.get("/api/v1/patients", headers=headers, params={**params, "search": "missing"}).json()
    assert empty["data"] == []
    assert empty["meta"]["total"] == 0


def test_patient_selector_distinguishes_names_and_filters_owners(client, tenant, selector_patients):
    _, owners = selector_patients
    headers = {"X-Tenant-Id": str(tenant.id)}
    params = {"search": "luna", "sort_by": "name", "page_size": 30}
    rows = client.get("/api/v1/patients", headers=headers, params=params).json()["data"]
    assert {row["owner_name"] for row in rows} == {"Ana Perez", "Maria Torres"}
    own = client.get("/api/v1/patients", headers=headers, params={**params, "owner_id": str(owners[0].id)}).json()
    assert own["meta"]["total"] == 1
    foreign = client.get("/api/v1/patients", headers=headers, params={**params, "owner_id": str(owners[2].id)}).json()
    assert foreign["meta"]["total"] == 0


def test_patient_selector_does_not_expose_owner_from_inconsistent_cross_tenant_link(client, db_session, tenant, selector_patients):
    _, owners = selector_patients
    patient = Patient(tenant_id=tenant.id, owner_id=owners[2].id, name="Legacy", species="dog")
    db_session.add(patient)
    db_session.commit()
    response = client.get("/api/v1/patients", headers={"X-Tenant-Id": str(tenant.id)}, params={"search": "Legacy", "sort_by": "name"})
    assert response.status_code == 200
    assert response.json()["data"][0]["owner_name"] is None
    assert "Private owner" not in response.text


def test_patient_name_order_is_opt_in_and_validated(client, db_session, tenant):
    owner = Owner(tenant_id=tenant.id, full_name="Owner", phone="111")
    db_session.add(owner)
    db_session.flush()
    now = datetime.now(UTC)
    db_session.add_all([
        Patient(tenant_id=tenant.id, owner_id=owner.id, name="Ana", species="dog", created_at=now - timedelta(days=1)),
        Patient(tenant_id=tenant.id, owner_id=owner.id, name="Zoe", species="dog", created_at=now),
    ])
    db_session.commit()
    headers = {"X-Tenant-Id": str(tenant.id)}
    default = client.get("/api/v1/patients", headers=headers).json()
    assert [row["name"] for row in default["data"]] == ["Zoe", "Ana"]
    assert default["meta"] == {"page": 1, "page_size": 2, "total": 2}
    assert client.get("/api/v1/patients", headers=headers, params={"sort_by": "unknown"}).status_code == 422

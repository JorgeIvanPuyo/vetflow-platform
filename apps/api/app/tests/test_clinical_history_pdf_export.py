import uuid

from sqlalchemy.orm import Session

from app.schemas.patient import ClinicalHistoryPdfExportRequest
from app.services.clinical_history_pdf import ClinicalHistoryPdfService


def _headers(tenant) -> dict:
    return {"X-Tenant-Id": str(tenant.id)}


def _create_owner(
    client,
    tenant,
    *,
    full_name: str = "María López",
    phone: str = "555-1000",
    email: str | None = "maria@example.com",
    address: str | None = "Calle 10",
) -> dict:
    response = client.post(
        "/api/v1/owners",
        headers=_headers(tenant),
        json={
            "full_name": full_name,
            "phone": phone,
            "email": email,
            "address": address,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_patient(client, tenant, owner_id: str, name: str = "Luna") -> dict:
    response = client.post(
        "/api/v1/patients",
        headers=_headers(tenant),
        json={
            "owner_id": owner_id,
            "name": name,
            "species": "Canine",
            "breed": "Criolla",
            "sex": "Hembra",
            "estimated_age": "3 años",
            "weight_kg": 12.5,
            "allergies": "Penicilina",
            "chronic_conditions": "Dermatitis",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_patient_for_tenant(client, tenant, name: str = "Luna") -> dict:
    owner = _create_owner(client, tenant, full_name=f"{name} Owner")
    return _create_patient(client, tenant, owner["id"], name)


def _create_consultation(client, tenant, patient_id: str, **overrides) -> dict:
    payload = {
        "patient_id": patient_id,
        "visit_date": "2026-04-24T10:30:00Z",
        "reason": "Irritación de piel",
        "anamnesis": "Prurito hace 3 días",
        "clinical_exam": "Eritema leve",
        "presumptive_diagnosis": "Dermatitis alérgica",
        "diagnostic_plan": "Raspado si persiste",
        "therapeutic_plan": "Tratamiento tópico",
        "final_diagnosis": "Dermatitis por contacto",
        "indications": "Volver si empeora",
        "consultation_summary": "Paciente estable",
    }
    payload.update(overrides)
    response = client.post(
        "/api/v1/consultations",
        headers=_headers(tenant),
        json=payload,
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_exam(client, tenant, patient_id: str, **overrides) -> dict:
    payload = {
        "patient_id": patient_id,
        "exam_type": "Hemograma",
        "requested_at": "2026-04-25T10:30:00Z",
        "observations": "Control inflamatorio",
    }
    payload.update(overrides)
    response = client.post(
        "/api/v1/exams",
        headers=_headers(tenant),
        json=payload,
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_preventive_care(client, tenant, patient_id: str, **overrides) -> dict:
    payload = {
        "name": "Rabia anual",
        "care_type": "vaccine",
        "applied_at": "2026-04-20T10:30:00Z",
        "next_due_at": "2027-04-20T10:30:00Z",
        "lot_number": "LOT-123",
        "notes": "Sin reacción",
    }
    payload.update(overrides)
    response = client.post(
        f"/api/v1/patients/{patient_id}/preventive-care",
        headers=_headers(tenant),
        json=payload,
    )
    assert response.status_code == 201
    return response.json()["data"]


def _create_file_reference(client, tenant, patient_id: str, **overrides) -> dict:
    payload = {
        "name": "Radiografía lateral",
        "file_type": "radiography",
        "description": "Referencia externa",
        "external_url": "https://example.com/rx.pdf",
    }
    payload.update(overrides)
    response = client.post(
        f"/api/v1/patients/{patient_id}/file-references",
        headers=_headers(tenant),
        json=payload,
    )
    assert response.status_code == 201
    return response.json()["data"]


def _export_text_lines(
    db_session: Session,
    tenant,
    patient_id: str,
    **options,
) -> list[str]:
    export = ClinicalHistoryPdfService(db_session).export_patient_history_pdf(
        tenant.id,
        uuid.UUID(patient_id),
        ClinicalHistoryPdfExportRequest(**options),
    )
    return export.text_lines


def test_export_pdf_success_with_default_options(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(client, tenant, patient["id"])

    response = client.post(
        f"/api/v1/patients/{patient['id']}/clinical-history/export-pdf",
        headers=_headers(tenant),
        json={},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert "attachment;" in response.headers["content-disposition"]
    assert "historia-clinica-luna-" in response.headers["content-disposition"]


def test_export_pdf_includes_patient_and_owner_data_when_enabled(
    client,
    tenant,
    db_session,
):
    owner = _create_owner(client, tenant, full_name="Ana Pérez")
    patient = _create_patient(client, tenant, owner["id"], "Mora")

    lines = _export_text_lines(db_session, tenant, patient["id"])

    assert "Datos del paciente" in lines
    assert "Nombre: Mora" in lines
    assert "Alergias: Penicilina" in lines
    assert "Datos del propietario" in lines
    assert "Nombre: Ana Pérez" in lines
    assert "Correo: maria@example.com" in lines


def test_export_pdf_excludes_owner_data_when_disabled(client, tenant, db_session):
    owner = _create_owner(client, tenant, full_name="Ana Pérez")
    patient = _create_patient(client, tenant, owner["id"], "Mora")

    lines = _export_text_lines(
        db_session,
        tenant,
        patient["id"],
        include_owner_data=False,
    )

    assert "Datos del propietario" not in lines
    assert "Nombre: Ana Pérez" not in lines


def test_export_pdf_filters_consultations_by_date_range(client, tenant, db_session):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(
        client,
        tenant,
        patient["id"],
        visit_date="2026-01-10T10:30:00Z",
        reason="Consulta antigua",
    )
    _create_consultation(
        client,
        tenant,
        patient["id"],
        visit_date="2026-04-10T10:30:00Z",
        reason="Consulta incluida",
    )

    lines = _export_text_lines(
        db_session,
        tenant,
        patient["id"],
        date_from="2026-04-01",
        date_to="2026-04-30",
    )

    assert "Motivo: Consulta incluida" in lines
    assert "Motivo: Consulta antigua" not in lines


def test_export_pdf_supports_summary_detail(client, tenant, db_session):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(client, tenant, patient["id"])

    lines = _export_text_lines(
        db_session,
        tenant,
        patient["id"],
        detail_level="summary",
    )

    assert "Diagnóstico presuntivo: Dermatitis alérgica" in lines
    assert "Resumen: Paciente estable" in lines
    assert "Anamnesis: Prurito hace 3 días" not in lines


def test_export_pdf_supports_full_detail(client, tenant, db_session):
    patient = _create_patient_for_tenant(client, tenant)
    consultation = _create_consultation(client, tenant, patient["id"])
    medication_response = client.post(
        f"/api/v1/consultations/{consultation['id']}/medications",
        headers=_headers(tenant),
        json={
            "medication_name": "Cefalexina",
            "dose_or_quantity": "250 mg",
            "instructions": "Cada 12 horas",
        },
    )
    assert medication_response.status_code == 201
    study_response = client.post(
        f"/api/v1/consultations/{consultation['id']}/study-requests",
        headers=_headers(tenant),
        json={
            "name": "Citología",
            "study_type": "laboratory",
            "notes": "Tomar muestra si no mejora",
        },
    )
    assert study_response.status_code == 201

    lines = _export_text_lines(
        db_session,
        tenant,
        patient["id"],
        detail_level="full",
    )

    assert "Anamnesis: Prurito hace 3 días" in lines
    assert "Examen clínico: Eritema leve" in lines
    assert "Medicamentos:" in lines
    assert "- Cefalexina · 250 mg · Cada 12 horas" in lines
    assert "Solicitudes de estudio:" in lines
    assert "- Citología · Laboratorio · Tomar muestra si no mejora" in lines


def test_export_pdf_does_not_include_cross_tenant_records(
    client,
    tenant,
    other_tenant,
    db_session,
):
    patient = _create_patient_for_tenant(client, tenant, "Luna")
    _create_consultation(client, tenant, patient["id"], reason="Consulta visible")
    foreign_patient = _create_patient_for_tenant(client, other_tenant, "Nina")
    _create_consultation(
        client,
        other_tenant,
        foreign_patient["id"],
        reason="Consulta oculta",
    )

    lines = _export_text_lines(db_session, tenant, patient["id"])

    assert "Motivo: Consulta visible" in lines
    assert "Motivo: Consulta oculta" not in lines
    assert "Paciente: Nina" not in lines


def test_export_pdf_invalid_date_range_returns_structured_error(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)

    response = client.post(
        f"/api/v1/patients/{patient['id']}/clinical-history/export-pdf",
        headers=_headers(tenant),
        json={"date_from": "2026-05-01", "date_to": "2026-01-01"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_date_range"


def test_export_pdf_patient_from_another_tenant_cannot_be_exported(
    client,
    tenant,
    other_tenant,
):
    foreign_patient = _create_patient_for_tenant(client, other_tenant, "Nina")

    response = client.post(
        f"/api/v1/patients/{foreign_patient['id']}/clinical-history/export-pdf",
        headers=_headers(tenant),
        json={},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "patient_not_found"


def test_export_pdf_can_include_all_record_types(client, tenant, db_session):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(client, tenant, patient["id"])
    _create_exam(client, tenant, patient["id"])
    _create_preventive_care(client, tenant, patient["id"])
    _create_file_reference(client, tenant, patient["id"])

    lines = _export_text_lines(db_session, tenant, patient["id"])

    assert "Examen - Hemograma" in lines
    assert "Vacuna - Rabia anual" in lines
    assert "Archivo - Radiografía lateral" in lines
    assert not any("signed" in line.lower() for line in lines)

import base64
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.consultation import Consultation
from app.models.patient import Patient
from app.schemas.patient import ClinicalHistoryPdfExportRequest
from app.services.clinical_history_pdf import ClinicalHistoryPdfService
from app.services.storage import get_storage_service


TEST_LOGO_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
TEST_PHOTO_PNG = TEST_LOGO_PNG


class FakeLogoStorageService:
    def __init__(
        self,
        *,
        logo_bytes: bytes = TEST_LOGO_PNG,
        should_fail: bool = False,
    ) -> None:
        self.bucket_name = "fallback-test-bucket"
        self.logo_bytes = logo_bytes
        self.should_fail = should_fail
        self.downloads: list[dict[str, str]] = []

    def download_object_bytes(self, *, bucket_name: str, object_path: str) -> bytes:
        self.downloads.append(
            {"bucket_name": bucket_name, "object_path": object_path}
        )
        if self.should_fail:
            raise RuntimeError("download failed")
        return self.logo_bytes


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
        "diagnostic_results": "Hemograma compatible con proceso infeccioso leve",
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


def _export_context(
    db_session: Session,
    tenant,
    patient_id: str,
    monkeypatch,
    storage_service=None,
    **options,
) -> dict:
    captured_context = {}

    def capture_render(self, context, *, options):
        captured_context.update(context)
        return b"%PDF-test"

    monkeypatch.setattr(
        ClinicalHistoryPdfService,
        "_render_pdf_from_template",
        capture_render,
    )
    ClinicalHistoryPdfService(
        db_session,
        storage_service=storage_service,
    ).export_patient_history_pdf(
        tenant.id,
        uuid.UUID(patient_id),
        ClinicalHistoryPdfExportRequest(**options),
    )
    return captured_context


def _render_html(
    db_session: Session,
    tenant,
    patient_id: str,
    monkeypatch,
    storage_service=None,
    **options,
) -> str:
    rendered = {}

    class FakeHTML:
        def __init__(self, *, string, base_url, url_fetcher):
            rendered["html"] = string

        def write_pdf(self):
            return b"%PDF-test"

    monkeypatch.setattr("app.services.clinical_history_pdf.HTML", FakeHTML)
    ClinicalHistoryPdfService(
        db_session,
        storage_service=storage_service,
    ).export_patient_history_pdf(
        tenant.id,
        uuid.UUID(patient_id),
        ClinicalHistoryPdfExportRequest(**options),
    )
    return rendered["html"]


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


def test_export_pdf_empty_payload_defaults_to_letter():
    options = ClinicalHistoryPdfExportRequest()

    assert options.page_size == "letter"


@pytest.mark.parametrize("page_size", ["letter", "a4", "legal"])
def test_export_pdf_supports_page_sizes(client, tenant, page_size):
    patient = _create_patient_for_tenant(client, tenant)

    response = client.post(
        f"/api/v1/patients/{patient['id']}/clinical-history/export-pdf",
        headers=_headers(tenant),
        json={"page_size": page_size},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


@pytest.mark.parametrize("page_size", ["letter", "a4", "legal"])
def test_template_context_preserves_page_size(
    client,
    tenant,
    db_session,
    monkeypatch,
    page_size,
):
    patient = _create_patient_for_tenant(client, tenant)

    context = _export_context(
        db_session,
        tenant,
        patient["id"],
        monkeypatch,
        page_size=page_size,
    )

    assert context["document"]["page_size"] == page_size


def test_export_pdf_rejects_invalid_page_size(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)

    response = client.post(
        f"/api/v1/patients/{patient['id']}/clinical-history/export-pdf",
        headers=_headers(tenant),
        json={"page_size": "tabloid"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_preview_pdf_success_uses_inline_disposition(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(client, tenant, patient["id"])

    response = client.post(
        f"/api/v1/patients/{patient['id']}/clinical-history/preview-pdf",
        headers=_headers(tenant),
        json={},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert "inline;" in response.headers["content-disposition"]
    assert "historia-clinica-luna-" in response.headers["content-disposition"]


def test_preview_pdf_passes_shared_export_options(
    client,
    tenant,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)
    captured_options = {}
    original_export = ClinicalHistoryPdfService.export_patient_history_pdf

    def capture_export(self, tenant_id, patient_id, options):
        captured_options.update(options.model_dump())
        return original_export(self, tenant_id, patient_id, options)

    monkeypatch.setattr(
        ClinicalHistoryPdfService,
        "export_patient_history_pdf",
        capture_export,
    )

    response = client.post(
        f"/api/v1/patients/{patient['id']}/clinical-history/preview-pdf",
        headers=_headers(tenant),
        json={
            "date_from": "2026-01-01",
            "date_to": "2026-12-31",
            "include_patient_data": False,
            "include_consultation_exam_data": False,
            "detail_level": "full",
            "page_size": "a4",
        },
    )

    assert response.status_code == 200
    assert captured_options["date_from"].isoformat() == "2026-01-01"
    assert captured_options["date_to"].isoformat() == "2026-12-31"
    assert captured_options["include_patient_data"] is False
    assert captured_options["include_consultation_exam_data"] is False
    assert captured_options["detail_level"] == "full"
    assert captured_options["page_size"] == "a4"


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


def test_export_pdf_excludes_patient_data_when_disabled(client, tenant, db_session):
    patient = _create_patient_for_tenant(client, tenant, "Mora")

    lines = _export_text_lines(
        db_session,
        tenant,
        patient["id"],
        include_patient_data=False,
    )

    assert "Datos del paciente" not in lines
    assert "Especie: Canine" not in lines
    assert "Alergias: Penicilina" not in lines


def test_export_pdf_includes_clinic_contact_and_report_metadata(
    client,
    tenant,
    db_session,
):
    tenant.display_name = "Clínica Vet Central"
    tenant.phone = "555-3000"
    tenant.email = "contacto@vetcentral.test"
    tenant.address = "Avenida Principal 123"
    db_session.add(tenant)
    db_session.commit()
    patient = _create_patient_for_tenant(client, tenant)

    lines = _export_text_lines(
        db_session,
        tenant,
        patient["id"],
        date_from="2026-01-01",
        date_to="2026-12-31",
        detail_level="full",
    )

    assert "Clínica: Clínica Vet Central" in lines
    assert "Teléfono de la clínica: 555-3000" in lines
    assert "Correo de la clínica: contacto@vetcentral.test" in lines
    assert "Dirección de la clínica: Avenida Principal 123" in lines
    assert "Rango: 2026-01-01 a 2026-12-31" in lines
    assert "Nivel de detalle: Historia completa" in lines


@pytest.mark.parametrize("endpoint", ["export-pdf", "preview-pdf"])
def test_pdf_continues_when_clinic_logo_storage_download_fails(
    client,
    tenant,
    db_session,
    endpoint,
):
    patient = _create_patient_for_tenant(client, tenant)
    tenant.logo_url = "gs://clinic-logo-bucket/tenants/tenant/logo.png"
    tenant.logo_object_path = "tenants/tenant/logo.png"
    db_session.add(tenant)
    db_session.commit()
    storage = FakeLogoStorageService(should_fail=True)
    client.app.dependency_overrides[get_storage_service] = lambda: storage

    response = client.post(
        f"/api/v1/patients/{patient['id']}/clinical-history/{endpoint}",
        headers=_headers(tenant),
        json={},
    )

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert storage.downloads == [
        {
            "bucket_name": "clinic-logo-bucket",
            "object_path": "tenants/tenant/logo.png",
        }
    ]


@pytest.mark.parametrize("endpoint", ["export-pdf", "preview-pdf"])
def test_pdf_loads_and_renders_clinic_logo_bytes(
    client,
    tenant,
    db_session,
    endpoint,
):
    patient = _create_patient_for_tenant(client, tenant)
    tenant.logo_url = "gs://clinic-logo-bucket/tenants/tenant/logo.png"
    tenant.logo_object_path = "tenants/tenant/logo.png"
    db_session.add(tenant)
    db_session.commit()
    storage = FakeLogoStorageService()
    client.app.dependency_overrides[get_storage_service] = lambda: storage

    response = client.post(
        f"/api/v1/patients/{patient['id']}/clinical-history/{endpoint}",
        headers=_headers(tenant),
        json={},
    )

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert storage.downloads == [
        {
            "bucket_name": "clinic-logo-bucket",
            "object_path": "tenants/tenant/logo.png",
        }
    ]


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


def test_template_context_sorts_consultations_chronologically(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(
        client,
        tenant,
        patient["id"],
        visit_date="2026-03-10T10:30:00Z",
        reason="Consulta reciente",
    )
    _create_consultation(
        client,
        tenant,
        patient["id"],
        visit_date="2026-01-10T10:30:00Z",
        reason="Consulta antigua",
    )

    context = _export_context(db_session, tenant, patient["id"], monkeypatch)

    assert [item["reason"] for item in context["consultations"]] == [
        "Consulta antigua",
        "Consulta reciente",
    ]


def test_template_context_sorts_consultations_with_same_date_by_id(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)
    visit_date = datetime(2026, 2, 10, 10, 30, tzinfo=timezone.utc)
    first_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    second_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    db_session.add_all(
        [
            Consultation(
                id=second_id,
                tenant_id=tenant.id,
                patient_id=uuid.UUID(patient["id"]),
                visit_date=visit_date,
                reason="Mismo día segundo id",
                status="draft",
            ),
            Consultation(
                id=first_id,
                tenant_id=tenant.id,
                patient_id=uuid.UUID(patient["id"]),
                visit_date=visit_date,
                reason="Mismo día primer id",
                status="draft",
            ),
        ]
    )
    db_session.commit()

    context = _export_context(db_session, tenant, patient["id"], monkeypatch)

    assert [item["reason"] for item in context["consultations"]] == [
        "Mismo día primer id",
        "Mismo día segundo id",
    ]


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
    assert (
        "Resultados del plan diagnóstico: Hemograma compatible con proceso infeccioso leve"
        in lines
    )
    assert lines.index(
        "Resultados del plan diagnóstico: Hemograma compatible con proceso infeccioso leve"
    ) < lines.index("Plan terapéutico: Tratamiento tópico")
    assert "Medicamentos:" in lines
    assert "- Cefalexina · 250 mg · Cada 12 horas" in lines
    assert "Solicitudes de estudio:" in lines
    assert "- Citología · Laboratorio · Tomar muestra si no mejora" in lines


def test_template_context_defaults_to_include_consultation_exam_data(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(
        client,
        tenant,
        patient["id"],
        temperature_c=38.7,
        current_weight_kg=6.7,
        heart_rate=150,
        respiratory_rate=30,
        mucous_membranes="Rosadas",
        hydration="Normal",
        physical_exam_findings="Examen clínico normal.",
    )

    context = _export_context(
        db_session,
        tenant,
        patient["id"],
        monkeypatch,
        detail_level="full",
    )

    exam_data = context["consultations"][0]["exam_data"]
    assert context["sections"]["include_consultation_exam_data"] is True
    assert exam_data["has_data"] is True
    assert exam_data["vitals"] == [
        {"label": "Temperatura", "value": "38,7 °C"},
        {"label": "Peso actual", "value": "6,7 kg"},
        {"label": "Frecuencia cardíaca", "value": "150 lpm"},
        {"label": "Frecuencia respiratoria", "value": "30 rpm"},
        {"label": "Mucosas", "value": "Rosadas"},
        {"label": "Hidratación", "value": "Normal"},
    ]
    assert exam_data["physical_exam_findings"] == "Examen clínico normal."


def test_template_context_excludes_consultation_exam_data_when_disabled(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(
        client,
        tenant,
        patient["id"],
        temperature_c=38.7,
        physical_exam_findings="No debe mostrarse.",
    )

    context = _export_context(
        db_session,
        tenant,
        patient["id"],
        monkeypatch,
        detail_level="full",
        include_consultation_exam_data=False,
    )

    assert context["sections"]["include_consultation_exam_data"] is False
    assert context["consultations"][0]["exam_data"] is None


def test_template_context_summary_consultation_exam_data_is_compact(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(
        client,
        tenant,
        patient["id"],
        temperature_c=38.7,
        current_weight_kg=6.7,
        heart_rate=150,
        respiratory_rate=30,
        mucous_membranes="Rosadas",
        hydration="Normal",
        physical_exam_findings="Hallazgo extenso para modo completo.",
    )

    context = _export_context(
        db_session,
        tenant,
        patient["id"],
        monkeypatch,
        detail_level="summary",
    )

    exam_data = context["consultations"][0]["exam_data"]
    assert exam_data["has_data"] is True
    assert exam_data["vitals"] == [
        {"label": "Temperatura", "value": "38,7 °C"},
        {"label": "Peso actual", "value": "6,7 kg"},
        {"label": "Frecuencia cardíaca", "value": "150 lpm"},
        {"label": "Frecuencia respiratoria", "value": "30 rpm"},
        {"label": "Mucosas", "value": "Rosadas"},
        {"label": "Hidratación", "value": "Normal"},
    ]
    assert exam_data["physical_exam_findings"] == (
        "Hallazgo extenso para modo completo."
    )


def test_template_context_consultation_exam_data_supports_findings_only(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(
        client,
        tenant,
        patient["id"],
        temperature_c=None,
        current_weight_kg=None,
        heart_rate=None,
        respiratory_rate=None,
        mucous_membranes="",
        hydration="",
        physical_exam_findings="Mordidas superficiales en MPD.\nOreja derecha sensible.",
    )

    context = _export_context(
        db_session,
        tenant,
        patient["id"],
        monkeypatch,
        detail_level="summary",
    )
    exam_data = context["consultations"][0]["exam_data"]

    assert exam_data["has_data"] is True
    assert exam_data["vitals"] == []
    assert exam_data["physical_exam_findings"] == (
        "Mordidas superficiales en MPD.\nOreja derecha sensible."
    )


def test_template_context_consultation_exam_data_supports_mucosas_hydration_only(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(
        client,
        tenant,
        patient["id"],
        temperature_c=None,
        current_weight_kg=None,
        heart_rate=None,
        respiratory_rate=None,
        mucous_membranes="Pálidas",
        hydration="Moderada",
        physical_exam_findings="",
    )

    context = _export_context(
        db_session,
        tenant,
        patient["id"],
        monkeypatch,
        detail_level="summary",
    )
    exam_data = context["consultations"][0]["exam_data"]

    assert exam_data["has_data"] is True
    assert exam_data["vitals"] == [
        {"label": "Mucosas", "value": "Pálidas"},
        {"label": "Hidratación", "value": "Moderada"},
    ]
    assert exam_data["physical_exam_findings"] is None


def test_template_context_full_consultation_exam_data_excludes_empty_fields(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(
        client,
        tenant,
        patient["id"],
        temperature_c=39.25,
        current_weight_kg=None,
        heart_rate=None,
        respiratory_rate=28,
        mucous_membranes="",
        hydration="Leve deshidratación",
        physical_exam_findings="Dolor abdominal leve.",
    )

    context = _export_context(
        db_session,
        tenant,
        patient["id"],
        monkeypatch,
        detail_level="full",
    )
    exam_data = context["consultations"][0]["exam_data"]

    assert exam_data["vitals"] == [
        {"label": "Temperatura", "value": "39,25 °C"},
        {"label": "Frecuencia respiratoria", "value": "28 rpm"},
        {"label": "Hidratación", "value": "Leve deshidratación"},
    ]
    assert exam_data["physical_exam_findings"] == "Dolor abdominal leve."


def test_template_context_omits_empty_consultation_exam_block(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(client, tenant, patient["id"])

    context = _export_context(
        db_session,
        tenant,
        patient["id"],
        monkeypatch,
        detail_level="full",
    )

    assert context["consultations"][0]["exam_data"]["has_data"] is False
    assert context["consultations"][0]["exam_data"]["vitals"] == []
    assert context["consultations"][0]["exam_data"]["physical_exam_findings"] is None


def test_export_pdf_consultation_exam_data_is_independent_from_diagnostic_exams(
    client,
    tenant,
    db_session,
):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(
        client,
        tenant,
        patient["id"],
        temperature_c=38.7,
        heart_rate=150,
    )
    _create_exam(client, tenant, patient["id"])

    lines = _export_text_lines(
        db_session,
        tenant,
        patient["id"],
        include_exams=False,
    )

    assert "Signos vitales y examen físico" in lines
    assert "Temperatura: 38,7 °C" in lines
    assert "Frecuencia cardíaca: 150 lpm" in lines
    assert "Exámenes" not in lines
    assert "Examen - Hemograma" not in lines


def test_export_pdf_includes_all_consultation_exam_data_when_enabled(
    client,
    tenant,
    db_session,
):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(
        client,
        tenant,
        patient["id"],
        temperature_c=38.7,
        current_weight_kg=6.7,
        heart_rate=150,
        respiratory_rate=30,
        mucous_membranes="Rosadas",
        hydration="Normal",
        physical_exam_findings="Heridas superficiales en ingle.",
    )

    lines = _export_text_lines(db_session, tenant, patient["id"])

    assert "Signos vitales y examen físico" in lines
    assert "Temperatura: 38,7 °C" in lines
    assert "Peso actual: 6,7 kg" in lines
    assert "Frecuencia cardíaca: 150 lpm" in lines
    assert "Frecuencia respiratoria: 30 rpm" in lines
    assert "Mucosas: Rosadas" in lines
    assert "Hidratación: Normal" in lines
    assert "Hallazgos del examen físico: Heridas superficiales en ingle." in lines


def test_export_pdf_excludes_all_consultation_exam_data_when_disabled(
    client,
    tenant,
    db_session,
):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(
        client,
        tenant,
        patient["id"],
        temperature_c=38.7,
        current_weight_kg=6.7,
        heart_rate=150,
        respiratory_rate=30,
        mucous_membranes="Rosadas",
        hydration="Normal",
        physical_exam_findings="Heridas superficiales en ingle.",
    )

    lines = _export_text_lines(
        db_session,
        tenant,
        patient["id"],
        include_consultation_exam_data=False,
    )

    assert "Signos vitales y examen físico" not in lines
    assert "Temperatura: 38,7 °C" not in lines
    assert "Peso actual: 6,7 kg" not in lines
    assert "Frecuencia cardíaca: 150 lpm" not in lines
    assert "Frecuencia respiratoria: 30 rpm" not in lines
    assert "Mucosas: Rosadas" not in lines
    assert "Hidratación: Normal" not in lines
    assert "Hallazgos del examen físico: Heridas superficiales en ingle." not in lines


def test_export_pdf_excludes_consultation_exam_data_without_consultations(
    client,
    tenant,
    db_session,
):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(
        client,
        tenant,
        patient["id"],
        temperature_c=38.7,
        physical_exam_findings="No debe aparecer.",
    )

    lines = _export_text_lines(
        db_session,
        tenant,
        patient["id"],
        include_consultations=False,
    )

    assert "Consultas" not in lines
    assert "Signos vitales y examen físico" not in lines
    assert "Temperatura: 38,7 °C" not in lines
    assert "Hallazgos del examen físico: No debe aparecer." not in lines


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


def test_preview_pdf_patient_from_another_tenant_cannot_be_exported(
    client,
    tenant,
    other_tenant,
):
    foreign_patient = _create_patient_for_tenant(client, other_tenant, "Nina")

    response = client.post(
        f"/api/v1/patients/{foreign_patient['id']}/clinical-history/preview-pdf",
        headers=_headers(tenant),
        json={},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "patient_not_found"


def test_preview_pdf_invalid_date_range_returns_same_structured_error(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)

    response = client.post(
        f"/api/v1/patients/{patient['id']}/clinical-history/preview-pdf",
        headers=_headers(tenant),
        json={"date_from": "2026-05-01", "date_to": "2026-01-01"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_date_range"


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


def test_preview_pdf_can_include_all_record_types(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(client, tenant, patient["id"])
    _create_exam(client, tenant, patient["id"])
    _create_preventive_care(client, tenant, patient["id"])
    _create_file_reference(client, tenant, patient["id"])

    response = client.post(
        f"/api/v1/patients/{patient['id']}/clinical-history/preview-pdf",
        headers=_headers(tenant),
        json={"detail_level": "full"},
    )

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert "inline;" in response.headers["content-disposition"]


def test_preview_pdf_renders_consultation_exam_data_block(client, tenant):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(
        client,
        tenant,
        patient["id"],
        temperature_c=38.7,
        current_weight_kg=6.7,
        heart_rate=150,
        respiratory_rate=30,
        mucous_membranes="Rosadas",
        hydration="Normal",
        physical_exam_findings="Examen clínico normal.",
    )

    response = client.post(
        f"/api/v1/patients/{patient['id']}/clinical-history/preview-pdf",
        headers=_headers(tenant),
        json={"detail_level": "full"},
    )

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


def test_template_context_contains_all_sections_and_structured_records(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    tenant.display_name = "Clínica Vet Central"
    db_session.add(tenant)
    db_session.commit()
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(client, tenant, patient["id"])
    _create_exam(client, tenant, patient["id"])
    _create_preventive_care(client, tenant, patient["id"])
    _create_file_reference(client, tenant, patient["id"])

    context = _export_context(
        db_session,
        tenant,
        patient["id"],
        monkeypatch,
        detail_level="full",
    )

    assert context["document"]["title"] == "Historia clínica veterinaria"
    assert context["clinic"]["name"] == "Clínica Vet Central"
    assert context["patient"]["name"] == "Luna"
    assert context["owner"]["full_name"] == "Luna Owner"
    assert context["consultations"][0]["reason"] == "Irritación de piel"
    assert context["exams"][0]["exam_type"] == "Hemograma"
    assert context["preventive_care"][0]["care_type"] == "Vacuna"
    assert context["file_references"][0]["name"] == "Radiografía lateral"
    assert all(context["sections"].values())


def test_template_context_empty_sections_and_summary_are_concise(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)

    context = _export_context(
        db_session,
        tenant,
        patient["id"],
        monkeypatch,
        detail_level="summary",
    )

    assert context["document"]["detail_level"] == "Resumen"
    assert context["consultations"] == []
    assert context["exams"] == []
    assert context["preventive_care"] == []
    assert context["file_references"] == []


def test_template_omits_empty_fields_and_keeps_zero_values(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    owner = _create_owner(client, tenant, email=None, address=None)
    response = client.post(
        "/api/v1/patients",
        headers=_headers(tenant),
        json={
            "owner_id": owner["id"],
            "name": "Cero",
            "species": "Feline",
            "breed": "",
            "sex": "",
            "allergies": "   ",
            "chronic_conditions": "",
            "weight_kg": 0,
        },
    )
    assert response.status_code == 201
    patient = response.json()["data"]
    _create_consultation(
        client,
        tenant,
        patient["id"],
        anamnesis="",
        clinical_exam="",
        presumptive_diagnosis="",
        diagnostic_plan="",
        diagnostic_results="",
        therapeutic_plan="",
        final_diagnosis="",
        indications="",
        consultation_summary="",
        temperature_c=0,
        current_weight_kg=0,
        heart_rate=0,
        respiratory_rate=0,
        mucous_membranes="",
        hydration="",
        physical_exam_findings="",
    )

    html = _render_html(
        db_session,
        tenant,
        patient["id"],
        monkeypatch,
        detail_level="full",
    )

    assert ">Raza<" not in html
    assert ">Sexo<" not in html
    assert ">Alergias<" not in html
    assert ">Condiciones crónicas<" not in html
    assert "0.00 kg" in html
    assert "0 °C" in html
    assert "0 kg" in html
    assert "0 lpm" in html
    assert "0 rpm" in html


def test_template_context_full_detail_includes_only_non_empty_clinical_fields(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(
        client,
        tenant,
        patient["id"],
        symptoms=None,
        indications="Control en 48 horas",
    )

    context = _export_context(
        db_session,
        tenant,
        patient["id"],
        monkeypatch,
        detail_level="full",
    )
    consultation = context["consultations"][0]

    assert consultation["indications"] == "Control en 48 horas"
    assert {field["label"] for field in consultation["clinical_fields"]} >= {
        "Anamnesis",
        "Examen clínico",
        "Plan diagnóstico",
        "Resultados del plan diagnóstico",
        "Plan terapéutico",
    }
    assert "Síntomas" not in {
        field["label"] for field in consultation["clinical_fields"]
    }


def test_template_notes_section_appears_once_before_legal_notice(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(client, tenant, patient["id"])

    html = _render_html(db_session, tenant, patient["id"], monkeypatch)

    assert html.count("<h2 class=\"manual-notes-title\">Notas</h2>") == 1
    assert html.index("<h2 class=\"manual-notes-title\">Notas</h2>") < html.index(
        "Documento generado automáticamente por VetFlow."
    )


def test_template_omits_patient_photo_container_without_photo(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)

    html = _render_html(db_session, tenant, patient["id"], monkeypatch)

    assert "<img class=\"patient-photo\"" not in html
    assert "Fotografía de" not in html


def test_template_context_logo_is_a_single_size_limited_data_uri(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)
    tenant.logo_url = "gs://clinic-logo-bucket/tenants/tenant/logo.png"
    tenant.logo_object_path = "tenants/tenant/logo.png"
    db_session.add(tenant)
    db_session.commit()
    storage = FakeLogoStorageService()

    context = _export_context(
        db_session,
        tenant,
        patient["id"],
        monkeypatch,
        storage_service=storage,
    )

    assert context["clinic"]["logo_data_uri"].startswith(
        "data:image/png;base64,"
    )
    assert len(storage.downloads) == 1


def test_template_context_includes_patient_photo_when_available(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)
    db_patient = db_session.get(Patient, uuid.UUID(patient["id"]))
    assert db_patient is not None
    db_patient.photo_bucket_name = "patient-photo-bucket"
    db_patient.photo_object_path = (
        f"tenants/{tenant.id}/patients/{patient['id']}/profile-photo/luna.png"
    )
    db_patient.photo_content_type = "image/png"
    db_session.add(db_patient)
    db_session.commit()
    storage = FakeLogoStorageService(logo_bytes=TEST_PHOTO_PNG)

    context = _export_context(
        db_session,
        tenant,
        patient["id"],
        monkeypatch,
        storage_service=storage,
    )

    assert context["patient"]["photo_data_uri"].startswith("data:image/png;base64,")
    assert storage.downloads == [
        {
            "bucket_name": "patient-photo-bucket",
            "object_path": (
                f"tenants/{tenant.id}/patients/{patient['id']}/profile-photo/luna.png"
            ),
        }
    ]


def test_template_context_omits_patient_photo_when_absent(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)
    storage = FakeLogoStorageService()

    context = _export_context(
        db_session,
        tenant,
        patient["id"],
        monkeypatch,
        storage_service=storage,
    )

    assert context["patient"]["photo_data_uri"] is None
    assert storage.downloads == []


def test_template_context_omits_unavailable_patient_photo_without_blocking(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)
    db_patient = db_session.get(Patient, uuid.UUID(patient["id"]))
    assert db_patient is not None
    db_patient.photo_bucket_name = "patient-photo-bucket"
    db_patient.photo_object_path = (
        f"tenants/{tenant.id}/patients/{patient['id']}/profile-photo/luna.png"
    )
    db_patient.photo_content_type = "image/png"
    db_session.add(db_patient)
    db_session.commit()
    storage = FakeLogoStorageService(should_fail=True)

    context = _export_context(
        db_session,
        tenant,
        patient["id"],
        monkeypatch,
        storage_service=storage,
    )

    assert context["patient"]["photo_data_uri"] is None
    assert storage.downloads == [
        {
            "bucket_name": "patient-photo-bucket",
            "object_path": (
                f"tenants/{tenant.id}/patients/{patient['id']}/profile-photo/luna.png"
            ),
        }
    ]


def test_template_context_rejects_patient_photo_outside_patient_scope(
    client,
    tenant,
    other_tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)
    db_patient = db_session.get(Patient, uuid.UUID(patient["id"]))
    assert db_patient is not None
    db_patient.photo_bucket_name = "patient-photo-bucket"
    db_patient.photo_object_path = (
        f"tenants/{other_tenant.id}/patients/{patient['id']}/profile-photo/luna.png"
    )
    db_patient.photo_content_type = "image/png"
    db_session.add(db_patient)
    db_session.commit()
    storage = FakeLogoStorageService()

    context = _export_context(
        db_session,
        tenant,
        patient["id"],
        monkeypatch,
        storage_service=storage,
    )

    assert context["patient"]["photo_data_uri"] is None
    assert storage.downloads == []


def test_template_context_skips_oversized_logo(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)
    tenant.logo_object_path = "tenants/tenant/logo.jpg"
    db_session.add(tenant)
    db_session.commit()
    storage = FakeLogoStorageService(logo_bytes=b"x" * (1024 * 1024 + 1))

    context = _export_context(
        db_session,
        tenant,
        patient["id"],
        monkeypatch,
        storage_service=storage,
    )

    assert context["clinic"]["logo_data_uri"] is None
    assert len(storage.downloads) == 1


def test_export_pdf_handles_long_clinical_text(
    client,
    tenant,
):
    patient = _create_patient_for_tenant(client, tenant)
    long_text = "Línea clínica extensa con seguimiento.\n" * 120
    _create_consultation(
        client,
        tenant,
        patient["id"],
        final_diagnosis=long_text,
        indications=long_text,
    )
    _create_exam(client, tenant, patient["id"], observations=long_text)

    response = client.post(
        f"/api/v1/patients/{patient['id']}/clinical-history/export-pdf",
        headers=_headers(tenant),
        json={"detail_level": "full"},
    )

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 0


def test_template_rendering_autoescapes_clinical_html(
    client,
    tenant,
    db_session,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)
    _create_consultation(
        client,
        tenant,
        patient["id"],
        indications='<script>alert("clinical")</script>',
    )
    rendered = {}

    class FakeHTML:
        def __init__(self, *, string, base_url, url_fetcher):
            rendered["html"] = string
            rendered["base_url"] = base_url
            rendered["url_fetcher"] = url_fetcher

        def write_pdf(self):
            return b"%PDF-test"

    monkeypatch.setattr("app.services.clinical_history_pdf.HTML", FakeHTML)
    ClinicalHistoryPdfService(db_session).export_patient_history_pdf(
        tenant.id,
        uuid.UUID(patient["id"]),
        ClinicalHistoryPdfExportRequest(),
    )

    assert "<script>alert" not in rendered["html"]
    assert "&lt;script&gt;alert" in rendered["html"]
    assert rendered["base_url"].endswith("app/templates")
    with pytest.raises(ValueError, match="External PDF assets"):
        rendered["url_fetcher"].fetch("https://example.com/asset.png")


def test_render_failure_returns_structured_pdf_export_error(
    client,
    tenant,
    monkeypatch,
):
    patient = _create_patient_for_tenant(client, tenant)

    def fail_render(self, context, *, options):
        raise RuntimeError("render unavailable")

    monkeypatch.setattr(
        ClinicalHistoryPdfService,
        "_render_pdf_from_template",
        fail_render,
    )
    response = client.post(
        f"/api/v1/patients/{patient['id']}/clinical-history/export-pdf",
        headers=_headers(tenant),
        json={},
    )

    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "pdf_export_failed",
        "message": "Clinical history PDF export failed",
    }

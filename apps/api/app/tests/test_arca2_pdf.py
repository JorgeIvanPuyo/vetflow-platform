import base64
import hashlib
import json
import socket
from copy import deepcopy
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest

from app.services.arca_pdf import (
    QR_ASSET_URL, QR_BASE_URL, _controlled_qr_fetcher, build_authorized_qr_url,
    render_authorized_html, render_authorized_pdf,
)


@pytest.fixture(autouse=True)
def no_pdf_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("PDF tests must not open a network connection")
    monkeypatch.setattr(socket.socket, "connect", blocked)


def authorized_example(*, long_description=False):
    """Synthetic frozen business data; never read the local customer database."""
    lines = [
        {"description": "Consulta clínica sintética documentada", "quantity": "1", "unit_price": "12500.10", "total": "12500.10"},
        {"description": "Tratamiento y seguimiento sintéticos", "quantity": "2", "unit_price": "2500.20", "total": "5000.40"},
        {"description": "Servicio complementario sintético", "quantity": "1", "unit_price": "500.05", "total": "500.05"},
    ]
    if long_description:
        lines[1]["description"] = ("Descripción extensa de un servicio sintético, con indicaciones revisadas y referencia a la porción efectivamente documentada. " * 15).strip()
    snapshot = {
        "environment": "homologation",
        "issuer": {"cuit": "20123456786", "legal_name": "Profesional veterinario de prueba", "tax_condition": "Monotributo", "fiscal_address": "Domicilio sintético 100, Ciudad de Prueba", "gross_income_registration": "Inscripción sintética", "activity_start_date": "2020-01-01"},
        "receiver": {"document_type": 99, "document_number": 0, "iva_condition_id": 5, "name": "Receptor sintético confirmado", "address": "Domicilio de prueba 200", "consumer_final": True},
        "point_of_sale": 7, "document_type": 15, "concept": 2,
        "voucher_date": "2026-10-20", "service_from": "2026-10-19", "service_to": "2026-10-20", "payment_due": "2026-10-20",
        "currency": "PES", "exchange_rate": "1", "total": "18000.55", "net_amount": "18000.55", "lines": lines, "number": 42,
    }
    authorization = {"cae": "70417054367476", "cae_expiry": "2026-10-30", "number": 42}
    return snapshot, authorization


def decode_qr(url):
    encoded = parse_qs(urlparse(url).query)["p"][0]
    return json.loads(base64.b64decode(encoded, validate=True), parse_float=Decimal)


@pytest.mark.parametrize("long_description", [False, True])
def test_real_pdf_from_authorized_synthetic_snapshot_is_nonempty(long_description, monkeypatch, caplog):
    from weasyprint.svg import SVG

    drawn_qr_paths = []
    original_draw_node = SVG.draw_node

    def record_real_qr_path(svg, node, *args, **kwargs):
        result = original_draw_node(svg, node, *args, **kwargs)
        if svg.url == QR_ASSET_URL and node.tag == "path":
            drawn_qr_paths.append(node.get("d", ""))
        return result

    monkeypatch.setattr(SVG, "draw_node", record_real_qr_path)
    snapshot, authorization = authorized_example(long_description=long_description)
    artifact = render_authorized_pdf(snapshot, authorization, "homologation")
    assert artifact.pdf_bytes.startswith(b"%PDF-")
    assert len(artifact.pdf_bytes) > 4000
    assert artifact.sha256 == hashlib.sha256(artifact.pdf_bytes).hexdigest()
    assert decode_qr(artifact.qr_url)["importe"] == Decimal("18000.55")
    # Verify the actual renderer drew the QR's nonempty vector path into its
    # PDF stream. Valid PDF headers alone also pass when an image was dropped.
    assert len(drawn_qr_paths) == 1
    assert len(drawn_qr_paths[0]) > 1000
    assert "Failed to load image" not in caplog.text
    assert "Failed to render SVG" not in caplog.text


def test_qr_payload_uses_official_url_and_exact_numeric_types():
    snapshot, authorization = authorized_example()
    snapshot["total"] = "9999999999999.99"
    payload_url = build_authorized_qr_url(snapshot, authorization, "homologation")
    assert payload_url.startswith(QR_BASE_URL + "?p=")
    payload = decode_qr(payload_url)
    assert payload == {
        "ver": 1, "fecha": "2026-10-20", "cuit": 20123456786, "ptoVta": 7,
        "tipoCmp": 15, "nroCmp": 42, "importe": Decimal("9999999999999.99"),
        "moneda": "PES", "ctz": Decimal("1.000000"), "tipoDocRec": 99,
        "nroDocRec": 0, "tipoCodAut": "E", "codAut": 70417054367476,
    }
    for key in ("ver", "cuit", "ptoVta", "tipoCmp", "nroCmp", "tipoDocRec", "nroDocRec", "codAut"):
        assert type(payload[key]) is int
    assert isinstance(payload["importe"], Decimal)
    assert isinstance(payload["ctz"], Decimal)


def test_pdf_html_keeps_only_documented_portion_and_frozen_identity():
    snapshot, authorization = authorized_example()
    snapshot["sale"] = {"total_ars": "999999.00", "lines": [{"description": "NO IMPRIMIR LÍNEA AJENA"}]}
    html, _, _ = render_authorized_html(snapshot, authorization, "homologation")
    assert "18000.55" in html
    assert "999999.00" not in html and "NO IMPRIMIR" not in html
    assert "Profesional veterinario de prueba" in html
    assert "HOMOLOGACIÓN — SIN VALIDEZ FISCAL" in html
    assert "00007-00000042" in html
    assert "70417054367476" in html and "2026-10-30" in html
    assert "Consumidor final confirmado" in html
    assert "Consulta clínica sintética documentada" in html


def test_pdf_content_is_escaped_and_asset_fetcher_rejects_uncontrolled_urls():
    snapshot, authorization = authorized_example()
    snapshot["lines"][0]["description"] = '<img src="file:///etc/passwd"> <script>alert(1)</script>'
    html, _, qr_data_uri = render_authorized_html(snapshot, authorization, "homologation")
    assert "&lt;img" in html and "&lt;script&gt;" in html
    assert '<img src="file:' not in html and "<script>" not in html
    fetcher = _controlled_qr_fetcher(qr_data_uri)
    assert callable(fetcher)
    resource = fetcher(QR_ASSET_URL)
    try:
        assert resource.content_type == "image/svg+xml"
        assert resource.read() == base64.b64decode(qr_data_uri.split(",", 1)[1], validate=True)
    finally:
        resource.close()
    for url in ("file:///etc/passwd", "http://127.0.0.1/", "https://example.com/a.png", "data:image/svg+xml;base64,AAAA"):
        with pytest.raises(ValueError, match="QR generado"):
            fetcher(url)


def test_missing_or_corrupt_qr_image_cannot_produce_an_accepted_pdf(monkeypatch, caplog):
    from app.services import arca_pdf

    snapshot, authorization = authorized_example()
    invalid_image = "data:image/svg+xml;base64," + base64.b64encode(b"not-an-svg").decode("ascii")
    monkeypatch.setattr(arca_pdf, "_qr_svg_data_uri", lambda _url: invalid_image)
    with pytest.raises(ValueError, match="QR obligatorio"):
        render_authorized_pdf(snapshot, authorization, "homologation")
    assert "data:image/svg" not in caplog.text


def test_qr_drawing_failure_is_fatal_instead_of_a_silent_blank_image(monkeypatch):
    from weasyprint.svg import SVG

    def broken_draw(*args, **kwargs):
        raise RuntimeError("Synthetic renderer failure")

    monkeypatch.setattr(SVG, "draw", broken_draw)
    snapshot, authorization = authorized_example()
    with pytest.raises(ValueError, match="dibujar el QR obligatorio"):
        render_authorized_pdf(snapshot, authorization, "homologation")


@pytest.mark.parametrize("mutate", [
    lambda snapshot, auth: auth.update(cae=None),
    lambda snapshot, auth: auth.update(cae_expiry="2026-10-19"),
    lambda snapshot, auth: snapshot["issuer"].update(cuit="20123456789"),
    lambda snapshot, auth: auth.update(number=43),
    lambda snapshot, auth: snapshot.update(number=None),
    lambda snapshot, auth: snapshot.update(currency="DOL"),
    lambda snapshot, auth: snapshot.update(exchange_rate="1.01"),
    lambda snapshot, auth: snapshot.update(document_type=1),
    lambda snapshot, auth: snapshot["lines"][0].update(total="12500.11"),
    lambda snapshot, auth: snapshot.update(total="18000.56", net_amount="18000.56"),
    lambda snapshot, auth: snapshot.update(net_amount="18000.50"),
    lambda snapshot, auth: snapshot.update(lines=[]),
])
def test_pdf_refuses_incomplete_authorization_and_inconsistent_snapshot(mutate):
    snapshot, authorization = authorized_example()
    mutate(snapshot, authorization)
    with pytest.raises(ValueError):
        render_authorized_pdf(snapshot, authorization, "homologation")


def test_regeneration_keeps_number_cae_qr_and_does_not_mutate_frozen_business_data():
    snapshot, authorization = authorized_example()
    original_snapshot, original_authorization = deepcopy(snapshot), deepcopy(authorization)
    first = render_authorized_pdf(snapshot, authorization, "homologation")
    second = render_authorized_pdf(snapshot, authorization, "homologation")
    assert first.qr_url == second.qr_url
    assert snapshot == original_snapshot and authorization == original_authorization
    with pytest.raises(ValueError, match="ambiente"):
        render_authorized_pdf(snapshot, authorization, "production")


def test_authorization_survives_storage_failure_and_regeneration_never_requests_another_cae(db_session):
    from sqlalchemy import func, select

    from app.models.sale_fiscal import SaleFiscalDocument
    from app.services.arca_emission import ArcaEmissionService
    from app.tests.arca2_emission_support import (
        NOW, SyntheticEmissionRuntime, SyntheticEmissionStorage, seed_emission_case,
    )

    case = seed_emission_case(db_session)
    runtime = SyntheticEmissionRuntime()
    storage = SyntheticEmissionStorage(fail_upload=True)
    try:
        service = ArcaEmissionService(db_session, runtime=runtime, storage=storage, clock=lambda: NOW)
        prepared = service.prepare(case.context, case.sale_id, case.create, "pdf-storage-failure-synthetic-intent")
        issued = service.issue(case.context, case.sale_id, prepared.id)
        assert issued.status == "authorized"
        assert issued.file_status == "failed"
        assert issued.document_id is not None and issued.cae and issued.number
        assert runtime.transport.authorization_calls == 1
        assert len(runtime.transport.records) == 1
        assert len(storage.uploads) == 1 and storage.objects == {}
        original_identity = (issued.number, issued.cae, issued.cae_expiry, issued.document_id)
        original_snapshot = deepcopy(issued.business_snapshot)
        auth_calls_before_regeneration = list(runtime.ticket_calls)

        # Recreate the orchestration service with only persisted state and the
        # same storage provider. No browser session or surviving task is needed.
        storage.fail_upload = False
        db_session.expire_all()
        restarted = ArcaEmissionService(db_session, runtime=runtime, storage=storage, clock=lambda: NOW)
        ready = restarted.regenerate(case.context, case.sale_id, prepared.id)
        assert ready.status == "authorized" and ready.file_status == "ready"
        assert (ready.number, ready.cae, ready.cae_expiry, ready.document_id) == original_identity
        assert ready.business_snapshot == original_snapshot
        assert len(ready.file_versions) == 1
        assert len(storage.objects) == 1
        content = next(iter(storage.objects.values()))
        assert content.startswith(b"%PDF-") and len(content) > 4000
        assert ready.file_versions[0].sha256 == hashlib.sha256(content).hexdigest()

        versioned = restarted.regenerate(case.context, case.sale_id, prepared.id)
        assert len(versioned.file_versions) == 2 and len(storage.objects) == 2
        assert (versioned.number, versioned.cae, versioned.cae_expiry, versioned.document_id) == original_identity
        assert runtime.transport.authorization_calls == 1
        assert len(runtime.transport.records) == 1
        assert runtime.ticket_calls == auth_calls_before_regeneration
        document_count = db_session.scalar(select(func.count()).select_from(SaleFiscalDocument).where(
            SaleFiscalDocument.tenant_id == case.tenant_id,
            SaleFiscalDocument.sale_id == case.sale_id,
            SaleFiscalDocument.source == "arca",
        ))
        assert document_count == 1
    finally:
        runtime.close()


def test_authorized_file_versions_and_attempts_cannot_be_rewritten_or_deleted(db_session):
    from sqlalchemy import func, select
    from app.core.errors import AppError
    from app.models.arca_emission import ArcaDocumentFile, ArcaEmissionAttempt
    from app.services.arca_emission import ArcaEmissionService
    from app.tests.arca2_emission_support import NOW, SyntheticEmissionRuntime, SyntheticEmissionStorage, seed_emission_case

    case = seed_emission_case(db_session)
    runtime = SyntheticEmissionRuntime()
    try:
        service = ArcaEmissionService(db_session, runtime=runtime, storage=SyntheticEmissionStorage(), clock=lambda: NOW)
        prepared = service.prepare(case.context, case.sale_id, case.create, "immutable-file-history")
        issued = service.issue(case.context, case.sale_id, prepared.id)
        assert issued.status == "authorized" and issued.file_status == "ready"
        descriptor = db_session.scalar(select(ArcaDocumentFile).where(ArcaDocumentFile.tenant_id == case.tenant_id, ArcaDocumentFile.emission_id == prepared.id))
        attempt = db_session.scalar(select(ArcaEmissionAttempt).where(ArcaEmissionAttempt.tenant_id == case.tenant_id, ArcaEmissionAttempt.emission_id == prepared.id).order_by(ArcaEmissionAttempt.created_at, ArcaEmissionAttempt.id))
        identities = [(ArcaDocumentFile, descriptor.id, "storage_key", "rewritten/path.pdf"), (ArcaEmissionAttempt, attempt.id, "outcome", "rewritten")]
        attempt_count = db_session.scalar(select(func.count()).select_from(ArcaEmissionAttempt).where(ArcaEmissionAttempt.tenant_id == case.tenant_id))
        for model, record_id, field, value in identities:
            record = db_session.scalar(select(model).where(model.tenant_id == case.tenant_id, model.id == record_id))
            setattr(record, field, value)
            with pytest.raises(AppError) as update_error:
                db_session.flush()
            assert update_error.value.code == "arca_audit_immutable"
            db_session.rollback()
            record = db_session.scalar(select(model).where(model.tenant_id == case.tenant_id, model.id == record_id))
            db_session.delete(record)
            with pytest.raises(AppError) as delete_error:
                db_session.flush()
            assert delete_error.value.code == "arca_audit_required"
            db_session.rollback()
        assert len(service.list(case.context, case.sale_id)["operations"][0]["file_versions"]) == 1
        assert db_session.scalar(select(func.count()).select_from(ArcaEmissionAttempt).where(ArcaEmissionAttempt.tenant_id == case.tenant_id)) == attempt_count
        assert runtime.transport.authorization_calls == 1
    finally:
        runtime.close()

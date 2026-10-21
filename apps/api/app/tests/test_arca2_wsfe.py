"""Real SOAP serialization/parsing behind a strictly in-process remote ledger."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import httpx
import pytest
from pydantic import ValidationError

from app.core.errors import AppError
from app.schemas.arca_emission import FiscalBusinessPayload, FiscalReceiverDetails
from app.services.arca_wsfe import (
    ArcaWsfeClient, MAX_RESPONSE_BYTES, PARAMETER_METHODS, SOAP_NS, WSFE_NS, WSFE_ENDPOINTS, business_fingerprint,
)
from app.tests.arca2_support import ControlledArcaTransport, synthetic_payload, synthetic_ticket


NOW = datetime(2026, 10, 20, 12, tzinfo=UTC)
CUIT = "20123456786"


@pytest.fixture(autouse=True)
def no_uncontrolled_network(monkeypatch):
    def reject_network(*_args, **_kwargs):
        raise AssertionError("WSFE unit tests must inject an in-process transport")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", reject_network)


def _client(transport, *, clock=None):
    return ArcaWsfeClient("homologation", transport=transport, clock=clock or (lambda: NOW))


def _mutate(field, value=None, *, remove=False, method="FECompConsultar"):
    def mutate(operation, xml):
        if operation != method:
            return xml
        root = ET.fromstring(xml)
        matches = root.findall(f".//{{{WSFE_NS}}}{field}")
        assert len(matches) == 1
        if remove:
            for parent in root.iter():
                if matches[0] in list(parent):
                    parent.remove(matches[0])
        else:
            matches[0].text = str(value)
        return ET.tostring(root, encoding="utf-8")
    return mutate


def test_soap_authorizes_one_exact_c_voucher_and_escapes_auth():
    transport = ControlledArcaTransport()
    ticket = replace(synthetic_ticket(now=NOW), token="synthetic<&token", sign="synthetic<&sign")
    payload = synthetic_payload()
    with _client(transport) as client:
        result = client.request_authorization(payload, ticket, CUIT)
    assert result.status == "authorized" and result.matches(payload)
    assert result.cae == "70000000000001" and result.cae_expiry.isoformat() == "2026-10-30"
    assert transport.authorization_calls == 1 and len(transport.records) == 1
    xml = ET.fromstring(transport.request_bodies[0])
    assert xml.findtext(f".//{{{WSFE_NS}}}Token") == ticket.token
    assert xml.findtext(f".//{{{WSFE_NS}}}Sign") == ticket.sign
    assert xml.findtext(f".//{{{WSFE_NS}}}CantReg") == "1"
    assert xml.findtext(f".//{{{WSFE_NS}}}MonId") == "PES"
    assert xml.findtext(f".//{{{WSFE_NS}}}MonCotiz") == "1"
    assert xml.findtext(f".//{{{WSFE_NS}}}CondicionIVAReceptorId") == "5"
    assert xml.findtext(f".//{{{WSFE_NS}}}ImpNeto") == "100.00"
    assert xml.findtext(f".//{{{WSFE_NS}}}ImpIVA") == "0.00"
    assert xml.find(f".//{{{WSFE_NS}}}Iva") is None
    assert xml.find(f".//{{{WSFE_NS}}}Tributos") is None
    assert len(xml.findall(f".//{{{WSFE_NS}}}FECAEDetRequest")) == 1
    assert result.events[0].code == 1
    # Same echoed identity with different full business data cannot reuse a result.
    changed = synthetic_payload(lines=[{"description": "Other service", "quantity": "1", "unit_price": "100.00", "total": "100.00"}])
    assert result.comparison(changed) == "conflict"


@pytest.mark.parametrize("document_type", [11, 15])
def test_factura_and_recibo_c_are_supported_without_improper_vat(document_type):
    with _client(ControlledArcaTransport()) as client:
        result = client.request_authorization(synthetic_payload(document_type=document_type), synthetic_ticket(now=NOW), CUIT)
    assert result.status == "authorized"


@pytest.mark.parametrize("method", sorted(PARAMETER_METHODS))
def test_parameter_methods_use_real_codec_cache_scope_and_expiry(method):
    transport = ControlledArcaTransport()
    clock = SimpleNamespace(now=NOW)
    ticket = synthetic_ticket(now=NOW)
    with _client(transport, clock=lambda: clock.now) as client:
        rows = client.parameters(method, ticket, CUIT)
        assert rows and all(isinstance(row, dict) for row in rows)
        assert client.parameters(method, ticket, CUIT) == rows
        assert transport.calls == [method]
        rows[0]["Desc"] = "Do not poison cached metadata"
        assert client.parameters(method, ticket, CUIT)[0].get("Desc") != "Do not poison cached metadata"
        rotated = replace(ticket, certificate_fingerprint="a" * 64)
        client.parameters(method, rotated, CUIT)
        assert transport.calls == [method, method]
        clock.now += timedelta(minutes=16)
        client.parameters(method, rotated, CUIT)
        assert transport.calls == [method, method, method]
    if method == "FEParamGetCondicionIvaReceptor":
        assert ET.fromstring(transport.request_bodies[0]).findtext(f".//{{{WSFE_NS}}}ClaseCmp") == "C"


def test_last_authorized_reads_remote_series_and_validates_echo():
    transport = ControlledArcaTransport()
    ticket = synthetic_ticket(now=NOW)
    with _client(transport) as client:
        assert client.last_authorized(ticket, CUIT, 1, 11) == 0
        assert client.request_authorization(synthetic_payload(), ticket, CUIT).status == "authorized"
        assert client.last_authorized(ticket, CUIT, 1, 11) == 1
        transport.response_mutator = _mutate("PtoVta", 2, method="FECompUltimoAutorizado")
        with pytest.raises(AppError) as error:
            client.last_authorized(ticket, CUIT, 1, 11)
        assert error.value.code == "arca_last_number_unknown"


@pytest.mark.parametrize("mode,status", [("observed", "authorized"), ("rejected", "rejected")])
def test_detail_observations_and_definitive_rejection_are_distinct(mode, status):
    transport = ControlledArcaTransport(mode=mode)
    with _client(transport) as client:
        result = client.request_authorization(synthetic_payload(), synthetic_ticket(now=NOW), CUIT)
    assert result.status == status and result.observations
    assert len(transport.records) == (1 if status == "authorized" else 0)
    assert result.events


def test_remote_observations_are_sanitized_without_storing_ticket_or_raw_response(caplog):
    transport = ControlledArcaTransport(mode="observed")
    ticket = synthetic_ticket(now=NOW)
    def echo_credentials(_method, xml):
        root = ET.fromstring(xml)
        for message in root.findall(f".//{{{WSFE_NS}}}Msg"):
            message.text = f"Synthetic token={ticket.token} sign={ticket.sign}"
        return ET.tostring(root, encoding="utf-8")
    transport.response_mutator = echo_credentials
    with _client(transport) as client:
        result = client.request_authorization(synthetic_payload(), ticket, CUIT)
    assert result.status == "authorized"
    assert ticket.token not in repr(result) and ticket.sign not in repr(result)
    assert ticket.token not in caplog.text and ticket.sign not in caplog.text
    assert "REDACTED" in result.observations[0].message


def test_lost_response_after_authorization_is_recovered_by_exact_consult_after_restart():
    transport = ControlledArcaTransport(timeout_after_authorization=True)
    payload, ticket = synthetic_payload(), synthetic_ticket(now=NOW)
    with _client(transport) as first:
        unknown = first.request_authorization(payload, ticket, CUIT)
    assert unknown.status == "unknown" and len(transport.records) == 1
    assert transport.authorization_calls == 1
    # A new adapter has no local authorization cache. The remote ledger persists.
    with _client(transport) as restarted:
        recovered = restarted.consult(ticket, CUIT, 1, 11, 1)
    assert recovered.status == "authorized" and recovered.comparison(payload) == "match"
    assert transport.authorization_calls == 1
    assert transport.calls == ["FECAESolicitar", "FECompConsultar"]


@pytest.mark.parametrize("field,value", [
    ("ImpTotal", "100.01"), ("ImpNeto", "99.99"), ("ImpTotConc", "1.00"), ("ImpOpEx", "1.00"),
    ("ImpTrib", "1.00"), ("ImpIVA", "1.00"), ("DocTipo", "80"), ("DocNro", "20123456786"),
    ("PtoVta", "2"), ("CbteTipo", "15"), ("CbteDesde", "2"), ("CbteHasta", "2"),
    ("Concepto", "3"), ("CbteFch", "20261019"), ("FchServDesde", "20261002"),
    ("FchServHasta", "20261019"), ("FchVtoPago", "20261021"), ("MonId", "DOL"),
    ("MonCotiz", "2"), ("CondicionIVAReceptorId", "6"),
])
def test_consult_never_adopts_a_different_remote_business_identity(field, value):
    transport = ControlledArcaTransport()
    ticket, payload = synthetic_ticket(now=NOW), synthetic_payload()
    with _client(transport) as client:
        assert client.request_authorization(payload, ticket, CUIT).matches(payload)
        transport.response_mutator = _mutate(field, value)
        result = client.consult(ticket, CUIT, 1, 11, 1)
    assert result.comparison(payload) == "conflict"


def test_consult_optional_iva_omission_and_incomplete_core_are_different():
    transport = ControlledArcaTransport()
    ticket, payload = synthetic_ticket(now=NOW), synthetic_payload()
    with _client(transport) as client:
        client.request_authorization(payload, ticket, CUIT)
        transport.omit_consult_iva = True
        assert client.consult(ticket, CUIT, 1, 11, 1).matches(payload)
        transport.response_mutator = _mutate("ImpTotal", remove=True)
        incomplete = client.consult(ticket, CUIT, 1, 11, 1)
        assert incomplete.status == "unknown" and incomplete.comparison(payload) == "incomplete"


@pytest.mark.parametrize("mode", ["fault", "malformed", "redirect"])
def test_fault_malformed_and_redirect_are_unknown_and_never_automatically_retried(mode):
    transport = ControlledArcaTransport(mode=mode)
    with _client(transport) as client:
        result = client.request_authorization(synthetic_payload(), synthetic_ticket(now=NOW), CUIT)
    assert result.status == "unknown" and transport.authorization_calls == 1


@pytest.mark.parametrize("content", [
    b'<!DOCTYPE doc [<!ENTITY external SYSTEM "file:///etc/passwd">]><doc>&external;</doc>',
    b"x" * (MAX_RESPONSE_BYTES + 1),
    f'<s:Envelope xmlns:s="{SOAP_NS}"><s:Body/><s:Body/></s:Envelope>'.encode(),
])
def test_xml_entities_oversized_and_duplicate_body_are_rejected_without_data_leak(content, caplog):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=content)
    with _client(httpx.MockTransport(handler)) as client:
        result = client.request_authorization(synthetic_payload(), synthetic_ticket(now=NOW), CUIT)
    assert result.status == "unknown" and len(calls) == 1
    assert "root:" not in str(result) and "synthetic-token-not-real" not in str(result)
    assert "synthetic-sign-not-real" not in caplog.text


@pytest.mark.parametrize("change", [
    {"expires_at": NOW}, {"generated_at": NOW + timedelta(minutes=1)}, {"service": "wsfev1"},
    {"environment": "production"}, {"represented_cuit": "20329642330"}, {"token": ""},
])
def test_ticket_scope_and_expiration_checked_before_transport(change):
    transport = ControlledArcaTransport()
    ticket = replace(synthetic_ticket(now=NOW), **change)
    with _client(transport) as client:
        with pytest.raises(AppError) as error:
            client.request_authorization(synthetic_payload(), ticket, CUIT)
    assert error.value.code == "arca_ticket_invalid" and transport.calls == []


def test_production_endpoint_and_tls_guards_run_before_http_client_creation(monkeypatch):
    created = []
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: created.append(kwargs))
    for kwargs in ({"environment": "production"}, {"environment": "homologation", "endpoint": "http://localhost/"},
                   {"environment": "homologation", "endpoint": WSFE_ENDPOINTS["production"]}):
        with pytest.raises(AppError):
            ArcaWsfeClient(**kwargs)
    assert created == []


def test_production_business_payload_does_not_read_a_ticket_or_call_transport():
    class UnavailableTicket:
        def __getattr__(self, _name):
            raise AssertionError("Production must be rejected before reading credentials")
    transport = ControlledArcaTransport()
    with _client(transport) as client:
        with pytest.raises(AppError) as error:
            client.request_authorization(synthetic_payload(environment="production"), UnavailableTicket(), CUIT)
    assert error.value.code == "arca_production_blocked" and transport.calls == []


def test_default_http_transport_uses_tls_timeouts_no_proxy_redirect_or_retry(monkeypatch):
    captured = {}
    class Transport(httpx.BaseTransport):
        def __init__(self, **kwargs):
            captured.update(kwargs)
        def handle_request(self, _request):
            raise AssertionError("No network request expected")
    monkeypatch.setattr(httpx, "HTTPTransport", Transport)
    with ArcaWsfeClient("homologation") as client:
        assert not client._http.follow_redirects
        assert client._http.timeout.connect == 5 and client._http.timeout.read == 25
    assert captured == {"verify": True, "retries": 0, "trust_env": False}


@pytest.mark.parametrize("change", [
    {"currency": "USD"}, {"exchange_rate": "2"}, {"vat_amount": "21.00"}, {"tax_amount": "1.00"},
    {"total": "99.99"}, {"net_amount": "99.99"}, {"service_to": "20260930"}, {"payment_due": "2026-10-19"},
    {"service_from": None}, {"document_type": 1},
    {"lines": [{"description": "Mismatch", "quantity": "1", "unit_price": "99.99", "total": "100.00"}]},
])
def test_business_payload_rejects_inconsistent_fiscal_data(change):
    with pytest.raises(ValidationError):
        synthetic_payload(**change)


def test_receiver_identification_is_explicit_never_inferred_from_owner_or_amount():
    base = synthetic_payload().receiver.model_dump()
    for change in ({"consumer_final": False}, {"document_number": 0}, {"iva_condition_id": 0},
                   {"document_type": 80, "document_number": 20123456788}):
        with pytest.raises(ValidationError):
            FiscalReceiverDetails.model_validate({**base, **change})
    with pytest.raises(ValidationError):
        FiscalReceiverDetails.model_validate({key: value for key, value in base.items() if key != "consumer_final"})
    identified = FiscalReceiverDetails.model_validate({**base, "document_type": 99, "document_number": 0})
    assert identified.consumer_final and identified.iva_condition_id == 5
    with pytest.raises(ValidationError):
        FiscalBusinessPayload.model_validate({**synthetic_payload().model_dump(mode="json"), "owner_document_id": "free text"})


def test_business_fingerprint_normalizes_decimal_scale_and_preserves_meaning():
    first = synthetic_payload()
    second = synthetic_payload(total="100", net_amount="100.0", exchange_rate="1.000000",
        lines=[{"description": "Synthetic veterinary service", "quantity": "1.00", "unit_price": "100", "total": "100.0"}])
    assert business_fingerprint(first) == business_fingerprint(second)
    assert first.model_dump(mode="json")["total"] == "100.00"

"""Controlled remote ledger for tests only; the real SOAP codec still runs.

This module is never selected by application settings or normal HTTP requests.
Keeping one transport instance across client/service restarts preserves its
remote ledger, including authorizations whose response was deliberately lost.
"""
from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from xml.etree import ElementTree as ET

import httpx
from defusedxml import ElementTree as SafeET

from app.schemas.arca_emission import FiscalBusinessPayload
from app.services.arca_wsfe import SOAP_NS, WSFE_NS


def _tag(name):
    return f"{{{WSFE_NS}}}{name}"


def _node(parent, name, text=None):
    node = ET.SubElement(parent, _tag(name))
    if text is not None:
        node.text = str(text)
    return node


def _text(parent, name):
    return parent.findtext(_tag(name))


def soap_response(method, content):
    envelope = ET.Element(f"{{{SOAP_NS}}}Envelope")
    body = ET.SubElement(envelope, f"{{{SOAP_NS}}}Body")
    result = _node(_node(body, method + "Response"), method + "Result")
    content(result)
    return ET.tostring(envelope, encoding="utf-8", xml_declaration=True)


def synthetic_payload(*, number=1, **changes):
    data = {
        "environment": "homologation",
        "issuer": {"cuit": "20123456786", "legal_name": "Synthetic issuer", "tax_condition": "Monotributo",
                   "fiscal_address": "Synthetic fiscal address", "gross_income_registration": "Synthetic IIBB",
                   "activity_start_date": "2020-01-01"},
        "receiver": {"document_type": 96, "document_number": 12345678, "iva_condition_id": 5,
                     "name": "Synthetic recipient", "address": "Synthetic recipient address", "consumer_final": True},
        "point_of_sale": 1, "document_type": 11, "concept": 2, "voucher_date": "2026-10-20",
        "service_from": "2026-10-01", "service_to": "2026-10-20", "payment_due": "2026-10-20",
        "total": "100.00", "net_amount": "100.00",
        "lines": [{"description": "Synthetic veterinary service", "quantity": "1", "unit_price": "100.00", "total": "100.00"}],
        "number": number,
    }
    data.update(changes)
    return FiscalBusinessPayload.model_validate(data)


def synthetic_ticket(*, now=None, **changes):
    from datetime import timedelta
    from app.services.arca_wsaa import AccessTicket

    now = now or datetime(2026, 10, 20, 12, tzinfo=UTC)
    values = {
        "token": "synthetic-token-not-real", "sign": "synthetic-sign-not-real",
        "generated_at": now - timedelta(minutes=1), "expires_at": now + timedelta(hours=1),
        "certificate_fingerprint": "f" * 64, "environment": "homologation",
        "auth_scope": "synthetic-tenant-scope", "represented_cuit": "20123456786", "service": "wsfe",
    }
    values.update(changes)
    return AccessTicket(**values)


class ControlledArcaTransport(httpx.BaseTransport):
    """One-voucher remote emulator behind the real production adapter's codec."""

    def __init__(self, *, timeout_after_authorization=False, mode="authorized", records=None, points_of_sale=(1,)):
        self.records = records if records is not None else {}
        self.calls: list[str] = []
        self.request_bodies: list[bytes] = []
        self.timeout_after_authorization = timeout_after_authorization
        self.mode = mode
        self.points_of_sale = tuple(points_of_sale)
        self.omit_consult_iva = False
        self.response_mutator = None
        self._lock = Lock()
        self.closed = False

    def close(self):
        # The external ledger intentionally outlives an HTTP client's lifecycle.
        self.closed = True

    @property
    def authorization_calls(self):
        return self.calls.count("FECAESolicitar")

    def handle_request(self, request):
        root = SafeET.fromstring(request.read(), forbid_dtd=True, forbid_entities=True, forbid_external=True)
        operation = list(root.find(f"{{{SOAP_NS}}}Body"))[0]
        method = operation.tag.split("}")[-1]
        auth = operation.find(_tag("Auth"))
        cuit = _text(auth, "Cuit")
        with self._lock:
            self.calls.append(method)
            # Test-only synthetic values; never log these bodies in production.
            self.request_bodies.append(request.content)
            if self.mode == "fault":
                return httpx.Response(200, content=(f'<s:Envelope xmlns:s="{SOAP_NS}"><s:Body><s:Fault>'
                    '<faultcode>soap:Server</faultcode><faultstring>Synthetic fault</faultstring>'
                    '</s:Fault></s:Body></s:Envelope>').encode())
            if self.mode == "malformed":
                return httpx.Response(200, content=b"<invalid")
            if self.mode == "redirect":
                return httpx.Response(302, headers={"Location": "https://forbidden.example/"})
            if method == "FECAESolicitar":
                header = operation.find(f"{_tag('FeCAEReq')}/{_tag('FeCabReq')}")
                detail = operation.find(f"{_tag('FeCAEReq')}/{_tag('FeDetReq')}/{_tag('FECAEDetRequest')}")
                data = {child.tag.split("}")[-1]: child.text or "" for child in detail}
                pos, document_type = int(_text(header, "PtoVta")), int(_text(header, "CbteTipo"))
                number = int(data["CbteDesde"])
                key = (cuit, pos, document_type, number)
                rejected = self.mode == "rejected"
                previous = self.records.get(key)
                cae = previous["CAE"] if previous else str(70000000000000 + len(self.records) + 1)
                data.update({"PtoVta": str(pos), "CbteTipo": str(document_type), "Cuit": cuit,
                             "Resultado": "R" if rejected else "A", "CAE": cae, "CAEFchVto": "20261030"})
                if not rejected:
                    existing = self.records.get(key)
                    if existing is not None and any(existing.get(name) != value for name, value in data.items()):
                        rejected = True
                        data["Resultado"] = "R"
                    else:
                        self.records[key] = dict(data)
                if self.timeout_after_authorization and not rejected:
                    self.timeout_after_authorization = False
                    raise httpx.ReadTimeout("Synthetic response loss after remote authorization", request=request)

                def render(result):
                    cab = _node(result, "FeCabResp")
                    for name, value in (("Cuit", cuit), ("PtoVta", pos), ("CbteTipo", document_type),
                                        ("CantReg", 1), ("Resultado", "R" if rejected else "A")):
                        _node(cab, name, value)
                    det = _node(_node(result, "FeDetResp"), "FECAEDetResponse")
                    for name in ("Concepto", "DocTipo", "DocNro", "CbteDesde", "CbteHasta", "CbteFch", "Resultado"):
                        _node(det, name, data[name])
                    if rejected:
                        obs = _node(_node(det, "Observaciones"), "Obs")
                        _node(obs, "Code", 10000)
                        _node(obs, "Msg", "Synthetic definitive validation rejection")
                    else:
                        _node(det, "CAE", data["CAE"])
                        _node(det, "CAEFchVto", data["CAEFchVto"])
                        if self.mode == "observed":
                            obs = _node(_node(det, "Observaciones"), "Obs")
                            _node(obs, "Code", 10017)
                            _node(obs, "Msg", "Synthetic nonblocking observation")
                    event = _node(_node(result, "Events"), "Evt")
                    _node(event, "Code", 1)
                    _node(event, "Msg", "Synthetic service event")

                response = soap_response(method, render)
            elif method == "FECompConsultar":
                query = operation.find(_tag("FeCompConsReq"))
                key = (cuit, int(_text(query, "PtoVta")), int(_text(query, "CbteTipo")), int(_text(query, "CbteNro")))
                data = self.records.get(key)

                def render(result):
                    if data is None:
                        error = _node(_node(result, "Errors"), "Err")
                        _node(error, "Code", 602)
                        _node(error, "Msg", "Synthetic voucher not found; does not authorize a new number")
                        return
                    det = _node(result, "ResultGet")
                    for name, value in data.items():
                        if name in {"Cuit", "CAE", "CAEFchVto"} or (self.omit_consult_iva and name == "CondicionIVAReceptorId"):
                            continue
                        _node(det, name, value)
                    _node(det, "CodAutorizacion", data["CAE"])
                    _node(det, "FchVto", data["CAEFchVto"])
                    _node(det, "EmisionTipo", "CAE")

                response = soap_response(method, render)
            elif method == "FECompUltimoAutorizado":
                pos, document_type = int(_text(operation, "PtoVta")), int(_text(operation, "CbteTipo"))
                latest = max((key[3] for key in self.records if key[:3] == (cuit, pos, document_type)), default=0)

                def render(result):
                    _node(result, "PtoVta", pos)
                    _node(result, "CbteTipo", document_type)
                    _node(result, "CbteNro", latest)

                response = soap_response(method, render)
            else:
                entries = {
                    "FEParamGetTiposCbte": [("CbteTipo", {"Id": "11", "Desc": "Factura C"}), ("CbteTipo", {"Id": "15", "Desc": "Recibo C"})],
                    "FEParamGetPtosVenta": [("PtoVenta", {"Nro": str(pos), "EmisionTipo": "CAE", "Bloqueado": "N", "FchBaja": "NULL"}) for pos in self.points_of_sale],
                    "FEParamGetTiposDoc": [("DocTipo", {"Id": "96", "Desc": "DNI"}), ("DocTipo", {"Id": "99", "Desc": "Sin identificar"})],
                    "FEParamGetTiposConcepto": [("ConceptoTipo", {"Id": "1", "Desc": "Productos"}), ("ConceptoTipo", {"Id": "2", "Desc": "Servicios"}), ("ConceptoTipo", {"Id": "3", "Desc": "Productos y servicios"})],
                    "FEParamGetTiposMonedas": [("Moneda", {"Id": "PES", "Desc": "Pesos argentinos"})],
                    "FEParamGetCondicionIvaReceptor": [("CondicionIvaReceptor", {"Id": "5", "Desc": "Consumidor final", "Cmp_Clase": "C"})],
                }
                assert method in entries, f"Unexpected test SOAP operation: {method}"

                def render(result):
                    values = _node(result, "ResultGet")
                    for tag, fields in entries[method]:
                        row = _node(values, tag)
                        for name, value in fields.items():
                            _node(row, name, value)

                response = soap_response(method, render)
            if self.response_mutator:
                response = self.response_mutator(method, response)
            return httpx.Response(200, content=response, headers={"Content-Type": "text/xml; charset=utf-8"})

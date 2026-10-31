"""WSFEv1 SOAP adapter with injectable HTTP transport, never an ARCA simulator.

Official sources consulted 2026-10-20:
* https://www.afip.gob.ar/ws/documentacion/ws-factura-electronica.asp
  links manual 4.7, history date 2026-09-01.
* https://www.afip.gob.ar/ws/documentacion/homologacion-externa.asp
  links https://www.afip.gob.ar/fe/ayuda/documentos/wsfev1-RG-4291.pdf
  manual 4.8, nominal history date 2026-12-01 (future on consultation day).
Used the URL/authentication, FECAESolicitar, FECompConsultar, last-authorized,
and six requested parameter contracts. This records the published homologation
specification, not successful external validation or its production activation.

FECAESolicitar echoes only a subset of the request; its result is also bound to
the exact business request hash. FECompConsultar supplies amounts/dates but its
published example omits receiver IVA: an absent optional IVA echo is not invented
or treated as a mismatch. All documented core echoes must still match exactly.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Callable, Literal
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

import httpx
from defusedxml import ElementTree as SafeET

from app.core.errors import AppError
from app.schemas.arca_emission import FiscalBusinessPayload
from app.schemas.fiscal_issuer import normalize_cuit


SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
SOAP12_NS = "http://www.w3.org/2003/05/soap-envelope"
WSFE_NS = "http://ar.gov.afip.dif.FEV1/"
WSFE_ENDPOINTS = {
    "homologation": "https://wswhomo.afip.gov.ar/wsfev1/service.asmx",
    "production": "https://servicios1.afip.gov.ar/wsfev1/service.asmx",
}
PARAMETER_METHODS = frozenset({
    "FEParamGetTiposCbte", "FEParamGetPtosVenta", "FEParamGetTiposDoc",
    "FEParamGetTiposConcepto", "FEParamGetTiposMonedas", "FEParamGetCondicionIvaReceptor",
})
MAX_RESPONSE_BYTES = 1024 * 1024
PARAMETER_TTL = timedelta(minutes=15)


class _ProtocolError(Exception):
    """Internal marker; never carries a remote body, credentials or exception text."""


@dataclass(frozen=True)
class WsfeMessage:
    code: int
    message: str


def business_fingerprint(payload: FiscalBusinessPayload) -> str:
    canonical = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _expected(payload: FiscalBusinessPayload) -> dict:
    return {
        "point_of_sale": payload.point_of_sale, "document_type": payload.document_type,
        "number": payload.number, "to_number": payload.number, "concept": payload.concept,
        "receiver_document_type": payload.receiver.document_type,
        "receiver_document_number": payload.receiver.document_number,
        "voucher_date": payload.voucher_date.isoformat(),
        "total": format(payload.total, ".2f"), "net_amount": format(payload.net_amount, ".2f"),
        "non_taxed_amount": format(payload.non_taxed_amount, ".2f"),
        "exempt_amount": format(payload.exempt_amount, ".2f"),
        "tax_amount": format(payload.tax_amount, ".2f"), "vat_amount": format(payload.vat_amount, ".2f"),
        "currency": payload.currency, "exchange_rate": str(payload.exchange_rate.normalize()),
        "service_from": payload.service_from.isoformat() if payload.service_from else None,
        "service_to": payload.service_to.isoformat() if payload.service_to else None,
        "payment_due": payload.payment_due.isoformat() if payload.payment_due else None,
    }


_AUTH_ECHO = frozenset({"point_of_sale", "document_type", "number", "to_number", "concept",
                        "receiver_document_type", "receiver_document_number", "voucher_date"})
_CONSULT_ECHO = _AUTH_ECHO | frozenset({"total", "net_amount", "non_taxed_amount", "exempt_amount",
    "tax_amount", "vat_amount", "currency", "exchange_rate", "service_from", "service_to", "payment_due"})


@dataclass(frozen=True)
class WsfeResult:
    status: Literal["authorized", "rejected", "unknown"]
    cae: str | None = None
    cae_expiry: date | None = None
    number: int | None = None
    observations: tuple[WsfeMessage, ...] = ()
    errors: tuple[WsfeMessage, ...] = ()
    events: tuple[WsfeMessage, ...] = ()
    remote: dict = field(default_factory=dict)
    operation: Literal["authorization", "consultation"] = "authorization"
    represented_cuit: str | None = None
    request_hash: str | None = None

    def comparison(self, payload: FiscalBusinessPayload) -> Literal["match", "conflict", "incomplete"]:
        if self.status != "authorized" or not self.cae or self.cae_expiry is None:
            return "incomplete"
        if self.represented_cuit != payload.issuer.cuit:
            return "conflict"
        expected = _expected(payload)
        required = _AUTH_ECHO if self.operation == "authorization" else frozenset(expected)
        if any(key not in self.remote for key in required):
            return "incomplete"
        if any(self.remote[key] != expected[key] for key in required):
            return "conflict"
        if "receiver_iva_condition_id" in self.remote and self.remote["receiver_iva_condition_id"] != payload.receiver.iva_condition_id:
            return "conflict"
        if "cuit" in self.remote and self.remote["cuit"] != payload.issuer.cuit:
            return "conflict"
        if self.cae_expiry < payload.voucher_date:
            return "conflict"
        if self.operation == "authorization" and self.request_hash != business_fingerprint(payload):
            return "conflict"
        return "match"

    def matches(self, payload: FiscalBusinessPayload) -> bool:
        return self.comparison(payload) == "match"


def _tag(name):
    return f"{{{WSFE_NS}}}{name}"


def _add(parent, name, value):
    child = ET.SubElement(parent, _tag(name))
    child.text = str(value)
    return child


def _one(parent, name, *, required=True):
    if parent is None:
        if required:
            raise _ProtocolError()
        return None
    values = parent.findall(_tag(name))
    if len(values) > 1 or (required and len(values) != 1):
        raise _ProtocolError()
    return values[0] if values else None


def _text(parent, name, *, required=True):
    node = _one(parent, name, required=required)
    if node is None:
        return None
    value = (node.text or "").strip()
    if required and not value:
        raise _ProtocolError()
    return value


def _integer(value):
    if not re.fullmatch(r"[0-9]{1,15}", value or ""):
        raise _ProtocolError()
    return int(value)


def _decimal(value):
    try:
        decimal = Decimal(value)
    except (InvalidOperation, TypeError):
        raise _ProtocolError() from None
    if not decimal.is_finite() or decimal < 0:
        raise _ProtocolError()
    return decimal


def _date(value):
    try:
        if not re.fullmatch(r"[0-9]{8}", value or ""):
            raise ValueError()
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        raise _ProtocolError() from None


def _clean(value: str, secrets: tuple[str, ...]) -> str:
    for secret in secrets:
        if secret:
            value = value.replace(secret, "[REDACTED]")
    value = re.sub(r"(?i)(token|sign|password|secret)\s*[:=]\s*\S+", r"\1=[REDACTED]", value)
    value = re.sub(r"[\x00-\x1f\x7f]", " ", value)
    return value[:500]


def _messages(parent, container, element, secrets):
    node = _one(parent, container, required=False)
    if node is None:
        return ()
    return tuple(WsfeMessage(_integer(_text(row, "Code")), _clean(_text(row, "Msg"), secrets))
                 for row in node.findall(_tag(element))[:100])


def _remote(detail, *, header=None):
    result = {}
    int_fields = {
        "Concepto": "concept", "DocTipo": "receiver_document_type", "DocNro": "receiver_document_number",
        "CbteDesde": "number", "CbteHasta": "to_number", "CondicionIVAReceptorId": "receiver_iva_condition_id",
        "PtoVta": "point_of_sale", "CbteTipo": "document_type",
    }
    for xml_name, field_name in int_fields.items():
        value = _text(detail, xml_name, required=False)
        if value:
            result[field_name] = _integer(value)
    for xml_name, field_name in {"CbteFch": "voucher_date", "FchServDesde": "service_from",
                                "FchServHasta": "service_to", "FchVtoPago": "payment_due"}.items():
        value = _text(detail, xml_name, required=False)
        if value:
            result[field_name] = _date(value).isoformat()
        elif xml_name != "CbteFch" and result.get("concept") == 1:
            # Empty service dates are the documented representation for goods.
            result[field_name] = None
    for xml_name, field_name in {"ImpTotal": "total", "ImpNeto": "net_amount", "ImpTotConc": "non_taxed_amount",
                                "ImpOpEx": "exempt_amount", "ImpTrib": "tax_amount", "ImpIVA": "vat_amount"}.items():
        value = _text(detail, xml_name, required=False)
        if value is not None and value != "":
            amount = _decimal(value)
            if amount != amount.quantize(Decimal("0.01")):
                raise _ProtocolError()
            result[field_name] = format(amount, ".2f")
    currency = _text(detail, "MonId", required=False)
    if currency:
        result["currency"] = currency
    rate = _text(detail, "MonCotiz", required=False)
    if rate:
        result["exchange_rate"] = str(_decimal(rate).normalize())
    cuit = _text(detail, "Cuit", required=False)
    if cuit:
        result["cuit"] = str(_integer(cuit))
    if header is not None:
        result["cuit"] = str(_integer(_text(header, "Cuit")))
        result["point_of_sale"] = _integer(_text(header, "PtoVta"))
        result["document_type"] = _integer(_text(header, "CbteTipo"))
    return result


class ArcaWsfeClient:
    def __init__(self, environment: str, *, transport: httpx.BaseTransport | None = None,
                 clock: Callable[[], datetime] | None = None, endpoint: str | None = None):
        # Guard before creating an HTTP client, reading a ticket, or resolving credentials.
        if environment == "production":
            raise AppError(403, "arca_production_blocked", "La emisión productiva permanece bloqueada")
        if environment != "homologation" or endpoint not in {None, WSFE_ENDPOINTS["homologation"]}:
            raise AppError(422, "arca_endpoint_forbidden", "El ambiente o endpoint fiscal no está permitido")
        self.environment = environment
        self.endpoint = WSFE_ENDPOINTS[environment]
        self.clock = clock or (lambda: datetime.now(UTC))
        self._cache: dict[tuple, tuple[datetime, list[dict]]] = {}
        self.parameter_events: dict[tuple, tuple[WsfeMessage, ...]] = {}
        self._http = httpx.Client(
            transport=transport if transport is not None else httpx.HTTPTransport(verify=True, retries=0, trust_env=False),
            verify=True, trust_env=False, follow_redirects=False,
            timeout=httpx.Timeout(connect=5, read=25, write=10, pool=5),
        )

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def _ticket(self, ticket, cuit):
        if self.environment != "homologation":
            raise AppError(403, "arca_production_blocked", "La emisión productiva permanece bloqueada")
        try:
            valid = (normalize_cuit(str(cuit)) == str(cuit) and ticket.environment == self.environment
                     and ticket.service == "wsfe" and ticket.represented_cuit == str(cuit)
                     and bool(ticket.auth_scope)
                     and re.fullmatch(r"[0-9a-fA-F]{64}", ticket.certificate_fingerprint) is not None
                     and ticket.generated_at.tzinfo is not None and ticket.expires_at.tzinfo is not None
                     and ticket.generated_at <= self.clock() < ticket.expires_at
                     and bool(ticket.token) and bool(ticket.sign))
        except (AttributeError, ValueError, TypeError):
            valid = False
        if not valid:
            raise AppError(409, "arca_ticket_invalid", "El acceso WSFE no está vigente o no corresponde al ámbito fiscal")

    def _envelope(self, method, ticket, cuit):
        self._ticket(ticket, cuit)
        envelope = ET.Element(f"{{{SOAP_NS}}}Envelope")
        body = ET.SubElement(envelope, f"{{{SOAP_NS}}}Body")
        operation = ET.SubElement(body, _tag(method))
        auth = ET.SubElement(operation, _tag("Auth"))
        _add(auth, "Token", ticket.token)
        _add(auth, "Sign", ticket.sign)
        _add(auth, "Cuit", cuit)
        return envelope, operation

    def _send(self, method, envelope):
        request = ET.tostring(envelope, encoding="utf-8", xml_declaration=True)
        with self._http.stream("POST", self.endpoint, content=request, headers={
            "Content-Type": "text/xml; charset=utf-8", "SOAPAction": f'"{WSFE_NS}{method}"',
        }) as response:
            if response.status_code != 200:
                raise _ProtocolError()
            length = response.headers.get("Content-Length")
            if length and (not length.isdigit() or int(length) > MAX_RESPONSE_BYTES):
                raise _ProtocolError()
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise _ProtocolError()
                chunks.append(chunk)
        try:
            root = SafeET.fromstring(b"".join(chunks), forbid_dtd=True, forbid_entities=True, forbid_external=True)
        except Exception:
            raise _ProtocolError() from None
        if root.tag not in {f"{{{SOAP_NS}}}Envelope", f"{{{SOAP12_NS}}}Envelope"}:
            raise _ProtocolError()
        soap_namespace = root.tag.split("}")[0] + "}"
        bodies = root.findall(soap_namespace + "Body")
        if len(bodies) != 1 or any(child.tag.endswith("}Fault") for child in bodies[0]):
            raise _ProtocolError()
        response = _one(bodies[0], method + "Response")
        return _one(response, method + "Result")

    def parameters(self, method: str, ticket, cuit: str) -> list[dict]:
        if method not in PARAMETER_METHODS:
            raise AppError(422, "arca_parameter_method_invalid", "Consulta de parámetros no permitida")
        envelope, operation = self._envelope(method, ticket, cuit)
        scope = (self.environment, cuit, ticket.certificate_fingerprint, ticket.auth_scope, ticket.service, method)
        cached = self._cache.get(scope)
        if cached and cached[0] > self.clock():
            return [dict(row) for row in cached[1]]
        if method == "FEParamGetCondicionIvaReceptor":
            _add(operation, "ClaseCmp", "C")
        try:
            result = self._send(method, envelope)
            if _messages(result, "Errors", "Err", (ticket.token, ticket.sign)):
                raise _ProtocolError()
            self.parameter_events[scope] = _messages(result, "Events", "Evt", (ticket.token, ticket.sign))
            rows = _one(result, "ResultGet")
            values = []
            for row in list(rows)[:2000]:
                item = {}
                for field in row:
                    if not field.tag.startswith("{" + WSFE_NS + "}") or len(field):
                        raise _ProtocolError()
                    name = field.tag.split("}")[-1]
                    if name in item:
                        raise _ProtocolError()
                    item[name] = _clean((field.text or "").strip(), (ticket.token, ticket.sign))
                values.append(item)
        except (httpx.HTTPError, _ProtocolError, ValueError):
            raise AppError(502, "arca_parameters_unavailable", "No fue posible validar los parámetros remotos; no se presume habilitación") from None
        self._cache[scope] = (self.clock() + PARAMETER_TTL, values)
        return [dict(row) for row in values]

    def last_authorized(self, ticket, cuit: str, pos: int, document_type: int) -> int:
        self._series_identity(pos, document_type)
        envelope, operation = self._envelope("FECompUltimoAutorizado", ticket, cuit)
        _add(operation, "PtoVta", pos)
        _add(operation, "CbteTipo", document_type)
        try:
            result = self._send("FECompUltimoAutorizado", envelope)
            if _messages(result, "Errors", "Err", (ticket.token, ticket.sign)):
                raise _ProtocolError()
            if _integer(_text(result, "PtoVta")) != pos or _integer(_text(result, "CbteTipo")) != document_type:
                raise _ProtocolError()
            number = _integer(_text(result, "CbteNro"))
            if number > 99999999:
                raise _ProtocolError()
            return number
        except (httpx.HTTPError, _ProtocolError, ValueError):
            raise AppError(502, "arca_last_number_unknown", "No pudo comprobarse el último número autorizado de esta serie") from None

    def request_authorization(self, payload: FiscalBusinessPayload, ticket, cuit: str) -> WsfeResult:
        if payload.environment == "production":
            raise AppError(403, "arca_production_blocked", "La emisión productiva permanece bloqueada")
        # Defensive revalidation also catches an internal model_copy/construct
        # that bypassed nested monetary or receiver validators.
        payload = FiscalBusinessPayload.model_validate(payload.model_dump(mode="json"))
        if payload.environment != self.environment or payload.issuer.cuit != cuit or payload.number is None:
            raise AppError(409, "arca_payload_context_mismatch", "La solicitud no coincide con el emisor, ambiente o número congelado")
        envelope, operation = self._envelope("FECAESolicitar", ticket, cuit)
        today = self.clock().astimezone(ZoneInfo("America/Argentina/Buenos_Aires")).date()
        tolerance = 5 if payload.concept == 1 else 10
        if abs((payload.voucher_date - today).days) > tolerance or (payload.concept == 1 and payload.voucher_date.month != today.month):
            raise AppError(422, "arca_voucher_date_invalid", "La fecha del comprobante está fuera del rango permitido por WSFE")
        request = ET.SubElement(operation, _tag("FeCAEReq"))
        header = ET.SubElement(request, _tag("FeCabReq"))
        for name, value in (("CantReg", 1), ("PtoVta", payload.point_of_sale), ("CbteTipo", payload.document_type)):
            _add(header, name, value)
        detail = ET.SubElement(ET.SubElement(request, _tag("FeDetReq")), _tag("FECAEDetRequest"))
        fields = [
            ("Concepto", payload.concept), ("DocTipo", payload.receiver.document_type),
            ("DocNro", payload.receiver.document_number), ("CbteDesde", payload.number), ("CbteHasta", payload.number),
            ("CbteFch", payload.voucher_date.strftime("%Y%m%d")), ("ImpTotal", format(payload.total, ".2f")),
            ("ImpTotConc", "0.00"), ("ImpNeto", format(payload.net_amount, ".2f")),
            ("ImpOpEx", "0.00"), ("ImpTrib", "0.00"), ("ImpIVA", "0.00"),
        ]
        if payload.concept in {2, 3}:
            fields.extend((name, value.strftime("%Y%m%d")) for name, value in (
                ("FchServDesde", payload.service_from), ("FchServHasta", payload.service_to), ("FchVtoPago", payload.payment_due)))
        fields.extend((("MonId", "PES"), ("MonCotiz", "1"), ("CondicionIVAReceptorId", payload.receiver.iva_condition_id)))
        for name, value in fields:
            _add(detail, name, value)
        context = {"operation": "authorization", "represented_cuit": cuit, "request_hash": business_fingerprint(payload)}
        errors, events, observations = (), (), ()
        try:
            result = self._send("FECAESolicitar", envelope)
            secrets = (ticket.token, ticket.sign)
            errors = _messages(result, "Errors", "Err", secrets)
            events = _messages(result, "Events", "Evt", secrets)
            cab = _one(result, "FeCabResp")
            details = _one(result, "FeDetResp")
            children = list(details)
            if _integer(_text(cab, "CantReg")) != 1 or len(children) != 1 or children[0].tag != _tag("FECAEDetResponse"):
                raise _ProtocolError()
            det = children[0]
            remote = _remote(det, header=cab)
            expected = _expected(payload)
            if any(remote.get(key) != expected[key] for key in _AUTH_ECHO) or remote.get("cuit") != cuit:
                raise _ProtocolError()
            observations = _messages(det, "Observaciones", "Obs", secrets)
            state, header_state = _text(det, "Resultado"), _text(cab, "Resultado")
            if state == "R" and header_state == "R":
                return WsfeResult("rejected", errors=errors, events=events, observations=observations, remote=remote, **context)
            if state != "A" or header_state != "A" or errors:
                raise _ProtocolError()
            cae, expiry = _text(det, "CAE"), _date(_text(det, "CAEFchVto"))
            if not re.fullmatch(r"[0-9]{14}", cae) or int(cae) == 0:
                raise _ProtocolError()
            outcome = WsfeResult("authorized", cae, expiry, payload.number, observations, errors, events, remote, **context)
            return outcome if outcome.matches(payload) else WsfeResult("unknown", errors=(WsfeMessage(-1, "La respuesta fiscal no coincide con la solicitud congelada"),), **context)
        except (httpx.HTTPError, _ProtocolError, ValueError, InvalidOperation):
            diagnostic = WsfeMessage(-1, "El resultado puede ser incierto; consulta el número persistido antes de volver a enviar")
            return WsfeResult("unknown", errors=(*errors, diagnostic), observations=observations, events=events, **context)

    def consult(self, ticket, cuit: str, pos: int, document_type: int, number: int) -> WsfeResult:
        self._series_identity(pos, document_type, number)
        envelope, operation = self._envelope("FECompConsultar", ticket, cuit)
        query = ET.SubElement(operation, _tag("FeCompConsReq"))
        for name, value in (("CbteTipo", document_type), ("CbteNro", number), ("PtoVta", pos)):
            _add(query, name, value)
        context = {"operation": "consultation", "represented_cuit": cuit}
        try:
            result = self._send("FECompConsultar", envelope)
            secrets = (ticket.token, ticket.sign)
            errors = _messages(result, "Errors", "Err", secrets)
            events = _messages(result, "Events", "Evt", secrets)
            detail = _one(result, "ResultGet", required=False)
            if errors or detail is None:
                # Official general error table: 602 = no registered data. This
                # is only an observation, never proof that an older sender has
                # stopped. The orchestrator may permit an explicit fenced retry
                # of the exact same number/request; it must not allocate a new one.
                absent = detail is None and bool(errors) and all(message.code == 602 for message in errors)
                return WsfeResult("unknown", errors=errors, events=events,
                                  remote={"not_found": True} if absent else {}, **context)
            remote = _remote(detail)
            if not _CONSULT_ECHO.issubset(remote):
                return WsfeResult("unknown", errors=(WsfeMessage(-1, "La consulta contiene datos fiscales incompletos; conserva el número y solicita conciliación"),), remote=remote, **context)
            cae, expiry = _text(detail, "CodAutorizacion"), _date(_text(detail, "FchVto"))
            if _text(detail, "Resultado") != "A" or _text(detail, "EmisionTipo") != "CAE" or not re.fullmatch(r"[0-9]{14}", cae) or int(cae) == 0:
                raise _ProtocolError()
            # Never replace returned fields with the query's fields: reconciliation
            # must detect a different remote voucher instead of adopting its CAE.
            return WsfeResult("authorized", cae, expiry, remote.get("number"),
                _messages(detail, "Observaciones", "Obs", secrets), errors, events, remote, **context)
        except (httpx.HTTPError, _ProtocolError, ValueError, InvalidOperation):
            return WsfeResult("unknown", errors=(WsfeMessage(-1, "La consulta remota no permite resolver el resultado; conserva la reserva y el número"),), **context)

    @staticmethod
    def _series_identity(pos, document_type, number=None):
        if (not isinstance(pos, int) or isinstance(pos, bool) or not 1 <= pos <= 99999
                or document_type not in {11, 15}
                or (number is not None and (not isinstance(number, int) or isinstance(number, bool) or not 1 <= number <= 99999999))):
            raise AppError(422, "arca_series_identity_invalid", "Selecciona una serie C y un número de comprobante válidos")

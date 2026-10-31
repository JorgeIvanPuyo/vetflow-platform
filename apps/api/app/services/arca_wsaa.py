"""WSAA 1.2.2 (official specification reviewed 2026-10-20).

https://www.afip.gob.ar/ws/WSAA/Especificacion_Tecnica_WSAA_1.2.2.pdf
TRA uses embedded CMS SignedData, RSA+SHA1 (p.7), service `wsfe`; valid TAs
are reused (p.10). cryptography's PKCS7 builder rejects SHA1, so the maintained
OpenSSL CMS implementation signs through anonymous pipes without key arguments
or persistent files. This does not weaken HTTPS/TLS policy.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Callable, Mapping
from xml.etree import ElementTree as ET

import httpx
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from defusedxml.ElementTree import fromstring
from defusedxml.common import DefusedXmlException
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.arca_auth import ArcaTenantTicketGrant
from app.repositories.arca_auth import ArcaAuthRepository
from app.services.arca_credentials import (
    CredentialRegistry, ValidatedCredential, external_server_file,
    require_homologation, validate_credential,
)


WSAA_ENDPOINTS = {"homologation": "https://wsaahomo.afip.gov.ar/ws/services/LoginCms"}
WSAA_NAMESPACE = "http://wsaa.view.sua.dvadac.desein.afip.gov"
SOAP_NAMESPACE = "http://schemas.xmlsoap.org/soap/envelope/"
MAX_XML_BYTES = 1024 * 1024
TICKET_MAX_LIFETIME = timedelta(hours=12)
TRA_CLOCK_WINDOW = timedelta(minutes=5)


def utcnow():
    return datetime.now(UTC)


def aware(value: datetime) -> datetime:
    # PostgreSQL preserves timezone; SQLite fixtures return naive UTC columns.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True)
class AccessTicket:
    token: str = field(repr=False)
    sign: str = field(repr=False)
    generated_at: datetime
    expires_at: datetime
    certificate_fingerprint: str = ""
    environment: str = "homologation"
    auth_scope: str = ""
    represented_cuit: str = field(default="", repr=False)
    service: str = "wsfe"


@dataclass(frozen=True)
class TicketEncryptionKey:
    scope: str
    key: bytes = field(repr=False)


class TicketKeyring:
    def __init__(self, keys: Mapping[str, TicketEncryptionKey], active_version: str | None):
        self.keys = dict(keys)
        self.active_version = active_version
        for version, material in self.keys.items():
            if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", version) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,120}", material.scope) or len(material.key) != 32:
                raise ValueError("Invalid external ticket encryption key")
        if active_version is not None and active_version not in self.keys:
            raise ValueError("Unknown active encryption version")

    @classmethod
    def from_server_settings(cls):
        path = os.getenv("ARCA_TICKET_KEYRING_FILE")
        if not path:
            return cls({}, None)
        try:
            raw = external_server_file(path, secret=True).read_bytes()
            if len(raw) > 64 * 1024:
                raise ValueError()
            content = json.loads(raw)
            keys = {version: TicketEncryptionKey(scope=entry["scope"], key=base64.b64decode(entry["key_b64"], validate=True)) for version, entry in content["keys"].items()}
            return cls(keys, content["active_version"])
        except (OSError, ValueError, KeyError, TypeError):
            raise AppError(503, "arca_ticket_keyring_invalid", "El cifrado fiscal del servidor no está correctamente provisionado") from None

    def ensure_ready(self):
        if self.active_version is None:
            raise AppError(503, "arca_ticket_encryption_not_configured", "Provisiona el cifrado de tickets fiscales fuera de la base de datos")

    @staticmethod
    def _aad(context, version, scope):
        return json.dumps({"context": context, "key_version": version, "key_scope": scope}, sort_keys=True, separators=(",", ":")).encode()

    def encrypt(self, plaintext: bytes, context: dict):
        self.ensure_ready()
        version = self.active_version
        material = self.keys[version]
        nonce = os.urandom(12)
        ciphertext = nonce + AESGCM(material.key).encrypt(nonce, plaintext, self._aad(context, version, material.scope))
        return ciphertext, version, material.scope

    def decrypt(self, ciphertext: bytes, version: str, scope: str, context: dict):
        material = self.keys.get(version)
        if material is None or material.scope != scope:
            raise AppError(503, "arca_ticket_key_version_unavailable", "La versión de cifrado del ticket no está disponible; restituye la clave externa")
        try:
            if len(ciphertext) < 29 or len(ciphertext) > MAX_XML_BYTES:
                raise ValueError()
            return AESGCM(material.key).decrypt(ciphertext[:12], ciphertext[12:], self._aad(context, version, scope))
        except (InvalidTag, ValueError, TypeError):
            raise AppError(503, "arca_ticket_integrity_failed", "El ticket cifrado no supera la validación de integridad y ámbito") from None


def build_tra(now: datetime, *, unique_id: int | None = None) -> tuple[bytes, int]:
    if now.tzinfo is None:
        raise AppError(503, "arca_clock_invalid", "El reloj fiscal requiere zona horaria")
    now = now.astimezone(UTC)
    unique_id = int.from_bytes(os.urandom(4), "big") if unique_id is None else unique_id
    if not isinstance(unique_id, int) or not 0 <= unique_id <= 0xFFFFFFFF:
        raise AppError(503, "arca_unique_id_invalid", "El identificador del requerimiento fiscal no es válido")
    root = ET.Element("loginTicketRequest", version="1.0")
    header = ET.SubElement(root, "header")
    ET.SubElement(header, "uniqueId").text = str(unique_id)
    ET.SubElement(header, "generationTime").text = (now - TRA_CLOCK_WINDOW).isoformat(timespec="seconds")
    ET.SubElement(header, "expirationTime").text = (now + TRA_CLOCK_WINDOW).isoformat(timespec="seconds")
    ET.SubElement(root, "service").text = "wsfe"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), unique_id


def sign_cms(tra: bytes, credential: ValidatedCredential) -> bytes:
    executable = shutil.which("openssl")
    if not executable:
        raise AppError(503, "arca_cms_runtime_unavailable", "El runtime requiere OpenSSL CMS con soporte RSA y SHA1")
    if len(tra) > 16 * 1024:
        raise AppError(503, "arca_cms_input_invalid", "El requerimiento fiscal excede su tamaño permitido")
    descriptors = []
    try:
        certificate_read, certificate_write = os.pipe()
        descriptors.extend((certificate_read, certificate_write))
        key_read, key_write = os.pipe()
        descriptors.extend((key_read, key_write))
        # RSA keys and certificates generated/validated above fit the pipe. A
        # bounded material size prevents a pre-subprocess blocking write.
        if len(credential.certificate_pem) > 4096 or len(credential.private_key_pem) > 4096:
            raise AppError(409, "arca_cms_material_unsupported", "El material RSA excede el tamaño soportado por el firmador")
        os.write(certificate_write, credential.certificate_pem)
        os.close(certificate_write)
        descriptors.remove(certificate_write)
        os.write(key_write, credential.private_key_pem)
        os.close(key_write)
        descriptors.remove(key_write)
        result = subprocess.run([executable, "cms", "-sign", "-binary", "-nodetach", "-md", "sha1", "-outform", "DER", "-signer", f"/proc/self/fd/{certificate_read}", "-inkey", f"/proc/self/fd/{key_read}"], input=tra, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False, pass_fds=(certificate_read, key_read))
        if result.returncode or not result.stdout or len(result.stdout) > MAX_XML_BYTES:
            raise AppError(503, "arca_cms_signature_failed", "No fue posible firmar el requerimiento CMS con RSA y SHA1")
        return result.stdout
    except (OSError, subprocess.SubprocessError):
        raise AppError(503, "arca_cms_signature_failed", "No fue posible firmar el requerimiento CMS con RSA y SHA1") from None
    finally:
        for descriptor in descriptors:
            os.close(descriptor)


def build_login_cms_soap(cms_b64: str) -> bytes:
    root = ET.Element(f"{{{SOAP_NAMESPACE}}}Envelope")
    body = ET.SubElement(root, f"{{{SOAP_NAMESPACE}}}Body")
    operation = ET.SubElement(body, f"{{{WSAA_NAMESPACE}}}loginCms")
    ET.SubElement(operation, f"{{{WSAA_NAMESPACE}}}in0").text = cms_b64
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


class HttpWsaaTransport:
    def __init__(self, *, transport: httpx.BaseTransport | None = None, allow_homologation_external: bool = False):
        self.transport = transport
        self.allow_homologation_external = allow_homologation_external

    def close(self):
        # Each login owns a context-managed Client and closes its transport.
        # Runtime.close() may therefore call this uniformly without retaining
        # an HTTP pool or raising after an otherwise persisted authorization.
        return None

    def ensure_enabled(self, environment):
        require_homologation(environment)
        if self.transport is None and not self.allow_homologation_external:
            raise AppError(503, "arca_homologation_external_disabled", "La conexión real de homologación requiere habilitación explícita del servidor")

    def login_cms(self, environment: str, cms_b64: str) -> bytes:
        self.ensure_enabled(environment)
        try:
            # New per-call clients own and close pools; redirects and retries are
            # disabled, TLS certificate verification remains enabled.
            with httpx.Client(transport=self.transport if self.transport is not None else httpx.HTTPTransport(verify=True, retries=0, trust_env=False), verify=True, trust_env=False, follow_redirects=False, timeout=httpx.Timeout(20.0, connect=5.0, write=10.0, pool=5.0)) as client:
                with client.stream("POST", WSAA_ENDPOINTS[environment], content=build_login_cms_soap(cms_b64), headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": '""'}) as response:
                    if response.is_redirect:
                        raise AppError(503, "arca_wsaa_redirect_rejected", "WSAA devolvió una redirección no permitida")
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > MAX_XML_BYTES:
                            raise AppError(503, "arca_wsaa_response_invalid", "La respuesta WSAA excede el límite permitido")
                        chunks.append(chunk)
                    content = b"".join(chunks)
                    # HTTP500 SOAP Faults must pass the same secure parser.
                    if response.status_code not in {200, 500}:
                        raise AppError(503, "arca_wsaa_transport_failed", "WSAA no devolvió una respuesta procesable")
                    return content
        except httpx.HTTPError:
            raise AppError(503, "arca_wsaa_transport_failed", "No se pudo confirmar el resultado de la autenticación WSAA") from None


class WsaaFault(AppError):
    def __init__(self, fault_code):
        self.fault_code = fault_code
        super().__init__(503, "arca_wsaa_" + fault_code.replace(".", "_"), "WSAA rechazó la autenticación; revisa el diagnóstico fiscal del servidor")


def _xml(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_XML_BYTES:
        raise AppError(503, "arca_wsaa_response_invalid", "La respuesta WSAA no es válida")
    try:
        return fromstring(raw, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except (ET.ParseError, DefusedXmlException, ValueError):
        raise AppError(503, "arca_wsaa_response_invalid", "La respuesta WSAA no es XML seguro y completo") from None


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _one_text(parent, name):
    matching = [child for child in parent if _local(child.tag) == name]
    if len(matching) != 1 or len(matching[0]) or not matching[0].text or not matching[0].text.strip():
        raise AppError(503, "arca_wsaa_response_invalid", "El ticket WSAA está incompleto")
    return matching[0].text.strip()


def _dn(value):
    aliases = {"serialnumber": "2.5.4.5", "cn": "2.5.4.3", "c": "2.5.4.6", "o": "2.5.4.10", "ou": "2.5.4.11"}
    parts = []
    for part in re.split(r"(?<!\\),", value):
        name, separator, content = part.partition("=")
        if not separator:
            raise ValueError()
        name = name.strip().lower()
        parts.append((aliases.get(name, name), content.strip().casefold()))
    return sorted(parts)


def parse_wsaa_response(raw: bytes, *, now: datetime, credential: ValidatedCredential, environment: str, auth_scope: str, unique_id: int) -> AccessTicket:
    require_homologation(environment)
    soap = _xml(raw)
    if soap.tag != f"{{{SOAP_NAMESPACE}}}Envelope":
        raise AppError(503, "arca_wsaa_response_invalid", "WSAA no devolvió un sobre SOAP válido")
    bodies = soap.findall(f"{{{SOAP_NAMESPACE}}}Body")
    if len(bodies) != 1:
        raise AppError(503, "arca_wsaa_response_invalid", "La respuesta SOAP de WSAA está incompleta")
    body = bodies[0]
    faults = [node for node in body if _local(node.tag) == "Fault"]
    if faults:
        # Only allowlisted codes escape the parser. Fault text may echo secrets.
        text = " ".join(faults[0].itertext())
        known = re.search(r"(?:coe\.(?:notAuthorized|alreadyAuthenticated)|cms\.(?:bad(?:\.base64)?|cert\.(?:notFound|expired|invalid|untrusted)|sign\.invalid)|xml\.(?:bad|source\.invalid|destination\.invalid|version\.notSupported|generationTime\.invalid|expirationTime\.(?:expired|invalid))|wsn\.(?:unavailable|notFound)|wsaa\.(?:unavailable|internalError))", text)
        raise WsaaFault(known.group(0) if known else "unrecognized_fault")
    responses = [node for node in body if node.tag == f"{{{WSAA_NAMESPACE}}}loginCmsResponse"]
    if len(responses) != 1 or len(body) != 1:
        raise AppError(503, "arca_wsaa_response_invalid", "WSAA no devolvió loginCmsResponse")
    response = _xml(_one_text(responses[0], "loginCmsReturn").encode())
    if response.tag != "loginTicketResponse":
        raise AppError(503, "arca_wsaa_response_invalid", "El ticket WSAA no tiene el formato esperado")
    headers = [node for node in response if node.tag == "header"]
    credentials = [node for node in response if node.tag == "credentials"]
    if len(headers) != 1 or len(credentials) != 1:
        raise AppError(503, "arca_wsaa_response_invalid", "El ticket WSAA está incompleto")
    header = headers[0]
    try:
        generated = datetime.fromisoformat(_one_text(header, "generationTime").replace("Z", "+00:00"))
        expires = datetime.fromisoformat(_one_text(header, "expirationTime").replace("Z", "+00:00"))
        expected_source = "cn=wsaahomo,o=afip,c=ar,serialNumber=CUIT 33693450239"
        if generated.tzinfo is None or expires.tzinfo is None or not generated < expires or generated > now + timedelta(minutes=2) or expires <= now or expires - generated > TICKET_MAX_LIFETIME + timedelta(minutes=2):
            raise ValueError()
        if int(_one_text(header, "uniqueId")) != unique_id or _dn(_one_text(header, "source")) != _dn(expected_source) or _dn(_one_text(header, "destination")) != _dn(credential.subject_dn):
            raise ValueError()
        token, sign = _one_text(credentials[0], "token"), _one_text(credentials[0], "sign")
        if len(token) > 65536 or len(sign) > 65536:
            raise ValueError()
    except (ValueError, TypeError):
        raise AppError(503, "arca_wsaa_ticket_context_invalid", "El contexto o la vigencia del ticket WSAA no coinciden con el requerimiento") from None
    return AccessTicket(token=token, sign=sign, generated_at=generated.astimezone(UTC), expires_at=expires.astimezone(UTC), certificate_fingerprint=credential.fingerprint, environment=environment, auth_scope=auth_scope)


class ArcaAuthService:
    """Short DB claims, network outside transactions, fenced durable publication.

    The caller must finish its fiscal transaction before requesting a ticket.
    A lost/uncertain WSAA renewal is never looped: its persisted retry boundary
    conservatively respects the possible twelve-hour TA that WSAA already issued.
    """
    def __init__(self, db: Session, registry: CredentialRegistry, provider, encryption_keys: TicketKeyring, *, transport=None, clock: Callable = utcnow, signer: Callable = sign_cms, owner_id: str | None = None, lease_seconds: int = 60):
        self.db, self.registry, self.provider, self.keys = db, registry, provider, encryption_keys
        self.repository = ArcaAuthRepository(db)
        self.transport = transport or HttpWsaaTransport()
        self.clock, self.signer = clock, signer
        self.owner_id = owner_id or uuid.uuid4().hex
        self.lease_seconds = max(30, min(lease_seconds, 300))

    @staticmethod
    def _identity(credential, binding):
        identity = {"certificate_fingerprint": credential.fingerprint, "environment": binding.environment, "service": "wsfe", "auth_scope": binding.auth_scope}
        return identity, hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _ticket_bytes(ticket):
        return json.dumps({"token": ticket.token, "sign": ticket.sign, "generated_at": ticket.generated_at.isoformat(), "expires_at": ticket.expires_at.isoformat(), "certificate_fingerprint": ticket.certificate_fingerprint, "environment": ticket.environment, "auth_scope": ticket.auth_scope, "service": ticket.service, "represented_cuit": ticket.represented_cuit}, sort_keys=True, separators=(",", ":")).encode()

    @staticmethod
    def _decode_ticket(raw, identity, now):
        try:
            payload = json.loads(raw)
            payload["generated_at"] = datetime.fromisoformat(payload["generated_at"])
            payload["expires_at"] = datetime.fromisoformat(payload["expires_at"])
            ticket = AccessTicket(**payload)
            if any(getattr(ticket, key) != value for key, value in identity.items()) or ticket.generated_at.tzinfo is None or ticket.expires_at.tzinfo is None or ticket.generated_at > now + timedelta(minutes=2) or ticket.expires_at <= now or not ticket.token or not ticket.sign:
                raise ValueError()
            return ticket
        except (TypeError, ValueError, KeyError):
            raise AppError(503, "arca_ticket_integrity_failed", "El ticket cifrado no corresponde al ámbito de autenticación vigente") from None

    def _grant(self, tenant_id, binding, represented_cuit, cache, ticket):
        ticket = replace(ticket, represented_cuit=represented_cuit)
        context = {"kind": "tenant_grant", "tenant_id": str(tenant_id), "reference": binding.reference, "represented_cuit": represented_cuit, "cache_key": cache.cache_key}
        encrypted, version, scope = self.keys.encrypt(self._ticket_bytes(ticket), context)
        grant = self.repository.get_tenant_grant(tenant_id, binding.reference, binding.environment, represented_cuit)
        if grant is None:
            grant = ArcaTenantTicketGrant(tenant_id=tenant_id, reference=binding.reference, environment=binding.environment, represented_cuit=represented_cuit)
            self.db.add(grant)
        grant.cache_id, grant.encrypted_ticket = cache.id, encrypted
        grant.encryption_key_version, grant.encryption_key_scope = version, scope
        grant.generated_at, grant.expires_at = ticket.generated_at, ticket.expires_at
        self.db.flush()
        return ticket

    def credential_status(self, tenant_id, reference, environment, represented_cuit):
        return self.registry.status(tenant_id, reference, environment, represented_cuit)

    def validate_credentials(self, tenant_id, reference, environment, represented_cuit):
        """Explicit offline provisioning check; never invoke from settings GET."""
        require_homologation(environment)
        binding = self.registry.authorize(tenant_id, reference, environment, represented_cuit)
        credential = validate_credential(self.provider.load(binding), binding, self.clock())
        return {"state": "locally_validated", "certificate_fingerprint": credential.fingerprint, "certificate_expires_at": credential.expires_at.isoformat(), "remote_validation": "pending", "delegation_validation": "pending", "production_enabled": False}

    def get_ticket(self, tenant_id, reference, environment, represented_cuit) -> AccessTicket:
        require_homologation(environment)
        binding = self.registry.authorize(tenant_id, reference, environment, represented_cuit)
        self.keys.ensure_ready()
        if self.db.new or self.db.dirty or self.db.deleted:
            raise AppError(409, "arca_auth_transaction_pending", "Finaliza la transacción fiscal antes de resolver credenciales u obtener un ticket")
        if hasattr(self.transport, "ensure_enabled"):
            self.transport.ensure_enabled(environment)
        material = self.provider.load(binding)
        credential = validate_credential(material, binding, self.clock())
        identity, cache_key = self._identity(credential, binding)
        context = {"kind": "auth_coordination", "cache_key": cache_key, **identity}
        try:
            cache = self.repository.lock_global_auth_scope(cache_key, **identity)
            # Secret resolution and a contended PostgreSQL row lock can outlast
            # a TA or certificate. Never return a ticket or start a new lease
            # using the time captured before those waits.
            now = self.clock()
            if now.tzinfo is None:
                raise AppError(503, "arca_clock_invalid", "El reloj fiscal requiere zona horaria")
            if credential.expires_at <= now:
                raise AppError(409, "arca_certificate_not_current", "El certificado fiscal venció mientras se coordinaba la autenticación")
            if cache.encrypted_ticket is not None and cache.expires_at is not None and aware(cache.expires_at) > now:
                ticket = self._decode_ticket(self.keys.decrypt(cache.encrypted_ticket, cache.encryption_key_version, cache.encryption_key_scope, context), identity, now)
                # Lazy key rotation re-encrypts only this scope; no WSAA request.
                if cache.encryption_key_version != self.keys.active_version:
                    cache.encrypted_ticket, cache.encryption_key_version, cache.encryption_key_scope = self.keys.encrypt(self._ticket_bytes(ticket), context)
                result = self._grant(tenant_id, binding, represented_cuit, cache, ticket)
                self.db.commit()
                return result
            if cache.state == "renewing":
                if cache.lease_expires_at is not None and aware(cache.lease_expires_at) > now:
                    raise AppError(409, "arca_wsaa_renewal_in_progress", "Otro proceso está obteniendo el ticket; reintenta después del claim vigente")
                # An expired worker may have reached WSAA. We cannot retrieve its
                # TA using another login, nor assume expiry means no remote call.
                cache.state, cache.diagnostic_code = "backoff", "arca_wsaa_renewal_outcome_unknown"
                # The old TRA could be accepted up to its own expiry. A TA
                # created at that boundary remains valid for its full lifetime.
                cache.retry_not_before = aware(cache.last_request_at or now) + TRA_CLOCK_WINDOW + TICKET_MAX_LIFETIME
                cache.fence += 1
                cache.lease_owner = cache.lease_expires_at = None
                self.db.commit()
                raise AppError(503, "arca_wsaa_renewal_outcome_unknown", "La autenticación anterior quedó incierta; se conserva el bloqueo de renovación programado")
            if cache.state == "blocked":
                raise AppError(503, cache.diagnostic_code or "arca_wsaa_configuration_blocked", "La autenticación fiscal requiere corregir su configuración antes de renovar")
            if cache.retry_not_before is not None and aware(cache.retry_not_before) > now:
                raise AppError(503, cache.diagnostic_code or "arca_wsaa_retry_scheduled", "La autenticación fiscal tiene un reintento pendiente; no se enviará otra solicitud todavía")
            cache.state, cache.lease_owner = "renewing", self.owner_id
            cache.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
            cache.fence += 1
            cache.last_request_at = now
            cache_id, fence = cache.id, cache.fence
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        dispatched = False
        try:
            tra, unique_id = build_tra(now)
            cms = self.signer(tra, credential)
            dispatched = True
            response = self.transport.login_cms(environment, base64.b64encode(cms).decode("ascii"))
            ticket = parse_wsaa_response(response, now=self.clock(), credential=credential, environment=environment, auth_scope=binding.auth_scope, unique_id=unique_id)
            encrypted, version, scope = self.keys.encrypt(self._ticket_bytes(ticket), context)
            published = self.repository.publish_global_ticket(cache_id, self.owner_id, fence, self.clock(), state="ready", encrypted_ticket=encrypted, encryption_key_version=version, encryption_key_scope=scope, generated_at=ticket.generated_at, expires_at=ticket.expires_at, retry_not_before=None, diagnostic_code=None)
            if not published:
                raise AppError(409, "arca_wsaa_claim_fenced", "El claim de autenticación venció o fue reemplazado; el proceso anterior no puede publicar")
            cache = self.repository.lock_global_auth_scope(cache_key, **identity)
            result = self._grant(tenant_id, binding, represented_cuit, cache, ticket)
            self.db.commit()
            return result
        except Exception as error:
            self.db.rollback()
            if isinstance(error, WsaaFault):
                retryable = error.fault_code.startswith("wsaa.") or error.fault_code == "wsn.unavailable"
                already = error.fault_code == "coe.alreadyAuthenticated"
                state = "backoff" if retryable or already else "blocked"
                retry_at = self.clock() + (timedelta(seconds=60) if retryable else TICKET_MAX_LIFETIME) if retryable or already else None
                code = error.code
            elif isinstance(error, AppError) and error.code == "arca_wsaa_claim_fenced":
                raise
            elif not dispatched:
                state, retry_at = "blocked", None
                code = error.code if isinstance(error, AppError) else "arca_cms_signature_failed"
            else:
                state, retry_at, code = "backoff", self.clock() + TICKET_MAX_LIFETIME, "arca_wsaa_renewal_outcome_unknown"
            try:
                self.repository.fail_global_claim(cache_id, self.owner_id, fence, state=state, retry_not_before=retry_at, diagnostic_code=code)
                self.db.commit()
            except Exception:
                self.db.rollback()
            # Never attach an unsafe transport/crypto exception to API errors.
            raise AppError(503, code, "La autenticación fiscal no pudo confirmarse; consulta el diagnóstico y el reintento programado") from None

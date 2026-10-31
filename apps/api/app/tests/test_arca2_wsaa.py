"""Real RSA/SHA1 CMS, secure SOAP parsing and durable encrypted WSAA state.

Every certificate, private key, ticket and encryption key here is synthetic.
Transport always runs the production serializer/parser through httpx.MockTransport.
Uninjected network is blocked within this file's fixture scope.
"""
import base64
import json
import os
import socket
import subprocess
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.arca_auth import ArcaAuthCache, ArcaTenantTicketGrant
from app.models.tenant import Tenant
from app.services.arca_credentials import (
    CredentialBinding, CredentialMaterial, CredentialRegistry,
    LocalCredentialProvider, SecretManagerCredentialProvider,
    SyntheticCredentialProvider, external_server_file, validate_credential,
)
from app.services.arca_wsaa import (
    ArcaAuthService, HttpWsaaTransport, SOAP_NAMESPACE, WSAA_NAMESPACE,
    TicketEncryptionKey, TicketKeyring, build_tra, parse_wsaa_response, sign_cms,
)


NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
CUIT = "20123456786"
DELEGATE = "30712345671"
TOKEN = "synthetic-token-do-not-log"
SIGN = "synthetic-sign-do-not-log"


@pytest.fixture(autouse=True)
def no_uninjected_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("WSAA tests must use explicitly injected transports")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


def _material(*, now=NOW, not_before=None, not_after=None):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME, "AR"), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Synthetic test"), x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic authentication certificate"), x509.NameAttribute(NameOID.SERIAL_NUMBER, "CUIT " + DELEGATE)])
    certificate = x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(not_before or now - timedelta(days=1)).not_valid_after(not_after or now + timedelta(days=30)).sign(key, hashes.SHA256())
    material = CredentialMaterial(certificate.public_bytes(serialization.Encoding.PEM), key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return material, certificate


def _binding(tenant_id, **changes):
    values = dict(reference="opaque://synthetic/credential", tenant_id=tenant_id, environment="homologation", represented_cuits=(CUIT,), auth_scope="synthetic-authorized-delegation", provider="synthetic", certificate_resource="synthetic-certificate", private_key_resource="synthetic-key")
    values.update(changes)
    return CredentialBinding(**values)


def _keyring(version="v1", **old_keys):
    return TicketKeyring({**old_keys, version: TicketEncryptionKey("synthetic-deployment", os.urandom(32))}, version)


def _soap_ta(certificate, now, unique_id, *, generation=None, expiry=None, source=None, destination=None, token=TOKEN, sign=SIGN):
    ticket = ET.Element("loginTicketResponse", version="1.0")
    header = ET.SubElement(ticket, "header")
    for name, value in (("source", source or "cn=wsaahomo,o=afip,c=ar,serialNumber=CUIT 33693450239"), ("destination", destination or certificate.subject.rfc4514_string()), ("uniqueId", str(unique_id)), ("generationTime", (generation or now - timedelta(seconds=1)).isoformat()), ("expirationTime", (expiry or now + timedelta(hours=11)).isoformat())):
        ET.SubElement(header, name).text = value
    credentials = ET.SubElement(ticket, "credentials")
    ET.SubElement(credentials, "token").text = token
    ET.SubElement(credentials, "sign").text = sign
    soap = ET.Element(f"{{{SOAP_NAMESPACE}}}Envelope")
    body = ET.SubElement(soap, f"{{{SOAP_NAMESPACE}}}Body")
    response = ET.SubElement(body, f"{{{WSAA_NAMESPACE}}}loginCmsResponse")
    ET.SubElement(response, f"{{{WSAA_NAMESPACE}}}loginCmsReturn").text = ET.tostring(ticket, encoding="unicode")
    return ET.tostring(soap)


def _soap_fault(code):
    root = ET.Element(f"{{{SOAP_NAMESPACE}}}Envelope")
    fault = ET.SubElement(ET.SubElement(root, f"{{{SOAP_NAMESPACE}}}Body"), f"{{{SOAP_NAMESPACE}}}Fault")
    ET.SubElement(fault, "faultcode").text = code
    ET.SubElement(fault, "faultstring").text = f"Untrusted remote echo {TOKEN} {SIGN}"
    return ET.tostring(root)


class SoapLaboratory:
    def __init__(self, certificate, clock):
        self.certificate, self.clock = certificate, clock
        self.requests = []
        self.mode = "success"
        self.before_response = None
        self.override = None

    def handle(self, request):
        assert str(request.url) == "https://wsaahomo.afip.gov.ar/ws/services/LoginCms"
        assert request.method == "POST" and request.headers["SOAPAction"] == '""'
        root = ET.fromstring(request.content)
        cms = base64.b64decode(root.find(f".//{{{WSAA_NAMESPACE}}}in0").text, validate=True)
        # This verifies an actual embedded CMS signature and extracts the exact
        # TRA signed by OpenSSL; no synthetic Base64 stand-in is accepted.
        verified = subprocess.run(["openssl", "cms", "-verify", "-inform", "DER", "-binary", "-noverify"], input=cms, capture_output=True, check=False)
        assert verified.returncode == 0
        tra = ET.fromstring(verified.stdout)
        assert tra.findtext("service") == "wsfe"
        unique_id = int(tra.findtext("header/uniqueId"))
        self.requests.append({"unique_id": unique_id, "generation": tra.findtext("header/generationTime")})
        if self.before_response:
            self.before_response()
        if self.mode == "timeout":
            raise httpx.ReadTimeout(f"Unsafe remote text {TOKEN}", request=request)
        if self.mode == "redirect":
            return httpx.Response(302, headers={"Location": "https://untrusted.example"})
        if self.mode != "success":
            return httpx.Response(500, content=_soap_fault(self.mode))
        return httpx.Response(200, content=self.override or _soap_ta(self.certificate, self.clock(), unique_id))


@pytest.fixture
def auth_case(db_session, tenant):
    material, certificate = _material()
    binding = _binding(tenant.id)
    clock = SimpleNamespace(value=NOW)
    now = lambda: clock.value
    laboratory = SoapLaboratory(certificate, now)
    provider = SyntheticCredentialProvider({binding.reference: material})
    registry = CredentialRegistry([binding])
    keyring = _keyring()
    transport = HttpWsaaTransport(transport=httpx.MockTransport(laboratory.handle))
    service = ArcaAuthService(db_session, registry, provider, keyring, transport=transport, clock=now)
    return SimpleNamespace(db=db_session, tenant=tenant, material=material, certificate=certificate, binding=binding, clock=clock, now=now, laboratory=laboratory, provider=provider, registry=registry, keyring=keyring, transport=transport, service=service)


def _ticket(case, service=None, *, tenant_id=None, reference=None, cuit=CUIT, environment="homologation"):
    return (service or case.service).get_ticket(tenant_id or case.tenant.id, reference or case.binding.reference, environment, cuit)


def test_tra_has_timezone_bounded_dates_and_unsigned_unique_id():
    raw, unique = build_tra(NOW, unique_id=0xFFFFFFFF)
    root = ET.fromstring(raw)
    assert unique == 0xFFFFFFFF
    assert root.findtext("service") == "wsfe"
    assert datetime.fromisoformat(root.findtext("header/generationTime")) == NOW - timedelta(minutes=5)
    assert datetime.fromisoformat(root.findtext("header/expirationTime")) == NOW + timedelta(minutes=5)
    with pytest.raises(AppError):
        build_tra(NOW.replace(tzinfo=None))
    with pytest.raises(AppError):
        build_tra(NOW, unique_id=2 ** 32)


def test_cms_is_real_embedded_rsa_sha1_and_never_puts_keys_in_argv(auth_case, monkeypatch):
    case = auth_case
    credential = validate_credential(case.material, case.binding, NOW)
    tra, _unique = build_tra(NOW, unique_id=17)
    original = subprocess.run
    arguments = []
    def capture(args, **kwargs):
        arguments.append(args)
        return original(args, **kwargs)
    monkeypatch.setattr(subprocess, "run", capture)
    cms = sign_cms(tra, credential)
    verified = original(["openssl", "cms", "-verify", "-inform", "DER", "-binary", "-noverify"], input=cms, capture_output=True, check=False)
    assert verified.returncode == 0 and verified.stdout == tra
    inspected = original(["openssl", "cms", "-cmsout", "-print", "-inform", "DER"], input=cms, capture_output=True, check=False)
    assert b"algorithm: sha1" in inspected.stdout
    assert len(arguments) == 1
    assert "sha1" in arguments[0]
    assert "PRIVATE KEY" not in " ".join(arguments[0])
    assert any(argument.startswith("/proc/self/fd/") for argument in arguments[0])
    assert case.material.private_key_pem not in cms


def test_cms_failure_closes_every_key_descriptor_and_hides_process_output(auth_case, monkeypatch, caplog):
    credential = validate_credential(auth_case.material, auth_case.binding, NOW)
    tra, _unique = build_tra(NOW)
    created = []
    original_pipe = os.pipe
    def pipe():
        descriptors = original_pipe()
        created.extend(descriptors)
        return descriptors
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("synthetic signer", 10, output=TOKEN.encode(), stderr=auth_case.material.private_key_pem)
    monkeypatch.setattr(os, "pipe", pipe)
    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(AppError) as error:
        sign_cms(tra, credential)
    assert error.value.code == "arca_cms_signature_failed"
    assert TOKEN not in str(error.value) and "PRIVATE KEY" not in str(error.value)
    assert len(created) == 4
    for descriptor in created:
        with pytest.raises(OSError):
            os.fstat(descriptor)
    assert TOKEN not in caplog.text and "PRIVATE KEY" not in caplog.text


def test_unsupported_private_key_algorithm_has_only_a_sanitized_diagnostic(auth_case, monkeypatch):
    from cryptography.exceptions import UnsupportedAlgorithm
    def unsupported(*_args, **_kwargs):
        raise UnsupportedAlgorithm("Untrusted provider output " + TOKEN)
    monkeypatch.setattr(serialization, "load_pem_private_key", unsupported)
    with pytest.raises(AppError) as error:
        validate_credential(auth_case.material, auth_case.binding, NOW)
    assert error.value.code == "arca_credential_invalid"
    assert TOKEN not in str(error.value)


def test_tickets_survive_service_restart_encrypted_without_another_login(auth_case, caplog):
    case = auth_case
    ticket = _ticket(case)
    assert ticket.token == TOKEN and ticket.sign == SIGN
    assert ticket.represented_cuit == CUIT and ticket.service == "wsfe"
    assert TOKEN not in repr(ticket) and SIGN not in repr(ticket)
    fresh = ArcaAuthService(case.db, case.registry, case.provider, case.keyring, transport=case.transport, clock=case.now)
    assert _ticket(case, fresh).token == TOKEN
    assert len(case.laboratory.requests) == 1
    cache = case.db.scalar(select(ArcaAuthCache))
    grant = case.db.scalar(select(ArcaTenantTicketGrant).where(ArcaTenantTicketGrant.tenant_id == case.tenant.id))
    assert cache.state == "ready" and cache.fence == 1
    assert TOKEN.encode() not in cache.encrypted_ticket and SIGN.encode() not in cache.encrypted_ticket
    assert TOKEN.encode() not in grant.encrypted_ticket and SIGN.encode() not in grant.encrypted_ticket
    assert cache.encrypted_ticket != grant.encrypted_ticket
    assert "token" not in ArcaAuthCache.__table__.columns and "sign" not in ArcaAuthCache.__table__.columns
    assert TOKEN not in caplog.text and SIGN not in caplog.text


def test_shared_certificate_uses_one_global_ta_but_distinct_tenant_bound_grants(auth_case, other_tenant):
    case = auth_case
    delegated = _binding(other_tenant.id, reference="opaque://other/credential", represented_cuits=(DELEGATE,))
    registry = CredentialRegistry([case.binding, delegated])
    provider = SyntheticCredentialProvider({case.binding.reference: case.material, delegated.reference: case.material})
    service = ArcaAuthService(case.db, registry, provider, case.keyring, transport=case.transport, clock=case.now)
    assert _ticket(case, service).represented_cuit == CUIT
    other = _ticket(case, service, tenant_id=other_tenant.id, reference=delegated.reference, cuit=DELEGATE)
    assert other.represented_cuit == DELEGATE
    assert len(case.laboratory.requests) == 1
    assert len(list(case.db.scalars(select(ArcaAuthCache)))) == 1
    grants = list(case.db.scalars(select(ArcaTenantTicketGrant)))
    assert len(grants) == 2 and grants[0].encrypted_ticket != grants[1].encrypted_ticket
    with pytest.raises(AppError) as error:
        _ticket(case, service, tenant_id=other_tenant.id)
    assert error.value.status_code == 404
    assert len(case.laboratory.requests) == 1


@pytest.mark.parametrize("altered", [{"tenant_id": "other"}, {"environment": "production"}, {"auth_scope": "other"}, {"represented_cuit": DELEGATE}])
def test_authenticated_encryption_rejects_scope_swapping(auth_case, altered):
    context = {"tenant_id": str(auth_case.tenant.id), "environment": "homologation", "auth_scope": "one", "represented_cuit": CUIT}
    ciphertext, version, scope = auth_case.keyring.encrypt(TOKEN.encode(), context)
    with pytest.raises(AppError) as error:
        auth_case.keyring.decrypt(ciphertext, version, scope, {**context, **altered})
    assert error.value.code == "arca_ticket_integrity_failed"
    assert TOKEN not in str(error.value)


def test_key_rotation_reencrypts_cached_ta_and_never_requests_a_second_valid_ticket(auth_case):
    case = auth_case
    _ticket(case)
    previous = case.db.scalar(select(ArcaAuthCache)).encrypted_ticket
    rotated = _keyring("v2", **case.keyring.keys)
    fresh = ArcaAuthService(case.db, case.registry, case.provider, rotated, transport=case.transport, clock=case.now)
    assert _ticket(case, fresh).token == TOKEN
    cache = case.db.scalar(select(ArcaAuthCache))
    assert cache.encryption_key_version == "v2" and cache.encrypted_ticket != previous
    assert len(case.laboratory.requests) == 1
    assert case.db.scalar(select(ArcaTenantTicketGrant).where(ArcaTenantTicketGrant.tenant_id == case.tenant.id)).encryption_key_version == "v2"


def test_missing_decryption_key_does_not_trigger_reauthentication(auth_case):
    case = auth_case
    _ticket(case)
    wrong = ArcaAuthService(case.db, case.registry, case.provider, _keyring("v2"), transport=case.transport, clock=case.now)
    with pytest.raises(AppError) as error:
        _ticket(case, wrong)
    assert error.value.code == "arca_ticket_key_version_unavailable"
    assert len(case.laboratory.requests) == 1


def test_same_certificate_cannot_request_a_second_ta_under_another_server_scope(auth_case):
    case = auth_case
    _ticket(case)
    alternate = replace(case.binding, reference="opaque://alternate/reference", auth_scope="separate-server-scope", certificate_resource="different-resource-same-certificate", private_key_resource="different-key-resource")
    provider = SyntheticCredentialProvider({alternate.reference: case.material})
    service = ArcaAuthService(case.db, CredentialRegistry([alternate]), provider, case.keyring, transport=case.transport, clock=case.now)
    with pytest.raises(AppError) as error:
        _ticket(case, service, reference=alternate.reference)
    assert error.value.code == "arca_auth_scope_conflict"
    assert error.value.status_code == 409
    assert len(case.laboratory.requests) == 1
    assert len(list(case.db.scalars(select(ArcaAuthCache)))) == 1


def test_certificate_rotation_changes_only_its_authentication_scope(auth_case):
    case = auth_case
    first = _ticket(case)
    replacement, certificate = _material()
    case.provider.materials[case.binding.reference] = replacement
    case.laboratory.certificate = certificate
    second = _ticket(case)
    assert second.certificate_fingerprint != first.certificate_fingerprint
    rows = list(case.db.scalars(select(ArcaAuthCache)))
    assert len(rows) == 2
    assert all(row.state == "ready" for row in rows)
    assert len(case.laboratory.requests) == 2
    assert case.db.scalar(select(ArcaTenantTicketGrant).where(ArcaTenantTicketGrant.tenant_id == case.tenant.id)).cache_id == next(row.id for row in rows if row.certificate_fingerprint == second.certificate_fingerprint)


@pytest.mark.parametrize("reason", ["expired", "future", "mismatch", "fingerprint"])
def test_offline_validation_rejects_invalid_credentials_without_remote_calls(auth_case, reason):
    case = auth_case
    material, binding = case.material, case.binding
    if reason == "expired":
        material, _certificate = _material(not_before=NOW - timedelta(days=3), not_after=NOW - timedelta(days=1))
    elif reason == "future":
        material, _certificate = _material(not_before=NOW + timedelta(days=1), not_after=NOW + timedelta(days=3))
    elif reason == "mismatch":
        another, _certificate = _material()
        material = CredentialMaterial(material.certificate_pem, another.private_key_pem)
    else:
        binding = replace(binding, expected_fingerprint="0" * 64)
    with pytest.raises(AppError):
        validate_credential(material, binding, NOW)
    assert not case.laboratory.requests
    # A delegated represented CUIT is accepted offline; this does not claim that
    # ARCA has granted the delegation or certificate trust.
    valid = validate_credential(case.material, case.binding, NOW)
    assert valid.fingerprint and DELEGATE in valid.subject_dn


def test_production_and_unprovisioned_scopes_are_rejected_before_secret_resolution(auth_case, other_tenant):
    case = auth_case
    for parameters, expected in (({"environment": "production"}, "arca_production_disabled"), ({"tenant_id": other_tenant.id}, "arca_credential_reference_not_found"), ({"cuit": DELEGATE}, "arca_credential_reference_not_found")):
        with pytest.raises(AppError) as error:
            _ticket(case, **parameters)
        assert error.value.code == expected
    assert case.provider.loads == 0 and case.laboratory.requests == []
    assert case.service.credential_status(case.tenant.id, case.binding.reference, "homologation", CUIT)["state"] == "configured"
    assert case.service.credential_status(case.tenant.id, case.binding.reference, "production", CUIT)["state"] == "production_blocked"
    assert case.provider.loads == 0


def test_default_transport_and_missing_keyring_fail_before_resolving_secrets(auth_case):
    case = auth_case
    for transport, keyring, code in ((HttpWsaaTransport(), case.keyring, "arca_homologation_external_disabled"), (case.transport, TicketKeyring({}, None), "arca_ticket_encryption_not_configured")):
        service = ArcaAuthService(case.db, case.registry, case.provider, keyring, transport=transport, clock=case.now)
        with pytest.raises(AppError) as error:
            _ticket(case, service)
        assert error.value.code == code
    assert case.provider.loads == 0


def test_authentication_cannot_commit_an_unfinished_business_transaction(auth_case):
    case = auth_case
    case.tenant.name = "Pending synthetic business edit"
    with pytest.raises(AppError) as error:
        _ticket(case)
    assert error.value.code == "arca_auth_transaction_pending"
    assert case.provider.loads == 0 and case.laboratory.requests == []
    case.db.rollback()


def test_http_transport_close_is_safe_after_its_per_call_pool_was_closed(auth_case):
    case = auth_case
    assert _ticket(case).token == TOKEN
    case.transport.close()
    case.transport.close()


@pytest.mark.parametrize("mode", ["coe.notAuthorized", "coe.alreadyAuthenticated", "wsaa.unavailable", "timeout", "redirect"])
def test_errors_are_sanitized_and_backoffs_are_persisted_without_retry_loops(auth_case, caplog, mode):
    case = auth_case
    case.laboratory.mode = mode
    with pytest.raises(AppError) as first:
        _ticket(case)
    assert TOKEN not in str(first.value) and SIGN not in str(first.value)
    row = case.db.scalar(select(ArcaAuthCache))
    if mode == "coe.notAuthorized":
        assert row.state == "blocked" and row.retry_not_before is None
    else:
        assert row.state == "backoff"
        expected = timedelta(seconds=60) if mode == "wsaa.unavailable" else timedelta(hours=12)
        assert row.retry_not_before.replace(tzinfo=UTC) == NOW + expected
    restarted = ArcaAuthService(case.db, case.registry, case.provider, case.keyring, transport=case.transport, clock=case.now)
    with pytest.raises(AppError):
        _ticket(case, restarted)
    assert len(case.laboratory.requests) == 1
    assert row.encrypted_ticket is None
    assert TOKEN not in caplog.text and SIGN not in caplog.text


def test_retry_is_allowed_only_after_its_durable_deadline(auth_case):
    case = auth_case
    case.laboratory.mode = "wsaa.unavailable"
    with pytest.raises(AppError):
        _ticket(case)
    case.clock.value += timedelta(seconds=61)
    case.laboratory.mode = "success"
    assert _ticket(case).token == TOKEN
    assert len(case.laboratory.requests) == 2


def test_ticket_expiry_is_checked_after_waiting_for_the_database_lock(auth_case, monkeypatch):
    case = auth_case
    original = _ticket(case)
    case.clock.value = original.expires_at - timedelta(seconds=1)
    lock = case.service.repository.lock_global_auth_scope
    def delayed_lock(*args, **kwargs):
        row = lock(*args, **kwargs)
        case.clock.value += timedelta(seconds=2)
        return row
    monkeypatch.setattr(case.service.repository, "lock_global_auth_scope", delayed_lock)
    renewed = _ticket(case)
    assert renewed.expires_at > original.expires_at
    assert renewed.expires_at > case.now()
    assert len(case.laboratory.requests) == 2


def test_certificate_expiry_during_the_database_wait_blocks_login(auth_case, monkeypatch):
    case = auth_case
    case.clock.value = case.certificate.not_valid_after_utc - timedelta(seconds=1)
    lock = case.service.repository.lock_global_auth_scope
    def delayed_lock(*args, **kwargs):
        row = lock(*args, **kwargs)
        case.clock.value += timedelta(seconds=2)
        return row
    monkeypatch.setattr(case.service.repository, "lock_global_auth_scope", delayed_lock)
    with pytest.raises(AppError) as error:
        _ticket(case)
    assert error.value.code == "arca_certificate_not_current"
    assert not case.laboratory.requests


def test_an_expired_worker_is_fenced_and_does_not_overwrite_or_duplicate_login(auth_case):
    case = auth_case
    fenced_codes = []
    def expire_and_recover():
        case.clock.value += timedelta(seconds=61)
        with Session(case.db.get_bind()) as another:
            contender = ArcaAuthService(another, case.registry, case.provider, case.keyring, transport=case.transport, clock=case.now)
            with pytest.raises(AppError) as error:
                _ticket(case, contender)
            fenced_codes.append(error.value.code)
    case.laboratory.before_response = expire_and_recover
    with pytest.raises(AppError) as error:
        _ticket(case)
    assert error.value.code == "arca_wsaa_claim_fenced"
    assert fenced_codes == ["arca_wsaa_renewal_outcome_unknown"]
    row = case.db.scalar(select(ArcaAuthCache))
    assert row.state == "backoff" and row.fence == 2 and row.encrypted_ticket is None
    assert len(case.laboratory.requests) == 1


@pytest.mark.parametrize("changes", [{"source": "cn=wsaa,o=afip,c=ar,serialNumber=CUIT 33693450239"}, {"destination": "cn=other"}, {"generation": NOW + timedelta(minutes=4)}, {"expiry": NOW - timedelta(seconds=1)}, {"expiry": NOW + timedelta(hours=20)}, {"token": ""}])
def test_ticket_parser_rejects_wrong_identity_clock_or_incomplete_credentials(auth_case, changes):
    case = auth_case
    credential = validate_credential(case.material, case.binding, NOW)
    with pytest.raises(AppError):
        parse_wsaa_response(_soap_ta(case.certificate, NOW, 7, **changes), now=NOW, credential=credential, environment="homologation", auth_scope=case.binding.auth_scope, unique_id=7)


def test_parser_rejects_entities_oversized_and_malformed_xml(auth_case):
    case = auth_case
    credential = validate_credential(case.material, case.binding, NOW)
    for raw in (b'<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///etc/passwd">]><x>&secret;</x>', b"<invalid>", b"x" * (1024 * 1024 + 1)):
        with pytest.raises(AppError):
            parse_wsaa_response(raw, now=NOW, credential=credential, environment="homologation", auth_scope=case.binding.auth_scope, unique_id=7)


def test_local_provider_is_opt_in_and_rejects_traversal_symlinks_and_repository_files(auth_case, tmp_path):
    case = auth_case
    certificate, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    certificate.write_bytes(case.material.certificate_pem)
    key.write_bytes(case.material.private_key_pem)
    certificate.chmod(0o600)
    key.chmod(0o600)
    binding = replace(case.binding, provider="local", certificate_resource="cert.pem", private_key_resource="key.pem")
    with pytest.raises(AppError) as error:
        LocalCredentialProvider(tmp_path).load(binding)
    assert error.value.code == "arca_local_credentials_disabled"
    assert LocalCredentialProvider(tmp_path, enabled=True).load(binding).certificate_pem == case.material.certificate_pem
    for resource in ("../key.pem", str(key)):
        with pytest.raises(AppError):
            LocalCredentialProvider(tmp_path, enabled=True).load(replace(binding, private_key_resource=resource))
    (tmp_path / "symlink.pem").symlink_to(key)
    with pytest.raises(AppError):
        LocalCredentialProvider(tmp_path, enabled=True).load(replace(binding, private_key_resource="symlink.pem"))
    with pytest.raises(AppError):
        external_server_file(__file__, secret=True)


def test_secret_manager_uses_only_server_bound_resources_and_is_disabled_by_default(auth_case):
    case = auth_case
    certificate_resource = "projects/synthetic-project/secrets/certificate/versions/1"
    key_resource = "projects/synthetic-project/secrets/private-key/versions/1"
    requested = []
    class Client:
        def access_secret_version(self, *, request):
            requested.append(request["name"])
            return SimpleNamespace(payload=SimpleNamespace(data={certificate_resource: case.material.certificate_pem, key_resource: case.material.private_key_pem}[request["name"]]))
    binding = replace(case.binding, provider="secret_manager", certificate_resource=certificate_resource, private_key_resource=key_resource)
    with pytest.raises(AppError):
        SecretManagerCredentialProvider(Client()).load(binding)
    assert requested == []
    provider = SecretManagerCredentialProvider(Client(), enabled=True)
    assert provider.load(binding).certificate_pem == case.material.certificate_pem
    assert requested == [certificate_resource, key_resource]
    with pytest.raises(AppError):
        provider.load(replace(binding, private_key_resource="https://untrusted.example/key"))
    assert "https://untrusted.example/key" not in requested


def test_server_files_provision_keys_and_registry_explicitly_without_defaults(auth_case, tmp_path, monkeypatch):
    case = auth_case
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps([{"reference": case.binding.reference, "tenant_id": str(case.tenant.id), "environment": "homologation", "represented_cuits": [CUIT], "auth_scope": case.binding.auth_scope, "provider": "local", "certificate_resource": "cert.pem", "private_key_resource": "key.pem"}]))
    key_path = tmp_path / "keyring.json"
    key_path.write_text(json.dumps({"active_version": "v1", "keys": {"v1": {"scope": "synthetic", "key_b64": base64.b64encode(os.urandom(32)).decode()}}}))
    key_path.chmod(0o600)
    monkeypatch.setenv("ARCA_CREDENTIAL_REGISTRY_FILE", str(registry_path))
    monkeypatch.setenv("ARCA_TICKET_KEYRING_FILE", str(key_path))
    assert CredentialRegistry.from_server_settings().authorize(case.tenant.id, case.binding.reference, "homologation", CUIT).provider == "local"
    TicketKeyring.from_server_settings().ensure_ready()
    monkeypatch.delenv("ARCA_CREDENTIAL_REGISTRY_FILE")
    monkeypatch.delenv("ARCA_TICKET_KEYRING_FILE")
    assert CredentialRegistry.from_server_settings().status(case.tenant.id, case.binding.reference, "homologation", CUIT)["state"] == "pending"
    with pytest.raises(AppError):
        TicketKeyring.from_server_settings().ensure_ready()

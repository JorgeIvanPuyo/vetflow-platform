"""Server-owned credential bindings. API input is never a resource/path selector.

Offline validation proves possession of a matching, currently valid RSA key pair;
it does not verify ARCA trust, business habilitation or fiscal delegation.
"""
from __future__ import annotations

import hmac
import json
import os
import re
import stat
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping, Protocol

from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.errors import AppError
from app.schemas.fiscal_issuer import normalize_cuit


OPAQUE_REFERENCE = re.compile(r"^opaque://[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
SECRET_RESOURCE = re.compile(r"^projects/[A-Za-z0-9_-]+/secrets/[A-Za-z0-9_-]+/versions/(?:[1-9][0-9]*|latest)$")
MAX_CREDENTIAL_BYTES = 128 * 1024


def require_homologation(environment: str) -> None:
    # This must precede registry lookup, secret resolution and client creation.
    if environment != "homologation":
        raise AppError(409, "arca_production_disabled", "La emisión y autenticación productivas permanecen bloqueadas")


def _repository_root() -> Path:
    source = Path(__file__).resolve()
    for parent in source.parents:
        if (parent / "apps" / "api" / "app").is_dir():
            return parent
    return source.parents[2]  # /app in the development image.


def external_server_file(path: str | Path, *, secret: bool = False) -> Path:
    """Only explicit regular files outside the checkout, with no symlink hops."""
    candidate = Path(path)
    if not candidate.is_absolute():
        raise AppError(503, "arca_server_configuration_invalid", "La configuración fiscal del servidor no es válida")
    try:
        resolved = candidate.resolve(strict=True)
        if resolved.is_relative_to(_repository_root()) or not resolved.is_file():
            raise ValueError()
        for parent in (candidate, *candidate.parents):
            if parent.is_symlink():
                raise ValueError()
        if secret and stat.S_IMODE(resolved.stat().st_mode) & 0o077:
            raise ValueError()
    except (OSError, ValueError):
        raise AppError(503, "arca_server_configuration_invalid", "La configuración fiscal del servidor no es válida") from None
    return resolved


@dataclass(frozen=True)
class CredentialBinding:
    reference: str
    tenant_id: uuid.UUID
    environment: str
    represented_cuits: tuple[str, ...]
    auth_scope: str
    provider: str
    certificate_resource: str
    private_key_resource: str
    password_resource: str | None = None
    expected_fingerprint: str | None = None

    def __post_init__(self):
        if not OPAQUE_REFERENCE.fullmatch(self.reference) or self.environment not in {"homologation", "production"} or not re.fullmatch(r"[A-Za-z0-9._:-]{1,120}", self.auth_scope):
            raise ValueError("Invalid server credential binding")
        if not self.represented_cuits or any(normalize_cuit(value) != value for value in self.represented_cuits):
            raise ValueError("Invalid represented fiscal identity")
        if self.provider not in {"secret_manager", "local", "synthetic"}:
            raise ValueError("Invalid credential provider")
        if self.expected_fingerprint and not re.fullmatch(r"[a-f0-9]{64}", self.expected_fingerprint):
            raise ValueError("Invalid certificate fingerprint")


class CredentialRegistry:
    def __init__(self, bindings=()):
        self._bindings: dict[tuple[uuid.UUID, str, str], CredentialBinding] = {}
        scopes: dict[tuple[str, str, str], str] = {}
        for binding in bindings:
            key = (binding.tenant_id, binding.reference, binding.environment)
            if key in self._bindings:
                raise ValueError("Duplicate credential reference")
            # One physical credential resource must not acquire multiple auth
            # scopes accidentally, which would duplicate WSAA ticket requests.
            identity = (binding.provider, binding.certificate_resource, binding.environment)
            if identity in scopes and scopes[identity] != binding.auth_scope:
                raise ValueError("Ambiguous authentication scope")
            scopes[identity] = binding.auth_scope
            self._bindings[key] = binding

    @classmethod
    def from_server_settings(cls) -> CredentialRegistry:
        path = os.getenv("ARCA_CREDENTIAL_REGISTRY_FILE")
        if not path:
            return cls()
        try:
            contents = external_server_file(path).read_bytes()
            if len(contents) > 1024 * 1024:
                raise ValueError()
            rows = json.loads(contents)
            if not isinstance(rows, list):
                raise ValueError()
            bindings = []
            for row in rows:
                row = dict(row)
                row["tenant_id"] = uuid.UUID(row["tenant_id"])
                row["represented_cuits"] = tuple(row["represented_cuits"])
                # Test providers can never be enabled from deployed config.
                if row["provider"] == "synthetic":
                    raise ValueError()
                bindings.append(CredentialBinding(**row))
            return cls(bindings)
        except (OSError, ValueError, TypeError, KeyError):
            raise AppError(503, "arca_server_configuration_invalid", "El registro fiscal del servidor no es válido") from None

    def authorize(self, tenant_id: uuid.UUID, reference: str, environment: str, represented_cuit: str) -> CredentialBinding:
        require_homologation(environment)
        binding = self._bindings.get((tenant_id, reference, environment))
        if binding is None or represented_cuit not in binding.represented_cuits:
            raise AppError(404, "arca_credential_reference_not_found", "La referencia fiscal no está provisionada para este emisor y ambiente")
        return binding

    def status(self, tenant_id: uuid.UUID, reference: str | None, environment: str, represented_cuit: str | None) -> dict:
        # Settings GET never resolves a private key or contacts a provider.
        if environment != "homologation":
            return {"state": "production_blocked", "configured": False, "remote_validation": "pending", "diagnostic_code": "arca_production_disabled"}
        try:
            binding = self.authorize(tenant_id, reference or "", environment, represented_cuit or "")
        except AppError:
            return {"state": "pending", "configured": False, "remote_validation": "pending", "diagnostic_code": "arca_credentials_not_provisioned"}
        return {"state": "configured", "configured": True, "remote_validation": "pending", "diagnostic_code": "arca_remote_validation_pending", "expected_fingerprint": binding.expected_fingerprint}


@dataclass(frozen=True)
class CredentialMaterial:
    certificate_pem: bytes = field(repr=False)
    private_key_pem: bytes = field(repr=False)
    password: bytes | None = field(default=None, repr=False)


@dataclass(frozen=True)
class ValidatedCredential:
    certificate: x509.Certificate = field(repr=False)
    private_key: rsa.RSAPrivateKey = field(repr=False)
    certificate_pem: bytes = field(repr=False)
    private_key_pem: bytes = field(repr=False)
    fingerprint: str
    expires_at: datetime
    subject_dn: str = field(repr=False)


class CredentialProvider(Protocol):
    def load(self, binding: CredentialBinding) -> CredentialMaterial: ...


def validate_credential(material: CredentialMaterial, binding: CredentialBinding, now: datetime) -> ValidatedCredential:
    if now.tzinfo is None:
        raise AppError(503, "arca_clock_invalid", "El reloj fiscal del servidor requiere zona horaria")
    try:
        if len(material.certificate_pem) > MAX_CREDENTIAL_BYTES or len(material.private_key_pem) > MAX_CREDENTIAL_BYTES:
            raise ValueError()
        certificate = x509.load_pem_x509_certificate(material.certificate_pem)
        key = serialization.load_pem_private_key(material.private_key_pem, password=material.password)
        if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
            raise ValueError()
        public = certificate.public_key()
        if not isinstance(public, rsa.RSAPublicKey) or public.public_numbers() != key.public_key().public_numbers():
            raise ValueError()
        if not certificate.not_valid_before_utc <= now < certificate.not_valid_after_utc:
            raise AppError(409, "arca_certificate_not_current", "El certificado fiscal no está vigente; revisa su provisión")
        fingerprint = certificate.fingerprint(hashes.SHA256()).hex()
        if binding.expected_fingerprint and not hmac.compare_digest(fingerprint, binding.expected_fingerprint):
            raise AppError(409, "arca_certificate_fingerprint_mismatch", "La huella del certificado no coincide con el registro del servidor")
        return ValidatedCredential(certificate=certificate, private_key=key, certificate_pem=certificate.public_bytes(serialization.Encoding.PEM), private_key_pem=key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()), fingerprint=fingerprint, expires_at=certificate.not_valid_after_utc, subject_dn=certificate.subject.rfc4514_string())
    except AppError:
        raise
    except (ValueError, TypeError, UnsupportedAlgorithm):
        raise AppError(409, "arca_credential_invalid", "El certificado y la clave deben ser una pareja RSA válida") from None


class SyntheticCredentialProvider:
    """Only explicitly constructed in tests/laboratories; never a runtime mode."""
    def __init__(self, materials: Mapping[str, CredentialMaterial]):
        self.materials = materials
        self.loads = 0

    def load(self, binding: CredentialBinding) -> CredentialMaterial:
        self.loads += 1
        material = self.materials.get(binding.reference)
        if material is None:
            raise AppError(503, "arca_credentials_unavailable", "Las credenciales fiscales no están disponibles")
        return material


class SecretManagerCredentialProvider:
    def __init__(self, client, *, enabled: bool = False):
        self.client = client
        self.enabled = enabled

    def _read(self, resource: str) -> bytes:
        if not SECRET_RESOURCE.fullmatch(resource):
            raise AppError(503, "arca_server_configuration_invalid", "El recurso fiscal del servidor no es válido")
        try:
            response = self.client.access_secret_version(request={"name": resource})
            data = bytes(response.payload.data)
            if len(data) > MAX_CREDENTIAL_BYTES:
                raise ValueError()
            return data
        except Exception:
            raise AppError(503, "arca_credentials_unavailable", "Las credenciales fiscales no están disponibles") from None

    def load(self, binding: CredentialBinding) -> CredentialMaterial:
        require_homologation(binding.environment)
        if not self.enabled:
            raise AppError(503, "arca_secret_manager_disabled", "La resolución externa de secretos requiere habilitación explícita del servidor")
        if binding.provider != "secret_manager":
            raise AppError(503, "arca_server_configuration_invalid", "El proveedor fiscal no coincide con el registro")
        return CredentialMaterial(self._read(binding.certificate_resource), self._read(binding.private_key_resource), self._read(binding.password_resource) if binding.password_resource else None)


class LocalCredentialProvider:
    def __init__(self, root: str | Path, *, enabled: bool = False):
        self.root = Path(root)
        self.enabled = enabled

    def _read(self, resource: str) -> bytes:
        try:
            relative = Path(resource)
            if relative.is_absolute() or ".." in relative.parts or not relative.parts:
                raise ValueError()
            root = self.root.resolve(strict=True)
            if not self.root.is_absolute() or root.is_relative_to(_repository_root()) or not root.is_dir():
                raise ValueError()
            candidate = self.root / relative
            path = external_server_file(candidate, secret=True)
            if not path.is_relative_to(root) or len(data := path.read_bytes()) > MAX_CREDENTIAL_BYTES:
                raise ValueError()
            return data
        except (OSError, ValueError):
            raise AppError(503, "arca_credentials_unavailable", "Las credenciales locales no están disponibles") from None

    def load(self, binding: CredentialBinding) -> CredentialMaterial:
        require_homologation(binding.environment)
        if not self.enabled:
            raise AppError(503, "arca_local_credentials_disabled", "Las credenciales locales requieren habilitación explícita del servidor")
        if binding.provider != "local":
            raise AppError(503, "arca_server_configuration_invalid", "El proveedor fiscal no coincide con el registro")
        return CredentialMaterial(self._read(binding.certificate_resource), self._read(binding.private_key_resource), self._read(binding.password_resource) if binding.password_resource else None)


class RoutedCredentialProvider:
    def __init__(self, providers: Mapping[str, CredentialProvider]):
        self.providers = providers

    def load(self, binding: CredentialBinding) -> CredentialMaterial:
        provider = self.providers.get(binding.provider)
        if provider is None:
            raise AppError(503, "arca_credentials_unavailable", "El proveedor fiscal no está provisionado en el servidor")
        return provider.load(binding)

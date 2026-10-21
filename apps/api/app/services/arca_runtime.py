"""Server-only production wiring. Test transports cannot be selected by HTTP input."""
import os

from app.core.errors import AppError
from app.services.arca_credentials import CredentialRegistry, LocalCredentialProvider, RoutedCredentialProvider, SecretManagerCredentialProvider, require_homologation
from app.services.arca_wsaa import ArcaAuthService, HttpWsaaTransport, TicketKeyring
from app.services.arca_wsfe import ArcaWsfeClient


def _enabled(name):
    return os.getenv(name, "false").lower() == "true"


class _LazySecretManagerClient:
    def __init__(self):
        self.client = None

    def access_secret_version(self, **kwargs):
        if self.client is None:
            from google.cloud import secretmanager
            self.client = secretmanager.SecretManagerServiceClient()
        return self.client.access_secret_version(**kwargs)

    def close(self):
        if self.client is not None:
            self.client.transport.close()


class _ServerCredentialProvider:
    def __init__(self):
        self.secret_client = _LazySecretManagerClient()

    def load(self, binding):
        require_homologation(binding.environment)
        if binding.provider == "local":
            root = os.getenv("ARCA_LOCAL_CREDENTIAL_ROOT", "")
            if not root or not _enabled("ARCA_LOCAL_CREDENTIALS_ENABLED"):
                raise AppError(503, "arca_local_credentials_disabled", "El proveedor local de homologación no está habilitado")
            return LocalCredentialProvider(root, enabled=True).load(binding)
        if binding.provider == "secret_manager":
            return SecretManagerCredentialProvider(self.secret_client, enabled=_enabled("ARCA_HOMOLOGATION_ENABLED")).load(binding)
        # Synthetic materials are injected by tests, never through server files.
        raise AppError(503, "arca_credential_provider_disabled", "Este proveedor no está disponible en la aplicación")

    def close(self):
        self.secret_client.close()


class ArcaRuntime:
    def __init__(self, db, *, clock=None):
        self.db = db
        self.clock = clock
        self.external_enabled = _enabled("ARCA_HOMOLOGATION_ENABLED")
        self.registry = CredentialRegistry.from_server_settings()
        self._provider = None
        self._auth = None
        self._wsfe = None

    def credential_status(self, tenant_id, reference, environment, cuit):
        if environment != "homologation":
            return {"status": "blocked", "diagnostic": "arca_production_disabled", "remote_validation": "pending"}
        try:
            binding = self.registry.authorize(tenant_id, reference, environment, cuit)
        except AppError:
            return {"status": "not_configured", "diagnostic": "arca_credentials_not_provisioned", "remote_validation": "pending"}
        return {"status": "configured" if self.external_enabled else "disabled", "fingerprint": binding.expected_fingerprint, "expires_at": None, "diagnostic": "Referencia de servidor configurada; validación del material y delegación pendientes", "remote_validation": "pending"}

    def ensure_available(self, tenant_id, reference, environment, cuit):
        require_homologation(environment)
        if not self.external_enabled:
            raise AppError(503, "arca_homologation_disabled", "Homologación externa desactivada; faltan accesos y validación explícita")
        binding = self.registry.authorize(tenant_id, reference, environment, cuit)
        if binding.provider == "synthetic":
            raise AppError(503, "arca_credential_provider_disabled", "La aplicación no admite un proveedor sintético")
        if binding.provider == "local" and not _enabled("ARCA_LOCAL_CREDENTIALS_ENABLED"):
            raise AppError(503, "arca_local_credentials_disabled", "El proveedor local está desactivado")
        TicketKeyring.from_server_settings().ensure_ready()

    def get_ticket(self, tenant_id, reference, environment, cuit):
        self.ensure_available(tenant_id, reference, environment, cuit)
        if self._auth is None:
            self._provider = _ServerCredentialProvider()
            options = {"clock": self.clock} if self.clock else {}
            self._auth = ArcaAuthService(self.db, self.registry, self._provider, TicketKeyring.from_server_settings(), transport=HttpWsaaTransport(allow_homologation_external=True), **options)
        return self._auth.get_ticket(tenant_id, reference, environment, cuit)

    @property
    def wsfe(self):
        if not self.external_enabled:
            raise AppError(503, "arca_homologation_disabled", "Homologación externa desactivada")
        if self._wsfe is None:
            self._wsfe = ArcaWsfeClient("homologation", clock=self.clock)
        return self._wsfe

    def close(self):
        if self._wsfe is not None:
            self._wsfe.close()
        if self._auth is not None:
            self._auth.transport.close()
        if self._provider is not None:
            self._provider.close()

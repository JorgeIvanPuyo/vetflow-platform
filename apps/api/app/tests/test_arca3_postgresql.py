"""Additional WSAA renewal/fencing races in a private PostgreSQL schema.

Only TEST_DATABASE_URL supplies a connection. Every worker and observer uses
the schema-translated factory. Certificates/keys/tickets are synthetic and the
real CMS/SOAP codec runs behind an explicitly injected HTTP transport.
"""
import socket
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, timedelta
from threading import Event
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.errors import AppError
from app.db.base import Base
from app.models.arca_auth import ArcaAuthCache, ArcaTenantTicketGrant
from app.models.tenant import Tenant
from app.services.arca_credentials import CredentialRegistry, SyntheticCredentialProvider
from app.services.arca_wsaa import ArcaAuthService, HttpWsaaTransport, TRA_CLOCK_WINDOW, TICKET_MAX_LIFETIME
from app.tests.test_arca2_wsaa import CUIT, DELEGATE, NOW, SoapLaboratory, _binding, _keyring, _material


@pytest.fixture(autouse=True)
def no_uninjected_auth_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("ARCA.3 authentication races require injected HTTP transport")
    # psycopg/libpq's explicitly configured local connection is not a Python
    # socket transport; HTTP and Python sockets must never leave this harness.
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


@pytest.fixture()
def arca3_auth_factory(postgres_test_session_factory):
    engine = postgres_test_session_factory.kw["bind"]
    assert engine.dialect.name == "postgresql"
    schema = "arca3_test_" + uuid.uuid4().hex
    scoped = engine.execution_options(schema_translate_map={None: schema})
    with engine.begin() as setup:
        setup.execute(CreateSchema(schema))
    try:
        Base.metadata.create_all(scoped)
        yield sessionmaker(bind=scoped, autoflush=False)
    finally:
        # Tests join all executors and close every Session before this cleanup.
        with engine.begin() as cleanup:
            cleanup.execute(DropSchema(schema, cascade=True))


def _laboratory(factory):
    with factory() as db:
        tenants = [Tenant(name="Synthetic authentication clinic one"), Tenant(name="Synthetic authentication clinic two")]
        db.add_all(tenants)
        db.flush()
        ids = [tenant.id for tenant in tenants]
        db.commit()
    material, certificate = _material()
    bindings = [_binding(ids[0]), _binding(ids[1], reference="opaque://other/renewal", represented_cuits=(DELEGATE,))]
    clock = SimpleNamespace(value=NOW)
    laboratory = SoapLaboratory(certificate, lambda: clock.value)
    return SimpleNamespace(factory=factory, clock=clock, laboratory=laboratory, bindings=bindings,
        registry=CredentialRegistry(bindings), provider=SyntheticCredentialProvider({binding.reference: material for binding in bindings}), keys=_keyring())


def _request(lab, binding):
    with lab.factory() as db:
        transport = HttpWsaaTransport(transport=httpx.MockTransport(lab.laboratory.handle))
        service = ArcaAuthService(db, lab.registry, lab.provider, lab.keys, transport=transport, clock=lambda: lab.clock.value)
        try:
            return service.get_ticket(binding.tenant_id, binding.reference, "homologation", binding.represented_cuits[0])
        finally:
            transport.close()


def _hold_response(lab):
    entered, release = Event(), Event()
    def hold():
        entered.set()
        if not release.wait(timeout=15):
            raise RuntimeError("Synthetic authentication coordination timed out")
    lab.laboratory.before_response = hold
    return entered, release


def test_postgresql_expired_ta_is_renewed_once_across_processes_and_tenants(arca3_auth_factory):
    lab = _laboratory(arca3_auth_factory)
    first = _request(lab, lab.bindings[0])
    with lab.factory() as db:
        original = db.scalar(select(ArcaAuthCache))
        cache_id, old_ciphertext = original.id, original.encrypted_ticket
    lab.clock.value = first.expires_at + timedelta(seconds=1)
    # Key rotation accompanies renewal without touching unrelated scopes or
    # creating another global authentication identity.
    lab.keys = _keyring("v2", **lab.keys.keys)
    entered, release = _hold_response(lab)
    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="arca3-auth-renew")
    try:
        renewing = executor.submit(_request, lab, lab.bindings[0])
        assert entered.wait(timeout=15)
        contender = executor.submit(_request, lab, lab.bindings[1])
        with pytest.raises(AppError) as pending:
            contender.result(timeout=15)
        assert pending.value.code == "arca_wsaa_renewal_in_progress"
        release.set()
        renewed = renewing.result(timeout=15)
        assert renewed.expires_at > first.expires_at
        assert _request(lab, lab.bindings[1]).expires_at == renewed.expires_at
        assert len(lab.laboratory.requests) == 2  # One initial TA, one renewal.
        with lab.factory() as db:
            rows = list(db.scalars(select(ArcaAuthCache)))
            grants = list(db.scalars(select(ArcaTenantTicketGrant)))
            assert len(rows) == 1 and rows[0].id == cache_id
            assert rows[0].state == "ready" and rows[0].fence == 2
            assert rows[0].encryption_key_version == "v2"
            assert rows[0].encrypted_ticket != old_ciphertext
            assert len(grants) == 2 and all(grant.cache_id == cache_id for grant in grants)
            assert all(grant.encryption_key_version == "v2" for grant in grants)
            assert {grant.tenant_id for grant in grants} == {binding.tenant_id for binding in lab.bindings}
            assert grants[0].encrypted_ticket != grants[1].encrypted_ticket
    finally:
        release.set()
        executor.shutdown(wait=True, cancel_futures=True)


def test_postgresql_expired_auth_worker_cannot_publish_or_trigger_an_early_relogin(arca3_auth_factory):
    lab = _laboratory(arca3_auth_factory)
    entered, release = _hold_response(lab)
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="arca3-auth-fenced")
    try:
        stale = executor.submit(_request, lab, lab.bindings[0])
        assert entered.wait(timeout=15)
        lab.clock.value += timedelta(seconds=61)
        with pytest.raises(AppError) as uncertain:
            _request(lab, lab.bindings[1])
        assert uncertain.value.code == "arca_wsaa_renewal_outcome_unknown"
        release.set()
        with pytest.raises(AppError) as fenced:
            stale.result(timeout=15)
        assert fenced.value.code == "arca_wsaa_claim_fenced"
        with lab.factory() as db:
            row = db.scalar(select(ArcaAuthCache))
            deadline = row.retry_not_before.astimezone(UTC)
            assert row.state == "backoff" and row.fence == 2
            assert row.encrypted_ticket is None
            assert deadline == NOW + TRA_CLOCK_WINDOW + TICKET_MAX_LIFETIME
            assert list(db.scalars(select(ArcaTenantTicketGrant))) == []
        # Twelve hours since the claim alone is insufficient: the old TRA could
        # have been accepted at the end of its remaining five-minute window.
        lab.clock.value = NOW + TICKET_MAX_LIFETIME + timedelta(seconds=1)
        with pytest.raises(AppError):
            _request(lab, lab.bindings[1])
        assert len(lab.laboratory.requests) == 1
        lab.clock.value = deadline + timedelta(seconds=1)
        lab.laboratory.before_response = None
        assert _request(lab, lab.bindings[1]).represented_cuit == DELEGATE
        assert len(lab.laboratory.requests) == 2
        with lab.factory() as db:
            row = db.scalar(select(ArcaAuthCache))
            assert row.state == "ready" and row.fence == 3
            grants = list(db.scalars(select(ArcaTenantTicketGrant)))
            assert len(grants) == 1 and grants[0].tenant_id == lab.bindings[1].tenant_id
    finally:
        release.set()
        executor.shutdown(wait=True, cancel_futures=True)

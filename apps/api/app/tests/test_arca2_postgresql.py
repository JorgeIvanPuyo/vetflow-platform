"""Real PostgreSQL claims/fences in a generated private schema; never public."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.errors import AppError
from app.db.base import Base
from app.models.arca_emission import ArcaEmissionIntent, ArcaSeriesOwnership
from app.models.fiscal_proposal import FiscalPaymentAllocation
from app.models.sale_fiscal import SaleFiscalDocument
from app.services.arca_emission import ArcaEmissionService
from app.services.fiscal_proposal import FiscalProposalService
from app.tests.arca2_emission_support import NOW, SyntheticEmissionRuntime, SyntheticEmissionStorage, seed_emission_case
from app.tests.arca2_support import ControlledArcaTransport


@pytest.fixture()
def arca2_postgres_factory(postgres_test_session_factory):
    engine = postgres_test_session_factory.kw["bind"]
    assert engine.dialect.name == "postgresql"
    schema = "arca2_test_" + uuid.uuid4().hex
    scoped = engine.execution_options(schema_translate_map={None: schema})
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    try:
        Base.metadata.create_all(scoped)
        # This is the only factory given to setup, every worker and every observer.
        yield sessionmaker(bind=scoped, autoflush=False)
    finally:
        # Executors are joined and Session contexts close before reaching here.
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))


def _seed(factory, *, reuse_case=None):
    with factory() as db:
        return seed_emission_case(db, reuse_case=reuse_case)


def _service(db, runtime, storage, *, owner=None, clock=None):
    return ArcaEmissionService(db, runtime=runtime, storage=storage,
        clock=clock or (lambda: NOW), owner_id=owner or uuid.uuid4().hex)


def _prepare(factory, runtime, storage, case, key):
    with factory() as db:
        return _service(db, runtime, storage).prepare(case.context, case.sale_id, case.create, key)


def _issue(factory, runtime, storage, case, operation_id, *, owner=None, clock=None):
    with factory() as db:
        return _service(db, runtime, storage, owner=owner, clock=clock).issue(case.context, case.sale_id, operation_id)


def _race(first, second):
    barrier = Barrier(2)
    def run(operation):
        barrier.wait(timeout=15)
        try:
            result = operation()
            return ("ok", result)
        except AppError as error:
            return ("error", error)
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="arca2-race") as executor:
        futures = [executor.submit(run, task) for task in (first, second)]
        return [future.result(timeout=60) for future in futures]


def _state(factory, case):
    with factory() as db:
        operations = list(db.scalars(select(ArcaEmissionIntent).where(
            ArcaEmissionIntent.tenant_id == case.tenant_id, ArcaEmissionIntent.sale_id == case.sale_id)))
        documents = list(db.scalars(select(SaleFiscalDocument).where(
            SaleFiscalDocument.tenant_id == case.tenant_id, SaleFiscalDocument.sale_id == case.sale_id,
            SaleFiscalDocument.source == "arca")))
        active = db.scalar(select(func.count()).select_from(FiscalPaymentAllocation).where(
            FiscalPaymentAllocation.tenant_id == case.tenant_id,
            FiscalPaymentAllocation.payment_id == case.payment_id, FiscalPaymentAllocation.is_active.is_(True)))
        assert active <= 1
        return {"operations": [(row.id, row.state, row.number, row.request_hash) for row in operations],
                "documents": [(row.id, row.document_number, row.cae) for row in documents], "active": active}


def test_postgresql_two_requests_with_different_keys_cannot_duplicate_same_proposal(arca2_postgres_factory):
    factory = arca2_postgres_factory
    case = _seed(factory)
    runtime, storage = SyntheticEmissionRuntime(), SyntheticEmissionStorage()
    try:
        def prepare_and_issue(key):
            operation = _prepare(factory, runtime, storage, case, key)
            return _issue(factory, runtime, storage, case, operation.id)
        results = _race(lambda: prepare_and_issue("same-proposal-first"), lambda: prepare_and_issue("same-proposal-second"))
        assert any(kind == "ok" and value.status == "authorized" for kind, value in results)
        assert all(kind == "ok" or value.status_code == 409 for kind, value in results)
        state = _state(factory, case)
        assert len(state["operations"]) == 1 and len(state["documents"]) == 1 and state["active"] == 1
        assert runtime.transport.authorization_calls == 1 and len(runtime.transport.records) == 1
    finally:
        runtime.close()


def test_postgresql_two_proposals_of_same_series_use_distinct_sequential_numbers(arca2_postgres_factory):
    factory = arca2_postgres_factory
    first = _seed(factory)
    second = _seed(factory, reuse_case=first)
    runtime, storage = SyntheticEmissionRuntime(), SyntheticEmissionStorage()
    try:
        a = _prepare(factory, runtime, storage, first, "series-first")
        b = _prepare(factory, runtime, storage, second, "series-second")
        results = _race(lambda: _issue(factory, runtime, storage, first, a.id),
                        lambda: _issue(factory, runtime, storage, second, b.id))
        assert any(kind == "ok" and value.status == "authorized" for kind, value in results)
        for case, operation in ((first, a), (second, b)):
            state = _state(factory, case)
            if state["operations"][0][1] != "authorized":
                assert _issue(factory, runtime, storage, case, operation.id).status == "authorized"
            assert len(_state(factory, case)["documents"]) == 1
        assert sorted(key[3] for key in runtime.transport.records) == [1, 2]
        assert runtime.transport.authorization_calls == 2
    finally:
        runtime.close()


def test_postgresql_lost_response_blocks_next_candidate_until_exact_reconciliation(arca2_postgres_factory):
    factory = arca2_postgres_factory
    first = _seed(factory)
    second = _seed(factory, reuse_case=first)
    runtime, storage = SyntheticEmissionRuntime(), SyntheticEmissionStorage()
    later = None
    try:
        a = _prepare(factory, runtime, storage, first, "uncertain-series-first")
        b = _prepare(factory, runtime, storage, second, "uncertain-series-second")
        runtime.transport.timeout_after_authorization = True
        assert _issue(factory, runtime, storage, first, a.id).status in {"unknown", "processing"}
        try:
            blocked = _issue(factory, runtime, storage, second, b.id)
        except AppError as error:
            assert error.status_code == 409
        else:
            assert blocked.status != "authorized"
        assert _state(factory, second)["operations"][0][2] is None
        assert runtime.transport.authorization_calls == 1
        later = SyntheticEmissionRuntime(transport=runtime.transport, clock=lambda: NOW + timedelta(seconds=121))
        with factory() as db:
            recovered = _service(db, later, storage, owner="new-process", clock=lambda: NOW + timedelta(seconds=121)).reconcile(first.context, first.sale_id, a.id)
        assert recovered.status == "authorized" and recovered.number == 1
        assert runtime.transport.authorization_calls == 1
        assert _issue(factory, later, storage, second, b.id,
                      clock=lambda: NOW + timedelta(seconds=121)).status == "authorized"
        assert sorted(key[3] for key in runtime.transport.records) == [1, 2]
        assert _state(factory, first)["active"] == _state(factory, second)["active"] == 1
    finally:
        runtime.close()
        if later:
            later.close()


def test_postgresql_wsaa_shared_certificate_has_one_login_and_scoped_encrypted_grants(arca2_postgres_factory):
    """Two processes/tenants coordinate the same certificate through PostgreSQL."""
    import httpx
    from app.models.arca_auth import ArcaAuthCache, ArcaTenantTicketGrant
    from app.models.tenant import Tenant
    from app.services.arca_credentials import CredentialRegistry, SyntheticCredentialProvider
    from app.services.arca_wsaa import ArcaAuthService, HttpWsaaTransport
    from app.tests.test_arca2_wsaa import CUIT, DELEGATE, SoapLaboratory, _binding, _keyring, _material

    factory = arca2_postgres_factory
    with factory() as setup:
        first = Tenant(name="Synthetic WSAA first clinic")
        second = Tenant(name="Synthetic WSAA second clinic")
        setup.add_all([first, second])
        setup.flush()
        first_id, second_id = first.id, second.id
        setup.commit()
    material, certificate = _material()
    bindings = [_binding(first_id), _binding(second_id, reference="opaque://second/wsaa", represented_cuits=(DELEGATE,))]
    registry = CredentialRegistry(bindings)
    provider = SyntheticCredentialProvider({binding.reference: material for binding in bindings})
    keyring = _keyring()
    entered, release = Event(), Event()
    laboratory = SoapLaboratory(certificate, lambda: NOW)

    def hold_remote_response():
        entered.set()
        if not release.wait(timeout=15):
            raise RuntimeError("Synthetic WSAA synchronization timeout")

    laboratory.before_response = hold_remote_response
    def request_ticket(binding):
        # The factory binds every connection to the generated private schema.
        with factory() as db:
            transport = HttpWsaaTransport(transport=httpx.MockTransport(laboratory.handle))
            service = ArcaAuthService(db, registry, provider, keyring, transport=transport, clock=lambda: NOW)
            try:
                return service.get_ticket(binding.tenant_id, binding.reference, "homologation", binding.represented_cuits[0])
            finally:
                service.transport.close()

    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="arca2-wsaa-race")
    try:
        active = executor.submit(request_ticket, bindings[0])
        assert entered.wait(timeout=15)
        contender = executor.submit(request_ticket, bindings[1])
        with pytest.raises(AppError) as pending:
            contender.result(timeout=15)
        assert pending.value.code == "arca_wsaa_renewal_in_progress"
        release.set()
        assert active.result(timeout=15).represented_cuit == CUIT
        # A restarted, independently connected client reuses the committed TA.
        assert request_ticket(bindings[1]).represented_cuit == DELEGATE
        assert len(laboratory.requests) == 1
        with factory() as observer:
            caches = list(observer.scalars(select(ArcaAuthCache)))
            grants = list(observer.scalars(select(ArcaTenantTicketGrant).order_by(ArcaTenantTicketGrant.tenant_id)))
            assert len(caches) == 1 and caches[0].state == "ready" and caches[0].fence == 1
            assert len(grants) == 2
            assert {grant.tenant_id for grant in grants} == {first_id, second_id}
            assert all(grant.cache_id == caches[0].id for grant in grants)
            assert grants[0].encrypted_ticket != grants[1].encrypted_ticket
    finally:
        release.set()
        executor.shutdown(wait=True, cancel_futures=True)


class _PausedAuthorizationTransport(ControlledArcaTransport):
    def __init__(self):
        super().__init__()
        self.remote_authorized = Event()
        self.release_old_response = Event()

    def handle_request(self, request):
        response = super().handle_request(request)
        if request.headers.get("SOAPAction", "").strip('"').endswith("/FECAESolicitar"):
            # super has committed the remote ledger and released its mutex. A
            # different process may now consult while this old reply is delayed.
            self.remote_authorized.set()
            if not self.release_old_response.wait(timeout=30):
                raise RuntimeError("Synthetic delayed response was not released")
        return response


def test_postgresql_expired_worker_cannot_overwrite_new_fenced_reconciliation(arca2_postgres_factory):
    factory = arca2_postgres_factory
    case = _seed(factory)
    transport = _PausedAuthorizationTransport()
    old = SyntheticEmissionRuntime(transport=transport)
    new = SyntheticEmissionRuntime(transport=transport, clock=lambda: NOW + timedelta(seconds=121))
    storage = SyntheticEmissionStorage()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="arca2-old-worker")
    try:
        operation = _prepare(factory, old, storage, case, "fenced-worker-intent")
        future = executor.submit(_issue, factory, old, storage, case, operation.id, owner="obsolete-worker")
        assert transport.remote_authorized.wait(timeout=15)
        with factory() as db:
            recovered = _service(db, new, storage, owner="fresh-worker", clock=lambda: NOW + timedelta(seconds=121)).reconcile(case.context, case.sale_id, operation.id)
        assert recovered.status == "authorized"
        saved_document = recovered.document_id
        transport.release_old_response.set()
        try:
            old_result = future.result(timeout=30)
        except AppError as error:
            assert error.status_code == 409
        else:
            assert old_result.status == "authorized" and old_result.document_id == saved_document
        state = _state(factory, case)
        assert len(state["documents"]) == 1 and state["documents"][0][0] == saved_document
        assert state["active"] == 1 and transport.authorization_calls == 1
        with factory() as db:
            owner = db.scalar(select(ArcaSeriesOwnership).where(ArcaSeriesOwnership.tenant_id == case.tenant_id))
            assert owner.fence >= 2
    finally:
        transport.release_old_response.set()
        executor.shutdown(wait=True, cancel_futures=True)
        old.close()
        new.close()


def test_postgresql_issue_and_proposal_cancellation_cannot_both_consume_or_release_payment(arca2_postgres_factory):
    factory = arca2_postgres_factory
    case = _seed(factory)
    runtime, storage = SyntheticEmissionRuntime(), SyntheticEmissionStorage()
    try:
        operation = _prepare(factory, runtime, storage, case, "cancel-versus-issue")
        def cancel():
            with factory() as db:
                return FiscalProposalService(db).cancel(case.context, case.sale_id, case.proposal.id, reason="Synthetic concurrent cancellation")
        results = _race(lambda: _issue(factory, runtime, storage, case, operation.id), cancel)
        state = _state(factory, case)
        if runtime.transport.authorization_calls:
            assert runtime.transport.authorization_calls == 1 and len(state["documents"]) == 1 and state["active"] == 1
            assert results[1][0] == "error" and results[1][1].status_code == 409
        else:
            assert state["documents"] == [] and state["active"] == 0
            assert results[0][0] == "error" and results[0][1].status_code == 409
    finally:
        runtime.close()


def test_postgresql_remote_conflict_keeps_reservation_and_blocks_series(arca2_postgres_factory):
    factory = arca2_postgres_factory
    case = _seed(factory)
    runtime = SyntheticEmissionRuntime(transport=ControlledArcaTransport(timeout_after_authorization=True))
    storage = SyntheticEmissionStorage()
    later = None
    try:
        operation = _prepare(factory, runtime, storage, case, "remote-conflict-intent")
        _issue(factory, runtime, storage, case, operation.id)
        runtime.transport.records[(case.payload.issuer.cuit, 1, 15, 1)]["DocNro"] = "87654321"
        later = SyntheticEmissionRuntime(transport=runtime.transport, clock=lambda: NOW + timedelta(seconds=121))
        with factory() as db:
            result = _service(db, later, storage, clock=lambda: NOW + timedelta(seconds=121)).reconcile(case.context, case.sale_id, operation.id)
        assert result.status == "conflict" and result.cae is None
        state = _state(factory, case)
        assert state["documents"] == [] and state["active"] == 1 and state["operations"][0][2] == 1
        with factory() as db:
            owner = db.scalar(select(ArcaSeriesOwnership).where(ArcaSeriesOwnership.tenant_id == case.tenant_id))
            assert owner.active_intent_id == operation.id
        assert runtime.transport.authorization_calls == 1
    finally:
        runtime.close()
        if later:
            later.close()

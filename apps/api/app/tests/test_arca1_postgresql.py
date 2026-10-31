"""Only critical fiscal races, using synthetic tables in a private PG schema."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.errors import AppError
from app.db.base import Base
from app.models.fiscal_proposal import FiscalPaymentAllocation, FiscalProposal
from app.models.payment import SalePayment
from app.models.sale import Sale
from app.schemas.fiscal_proposal import FiscalProposalApprove, FiscalProposalGenerate
from app.services.fiscal_proposal import FiscalProposalService
from app.services.payment import SalePaymentService
from app.services.sale import SaleService
from app.tests.fiscal_test_support import seed_fiscal_case


@pytest.fixture()
def arca1_postgres_factory(postgres_test_session_factory):
    # The caller must provide the already verified LOCAL TEST_DATABASE_URL. The
    # shared fixture never falls back to the application's DATABASE_URL.
    engine = postgres_test_session_factory.kw["bind"]
    assert engine.dialect.name == "postgresql"
    schema = "arca1_test_" + uuid.uuid4().hex
    scoped_engine = engine.execution_options(schema_translate_map={None: schema})
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    try:
        # Every mapped table/FK and every session in every worker is translated.
        Base.metadata.create_all(scoped_engine)
        yield sessionmaker(bind=scoped_engine, autoflush=False)
    finally:
        # ThreadPoolExecutor and Session contexts close before fixture teardown.
        # Only this generated schema is touched; public is never a fixture.
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))


def _case(factory):
    with factory() as db:
        return seed_fiscal_case(db)


def _draft(factory, case):
    with factory() as db:
        proposals = FiscalProposalService(db).generate(
            case.context, case.sale_id,
            FiscalProposalGenerate(payment_ids=[case.payment_id], fiscal_series_id=case.series_id,
                                   fiscal_description=f"Synthetic reviewed veterinary service {uuid.uuid4().hex}"),
        )
        assert len(proposals) == 1
        return proposals[0]


def _approve(factory, case, proposal, key):
    with factory() as db:
        result = FiscalProposalService(db).approve(
            case.context, case.sale_id, proposal.id,
            FiscalProposalApprove(content_hash=proposal.content_hash, confirm_fiscal_identity=True),
            idempotency_key=key,
        )
        return str(result.id)


def _race(first, second):
    barrier = Barrier(2)

    def run(operation):
        barrier.wait(timeout=15)
        try:
            return ("ok", operation())
        except AppError as exc:
            return ("error", exc.code)

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="arca1-pg") as executor:
        futures = [executor.submit(run, operation) for operation in (first, second)]
        return [future.result(timeout=45) for future in futures]


def _state(factory, case):
    with factory() as db:
        active = list(db.scalars(select(FiscalPaymentAllocation).where(
            FiscalPaymentAllocation.tenant_id == case.tenant_id,
            FiscalPaymentAllocation.sale_id == case.sale_id,
            FiscalPaymentAllocation.is_active.is_(True),
        )))
        sale = db.scalar(select(Sale).where(Sale.tenant_id == case.tenant_id, Sale.id == case.sale_id))
        payment = db.scalar(select(SalePayment).where(
            SalePayment.tenant_id == case.tenant_id, SalePayment.id == case.payment_id,
        ))
        approved = db.scalar(select(func.count()).select_from(FiscalProposal).where(
            FiscalProposal.tenant_id == case.tenant_id, FiscalProposal.sale_id == case.sale_id,
            FiscalProposal.status == "approved",
        ))
        assert len(active) <= 1
        assert all(row.payment_id == case.payment_id and row.amount_ars == payment.amount_ars for row in active)
        if active:
            assert payment.is_active and sale.status == "confirmed"
            assert approved == 1
        return len(active), sale.status, payment.is_active, approved


def test_postgresql_two_approvals_cannot_reserve_same_payment(arca1_postgres_factory):
    factory = arca1_postgres_factory
    case = _case(factory)
    first = _draft(factory, case)
    second = _draft(factory, case)
    assert first.id != second.id
    results = _race(
        lambda: _approve(factory, case, first, "arca1-race-first"),
        lambda: _approve(factory, case, second, "arca1-race-second"),
    )
    assert sorted(result[0] for result in results) == ["error", "ok"]
    assert _state(factory, case) == (1, "confirmed", True, 1)


def test_postgresql_concurrent_idempotent_retry_has_one_reservation(arca1_postgres_factory):
    factory = arca1_postgres_factory
    case = _case(factory)
    proposal = _draft(factory, case)
    results = _race(
        lambda: _approve(factory, case, proposal, "arca1-same-key"),
        lambda: _approve(factory, case, proposal, "arca1-same-key"),
    )
    assert results == [("ok", str(proposal.id)), ("ok", str(proposal.id))]
    assert _state(factory, case) == (1, "confirmed", True, 1)


@pytest.mark.parametrize("operation", ["void", "reverse"])
def test_postgresql_approval_serializes_with_payment_void_and_sale_reverse(arca1_postgres_factory, operation):
    factory = arca1_postgres_factory
    case = _case(factory)
    proposal = _draft(factory, case)

    def operational_change():
        with factory() as db:
            if operation == "void":
                return str(SalePaymentService(db).void(case.tenant_id, case.payment_id,
                    reason="Synthetic correction", user_id=case.context.user_id).id)
            return str(SaleService(db).reverse(case.tenant_id, case.sale_id,
                reason="Synthetic reversal", reversed_by_user_id=case.context.user_id).id)

    results = _race(
        lambda: _approve(factory, case, proposal, f"arca1-vs-{operation}"),
        operational_change,
    )
    assert sorted(result[0] for result in results) == ["error", "ok"]
    active, sale_status, payment_active, approved = _state(factory, case)
    if results[0][0] == "ok":
        assert results[1] == ("error", "fiscal_payment_reserved" if operation == "void" else "fiscal_sale_reserved")
        assert (active, sale_status, payment_active, approved) == (1, "confirmed", True, 1)
    elif operation == "void":
        assert (active, sale_status, payment_active, approved) == (0, "confirmed", False, 0)
    else:
        assert (active, sale_status, payment_active, approved) == (0, "reversed", True, 0)

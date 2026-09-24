import os
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.tenant import get_tenant_context, require_clinic_admin

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.tenant import Tenant



@pytest.fixture()
def postgres_test_session_factory():
    """Return a session factory bound only to an explicit PostgreSQL test DB.

    Concurrency tests must never fall back to the application DATABASE_URL,
    because that can point at a developer database (or worse, another shared
    environment). Set TEST_DATABASE_URL to opt in to row-lock tests.
    """
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL concurrency tests")

    test_engine = create_engine(database_url, future=True)
    if test_engine.dialect.name != "postgresql":
        test_engine.dispose()
        pytest.skip("TEST_DATABASE_URL must use PostgreSQL")

    TestSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
        class_=Session,
    )
    try:
        yield TestSessionLocal
    finally:
        test_engine.dispose()

@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def tenant(db_session: Session) -> Tenant:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant A")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture()
def other_tenant(db_session: Session) -> Tenant:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant B")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant

@pytest.fixture(autouse=True)
def development_app_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def allow_supplier_mutations(client: TestClient):
    """Bypass supplier-admin authorization in tests focused on purchase workflows.

    Supplier authorization itself is covered by test_suppliers.py. Purchase-domain
    tests only need deterministic supplier fixtures without coupling every test to
    clinic-admin setup.
    """
    client.app.dependency_overrides[require_clinic_admin] = get_tenant_context
    try:
        yield
    finally:
        client.app.dependency_overrides.pop(require_clinic_admin, None)

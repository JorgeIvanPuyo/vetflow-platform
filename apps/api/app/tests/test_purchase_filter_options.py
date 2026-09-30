"""Run the creator-filter regression on SQLite and explicit test PostgreSQL."""
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.purchase import Purchase
from app.models.supplier import Supplier
from app.models.tenant import Tenant
from app.models.user import User


@pytest.fixture(params=["sqlite", "postgresql"])
def filter_db_session(request):
    if request.param == "sqlite":
        yield request.getfixturevalue("db_session")
        return

    factory = request.getfixturevalue("postgres_test_session_factory")
    engine = factory.kw["bind"]
    assert engine.dialect.name == "postgresql"
    # A unique transactional schema keeps this test independent of existing
    # databases/migrations and rolls back all DDL and data after the test.
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            schema = f"purchase_filter_test_{uuid.uuid4().hex}"
            connection.execute(CreateSchema(schema))
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
            Base.metadata.create_all(connection)
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                yield session
        finally:
            transaction.rollback()


def test_creator_filter_options_unique_ordered_and_tenant_scoped(filter_db_session):
    db = filter_db_session
    tenant = Tenant(id=uuid.uuid4(), name="Tenant A")
    other = Tenant(id=uuid.uuid4(), name="Tenant B")
    db.add_all([tenant, other])
    db.flush()

    def user(number, name, *, clinic=tenant, active=True):
        result = User(id=uuid.UUID(int=number), tenant_id=clinic.id,
                      full_name=name, email=f"creator-{number}@example.com",
                      role="secretaria", is_active=active)
        db.add(result)
        return result

    zulu = user(1, "Zulu")
    alpha_high = user(30, "alpha", active=False)
    beta = user(20, "beta")
    alpha_low = user(10, "ALPHA")
    no_purchases = user(40, "Sin compras")
    only_foreign_purchases = user(50, "Solo compras ajenas")
    foreign = user(60, "Ajeno", clinic=other)
    suppliers = {
        clinic.id: Supplier(id=uuid.uuid4(), tenant_id=clinic.id,
                            name="Proveedor", normalized_name="proveedor")
        for clinic in (tenant, other)
    }
    db.add_all(suppliers.values())
    db.flush()

    def purchase(clinic, creator):
        db.add(Purchase(id=uuid.uuid4(), tenant_id=clinic.id,
                        supplier_id=suppliers[clinic.id].id, supplier_name="Proveedor",
                        purchase_date=date(2026, 9, 29), document_type="invoice",
                        currency="USD", created_by_user_id=creator.id if creator else None))

    for creator in (zulu, alpha_high, beta, alpha_low, alpha_low, alpha_low, None):
        purchase(tenant, creator)
    purchase(other, foreign)
    # Deliberately inconsistent references verify BOTH tenant predicates:
    # an A user with purchases only in B, and a B user referenced by A.
    purchase(other, only_foreign_purchases)
    purchase(tenant, foreign)
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/purchases/filter-options", headers={
                "X-User-Email": no_purchases.email,
                "X-Tenant-Id": str(other.id),
                "X-Acting-Tenant-Id": str(other.id),
            })
            assert response.status_code == 200, response.text
            assert response.json() == {
                "data": {"creators": [
                    {"id": str(creator.id), "full_name": creator.full_name,
                     "email": creator.email, "is_active": creator.is_active}
                    for creator in (alpha_low, alpha_high, beta, zulu)
                ]},
                "meta": {},
            }
            foreign_response = client.get("/api/v1/purchases/filter-options",
                                          headers={"X-User-Email": foreign.email})
            assert foreign_response.status_code == 200
            assert [row["id"] for row in foreign_response.json()["data"]["creators"]] == [str(foreign.id)]
    finally:
        app.dependency_overrides.pop(get_db, None)

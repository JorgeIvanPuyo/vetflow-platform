"""P.10 upgrade/downgrade and preservation against disposable PostgreSQL."""

import os
import uuid
from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.owner import Owner
from app.models.sale import Sale
from app.repositories.receivables import receivable_sale_criteria
from app.schemas.owner import OwnerUpdate
from app.services.owner import OwnerService
from app.tests.test_service_pricing_migration import _config


def test_receivables_migration_follows_batches_as_single_head():
    script = ScriptDirectory.from_config(_config())
    assert script.get_heads() == ["0054_receivables_foundation"]
    assert script.get_revision("0054_receivables_foundation").down_revision == "0053_sale_payment_batches"


def test_postgresql_upgrade_history_restrict_archive_cutoff_and_downgrade(monkeypatch):
    url = os.getenv("RECEIVABLES_MIGRATION_DATABASE_URL")
    if not url:
        pytest.skip("Requires an empty disposable RECEIVABLES_MIGRATION_DATABASE_URL")
    engine = sa.create_engine(url)
    assert engine.dialect.name == "postgresql"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    config = _config()
    tenants = [uuid.uuid4(), uuid.uuid4()]
    owner_id, free_owner_id = uuid.uuid4(), uuid.uuid4()
    sale_ids = [uuid.uuid4(), uuid.uuid4()]
    try:
        assert not sa.inspect(engine).has_table("alembic_version"), "Use an empty migration test DB"
        command.upgrade(config, "0053_sale_payment_batches")
        with engine.begin() as connection:
            for tenant_id in tenants:
                connection.execute(sa.text("INSERT INTO tenants (id, name) VALUES (:id, 'P10 migration')"), {"id": tenant_id})
                connection.execute(sa.text("INSERT INTO tenant_preferences (id, tenant_id, appointment_duration_options) VALUES (:id, :tenant, '[15,30,45,60]')"), {"id": uuid.uuid4(), "tenant": tenant_id})
            for identity in [owner_id, free_owner_id]:
                connection.execute(sa.text("INSERT INTO owners (id, tenant_id, full_name, phone, document_id, email) VALUES (:id, :tenant, 'Historic owner', '555', 'DOC', 'history@example.com')"), {"id": identity, "tenant": tenants[0]})
            for identity, owner in zip(sale_ids, [owner_id, None]):
                connection.execute(sa.text("""INSERT INTO sales
                    (id, tenant_id, owner_id, owner_name_snapshot, sale_date, currency,
                     subtotal_ars, discount_total_ars, total_ars, status, confirmed_at)
                    VALUES (:id, :tenant, :owner, 'Historic snapshot', '2020-01-01',
                        'ARS', 100, 0, 100, 'confirmed', '2020-01-01T13:00:00Z')"""),
                    {"id": identity, "tenant": tenants[0], "owner": owner})

        def snapshot(table):
            with engine.connect() as connection:
                return [dict(row) for row in connection.execute(sa.text(f"SELECT * FROM {table} ORDER BY id")).mappings()]

        original = {table: snapshot(table) for table in ["sales", "owners", "tenant_preferences", "sale_payments", "sale_payment_batches", "inventory_movements"]}
        command.upgrade(config, "head")
        inspector = sa.inspect(engine)
        column = next(c for c in inspector.get_columns("tenant_preferences") if c["name"] == "receivables_tracking_started_at")
        assert column["nullable"] and column["default"] is None and column["type"].timezone
        fk = next(f for f in inspector.get_foreign_keys("sales") if f["constrained_columns"] == ["owner_id"])
        assert fk["name"] == "fk_sales_owner_id_preserve_history" and fk["options"]["ondelete"] == "RESTRICT"
        for table, rows in original.items():
            upgraded = snapshot(table)
            if table == "owners":
                assert all(row.pop("is_active") is True for row in upgraded)
            elif table == "tenant_preferences":
                assert all(row.pop("receivables_tracking_started_at") is None for row in upgraded)
            assert upgraded == rows

        with pytest.raises(sa.exc.IntegrityError) as error:
            with engine.begin() as connection:
                connection.execute(sa.text("DELETE FROM owners WHERE id=:id AND tenant_id=:tenant"), {"id": owner_id, "tenant": tenants[0]})
        assert error.value.orig.diag.constraint_name == "fk_sales_owner_id_preserve_history"
        factory = sessionmaker(bind=engine)
        with factory() as db:
            service = OwnerService(db)
            with pytest.raises(AppError) as error:
                service.delete_owner(tenants[1], owner_id)
            assert error.value.status_code == 404
            with pytest.raises(AppError) as error:
                service.delete_owner(tenants[0], owner_id)
            assert error.value.code == "owner_has_commercial_history"
            service.update_owner(tenants[0], owner_id, OwnerUpdate(is_active=False))
            assert service.get_owner(tenants[0], owner_id).is_active is False
            assert list(db.scalars(sa.select(Sale.id).where(receivable_sale_criteria(tenants[0])))) == []
            cutoff = datetime(2026, 10, 2, 13, tzinfo=UTC)
            db.execute(sa.text("UPDATE tenant_preferences SET receivables_tracking_started_at=:cutoff WHERE tenant_id=:tenant"), {"cutoff": cutoff, "tenant": tenants[0]})
            db.commit()
            assert list(db.scalars(sa.select(Sale.id).where(receivable_sale_criteria(tenants[0])))) == []
            # Deliberate configuration to include this date verifies >= on timestamptz.
            db.execute(sa.text("UPDATE tenant_preferences SET receivables_tracking_started_at='2020-01-01T08:00:00-05:00' WHERE tenant_id=:tenant"), {"tenant": tenants[0]})
            db.commit()
            assert set(db.scalars(sa.select(Sale.id).where(receivable_sale_criteria(tenants[0])))) == {sale_ids[0]}
            # Restore changed configuration fields before checking rollback of DDL.
            service.update_owner(tenants[0], owner_id, OwnerUpdate(is_active=True))
            db.execute(sa.text("UPDATE tenant_preferences SET receivables_tracking_started_at=NULL WHERE tenant_id=:tenant"), {"tenant": tenants[0]})
            db.commit()
            service.delete_owner(tenants[0], free_owner_id)
            assert db.scalar(sa.select(Owner.id).where(Owner.tenant_id == tenants[0], Owner.id == free_owner_id)) is None
        assert snapshot("sales") == original["sales"]
        # The free-owner deletion was deliberate; archive changed only updated_at.
        original["owners"] = [row for row in original["owners"] if row["id"] != free_owner_id]
        command.downgrade(config, "0053_sale_payment_batches")
        inspector = sa.inspect(engine)
        assert "is_active" not in {c["name"] for c in inspector.get_columns("owners")}
        assert "receivables_tracking_started_at" not in {c["name"] for c in inspector.get_columns("tenant_preferences")}
        assert next(f for f in inspector.get_foreign_keys("sales") if f["constrained_columns"] == ["owner_id"])["options"]["ondelete"] == "SET NULL"
        for table, rows in original.items():
            actual = snapshot(table)
            if table == "owners":
                for row in actual + rows:
                    row.pop("updated_at")  # Explicit archive/reactivation changed this timestamp.
            assert actual == rows
        command.upgrade(config, "head")
        assert snapshot("sales") == original["sales"]
    finally:
        engine.dispose()
        get_settings.cache_clear()

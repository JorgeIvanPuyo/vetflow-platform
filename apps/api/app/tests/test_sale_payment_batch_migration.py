"""P.8 migration against an explicitly selected, empty PostgreSQL database."""

import os
import uuid

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.script import ScriptDirectory

from app.core.config import get_settings
from app.tests.test_service_pricing_migration import _config


def test_batch_migration_is_additive_single_head():
    script = ScriptDirectory.from_config(_config())
    assert script.get_heads() == ["0054_receivables_foundation"]
    assert script.get_revision("0053_sale_payment_batches").down_revision == "0052_sale_payment_idempotency"


def test_postgresql_batch_upgrade_constraints_history_and_downgrade(monkeypatch):
    url = os.getenv("PAYMENT_BATCH_MIGRATION_DATABASE_URL")
    if not url:
        pytest.skip("Requires an empty disposable PAYMENT_BATCH_MIGRATION_DATABASE_URL")
    engine = sa.create_engine(url)
    assert engine.dialect.name == "postgresql"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    config = _config()
    tenants = [uuid.uuid4(), uuid.uuid4()]
    sales = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    methods = [uuid.uuid4(), uuid.uuid4()]
    history_id, batch_id = uuid.uuid4(), uuid.uuid4()
    try:
        assert not sa.inspect(engine).has_table("alembic_version"), "Use an empty migration test DB"
        command.upgrade(config, "0052_sale_payment_idempotency")
        with engine.begin() as connection:
            for tenant_id in tenants:
                connection.execute(sa.text("INSERT INTO tenants (id, name) VALUES (:id, 'P8 migration')"), {"id": tenant_id})
            for index, sale_id in enumerate(sales):
                connection.execute(sa.text("""
                    INSERT INTO sales (id, tenant_id, sale_date, currency, subtotal_ars, discount_total_ars, total_ars, status)
                    VALUES (:id, :tenant, '2026-10-01', 'ARS', 100, 0, 100, 'confirmed')
                """), {"id": sale_id, "tenant": tenants[1 if index == 2 else 0]})
            for tenant_id, method_id in zip(tenants, methods):
                connection.execute(sa.text("""
                    INSERT INTO payment_methods (id, tenant_id, label, normalized_label, type)
                    VALUES (:id, :tenant, 'Cash', 'cash', 'cash')
                """), {"id": method_id, "tenant": tenant_id})
            connection.execute(sa.text("""
                INSERT INTO sale_payments (id, tenant_id, sale_id, payment_method_id,
                    payment_method_label_snapshot, payment_method_type_snapshot, amount_ars, received_at,
                    reference, notes, idempotency_key, idempotency_request_hash)
                VALUES (:id, :tenant, :sale, :method, 'Historic cash', 'cash', 20, '2026-10-01T12:00:00Z',
                    'Historic REF', 'Historic notes', 'individual-key', :hash)
            """), {"id": history_id, "tenant": tenants[0], "sale": sales[0], "method": methods[0], "hash": "a" * 64})
            history = dict(connection.execute(sa.text("SELECT * FROM sale_payments WHERE id=:id"), {"id": history_id}).mappings().one())
        command.upgrade(config, "head")
        inspector = sa.inspect(engine)
        batch_columns = {c["name"]: c for c in inspector.get_columns("sale_payment_batches")}
        assert set(batch_columns) == {"id", "tenant_id", "sale_id", "idempotency_key", "request_hash", "created_at", "updated_at"}
        assert all(not c["nullable"] for c in batch_columns.values())
        assert batch_columns["idempotency_key"]["type"].length == 128
        assert batch_columns["request_hash"]["type"].length == 64
        assert next(c for c in inspector.get_columns("sale_payments") if c["name"] == "batch_id")["nullable"]
        uniques = {c["name"]: c["column_names"] for c in inspector.get_unique_constraints("sale_payment_batches")}
        assert uniques["uq_sale_payment_batches_tenant_key"] == ["tenant_id", "idempotency_key"]
        assert uniques["uq_sale_payment_batches_membership"] == ["tenant_id", "sale_id", "id"]
        assert {i["name"] for i in inspector.get_indexes("sale_payment_batches")} >= {"ix_sale_payment_batches_tenant_id", "ix_sale_payment_batches_tenant_sale"}
        assert next(i for i in inspector.get_indexes("sale_payments") if i["name"] == "ix_sale_payments_tenant_batch")["column_names"] == ["tenant_id", "batch_id"]
        batch_fk = next(f for f in inspector.get_foreign_keys("sale_payment_batches") if f["name"] == "fk_sale_payment_batches_tenant_sale")
        member_fk = next(f for f in inspector.get_foreign_keys("sale_payments") if f["name"] == "fk_sale_payments_batch_membership")
        assert batch_fk["constrained_columns"] == ["tenant_id", "sale_id"]
        assert batch_fk["referred_columns"] == ["tenant_id", "id"]
        assert member_fk["constrained_columns"] == ["tenant_id", "sale_id", "batch_id"]
        assert member_fk["referred_columns"] == ["tenant_id", "sale_id", "id"]
        assert member_fk["options"]["ondelete"] == "RESTRICT"
        with engine.connect() as connection:
            upgraded = dict(connection.execute(sa.text("SELECT * FROM sale_payments WHERE id=:id"), {"id": history_id}).mappings().one())
        assert upgraded.pop("batch_id") is None
        assert upgraded == history

        def insert_batch(tenant_id, sale_id, key="batch-key", fingerprint="b" * 64, identity=None):
            identity = identity or uuid.uuid4()
            with engine.begin() as connection:
                connection.execute(sa.text("""INSERT INTO sale_payment_batches
                    (id, tenant_id, sale_id, idempotency_key, request_hash)
                    VALUES (:id, :tenant, :sale, :key, :hash)"""),
                    {"id": identity, "tenant": tenant_id, "sale": sale_id, "key": key, "hash": fingerprint})
            return identity

        insert_batch(tenants[0], sales[0], identity=batch_id)
        insert_batch(tenants[1], sales[2])  # Same key in another tenant is valid.
        with pytest.raises(sa.exc.IntegrityError):
            insert_batch(tenants[0], sales[1])  # Same tenant, another sale cannot reuse a key.
        with pytest.raises(sa.exc.IntegrityError):
            insert_batch(tenants[1], sales[0], key="foreign-sale")
        for key, fingerprint in [("", "b" * 64), ("k", "short"), (None, "b" * 64), ("k", None)]:
            with pytest.raises(sa.exc.IntegrityError):
                insert_batch(tenants[0], sales[0], key=key, fingerprint=fingerprint)
        # The new identity has a separate namespace from individual P.4 keys.
        insert_batch(tenants[0], sales[0], key="individual-key")

        def insert_member(tenant_index, sale_id, identity):
            with engine.begin() as connection:
                connection.execute(sa.text("""
                    INSERT INTO sale_payments (id, tenant_id, sale_id, payment_method_id,
                        payment_method_label_snapshot, payment_method_type_snapshot, amount_ars, received_at, batch_id)
                    VALUES (:id, :tenant, :sale, :method, 'Cash', 'cash', 10, '2026-10-01T12:00:00Z', :batch)
                """), {"id": identity, "tenant": tenants[tenant_index], "sale": sale_id,
                        "method": methods[tenant_index], "batch": batch_id})
        members = [uuid.uuid4(), uuid.uuid4()]
        for identity in members:
            insert_member(0, sales[0], identity)
        with pytest.raises(sa.exc.IntegrityError):
            insert_member(0, sales[1], uuid.uuid4())  # Same tenant but wrong sale.
        with pytest.raises(sa.exc.IntegrityError):
            insert_member(1, sales[2], uuid.uuid4())  # Wrong tenant.
        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as connection:
                connection.execute(sa.text("DELETE FROM sale_payment_batches WHERE tenant_id=:tenant AND id=:id"), {"tenant": tenants[0], "id": batch_id})
        with engine.connect() as connection:
            before_down = [dict(r) for r in connection.execute(sa.text("SELECT * FROM sale_payments ORDER BY id")).mappings()]
        command.downgrade(config, "0052_sale_payment_idempotency")
        assert not sa.inspect(engine).has_table("sale_payment_batches")
        assert "batch_id" not in {c["name"] for c in sa.inspect(engine).get_columns("sale_payments")}
        assert "uq_sales_tenant_id_id" not in {c["name"] for c in sa.inspect(engine).get_unique_constraints("sales")}
        with engine.connect() as connection:
            after_down = [dict(r) for r in connection.execute(sa.text("SELECT * FROM sale_payments ORDER BY id")).mappings()]
        assert after_down == [{k: v for k, v in r.items() if k != "batch_id"} for r in before_down]
        assert len(after_down) == 3
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT count(*) FROM sale_payment_batches")) == 0
            assert connection.scalar(sa.text("SELECT count(*) FROM sale_payments WHERE batch_id IS NULL")) == 3
            assert connection.scalar(sa.text("SELECT idempotency_key FROM sale_payments WHERE id=:id"), {"id": history_id}) == "individual-key"
    finally:
        engine.dispose()
        get_settings.cache_clear()

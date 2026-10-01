import os
import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.script import ScriptDirectory

from app.core.config import get_settings
from app.tests.test_service_pricing_migration import _config


def test_payment_idempotency_is_single_head_after_secretary():
    script = ScriptDirectory.from_config(_config())
    assert script.get_heads() == ["0052_sale_payment_idempotency"]
    assert script.get_current_head() == "0052_sale_payment_idempotency"
    assert script.get_revision(script.get_current_head()).down_revision == "0051_secretary_role"


def test_payment_idempotency_upgrade_preserves_history_unique_scope_and_downgrade(monkeypatch):
    # Explicit opt-in only: this test never uses the application's database URL.
    url = os.getenv("PAYMENT_IDEMPOTENCY_MIGRATION_DATABASE_URL")
    if not url:
        pytest.skip("Requires an empty disposable PAYMENT_IDEMPOTENCY_MIGRATION_DATABASE_URL")
    engine = sa.create_engine(url)
    assert engine.dialect.name == "postgresql"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    config = _config()
    tenant_ids = [uuid.uuid4(), uuid.uuid4()]
    sale_ids, method_ids = [uuid.uuid4(), uuid.uuid4()], [uuid.uuid4(), uuid.uuid4()]
    historical_id = uuid.uuid4()
    try:
        assert not sa.inspect(engine).has_table("alembic_version"), "Use an empty migration test DB"
        command.upgrade(config, "0051_secretary_role")
        with engine.begin() as connection:
            for tenant_id, sale_id, method_id in zip(tenant_ids, sale_ids, method_ids):
                connection.execute(sa.text("INSERT INTO tenants (id, name) VALUES (:id, 'P4 migration')"), {"id": tenant_id})
                connection.execute(sa.text("""
                    INSERT INTO sales (id, tenant_id, sale_date, currency, subtotal_ars, discount_total_ars, total_ars, status)
                    VALUES (:id, :tenant, '2026-10-01', 'ARS', 100, 0, 100, 'confirmed')
                """), {"id": sale_id, "tenant": tenant_id})
                connection.execute(sa.text("""
                    INSERT INTO payment_methods (id, tenant_id, label, normalized_label, type)
                    VALUES (:id, :tenant, 'Cash', 'cash', 'cash')
                """), {"id": method_id, "tenant": tenant_id})
            connection.execute(sa.text("""
                INSERT INTO sale_payments (id, tenant_id, sale_id, payment_method_id,
                    payment_method_label_snapshot, payment_method_type_snapshot, amount_ars, received_at, reference)
                VALUES (:id, :tenant, :sale, :method, 'Historic cash', 'cash', 20, '2026-10-01T12:00:00Z', 'Legacy')
            """), {"id": historical_id, "tenant": tenant_ids[0], "sale": sale_ids[0], "method": method_ids[0]})
            before = connection.execute(sa.text("SELECT * FROM sale_payments WHERE id=:id"), {"id": historical_id}).mappings().one()
        command.upgrade(config, "head")
        columns = {column["name"]: column for column in sa.inspect(engine).get_columns("sale_payments")}
        for name, length in (("idempotency_key", 128), ("idempotency_request_hash", 64)):
            assert columns[name]["nullable"] is True
            assert columns[name]["default"] is None
            assert columns[name]["type"].length == length
        index = next(index for index in sa.inspect(engine).get_indexes("sale_payments") if index["name"] == "uq_sale_payments_tenant_idempotency_key")
        assert index["unique"] and index["column_names"] == ["tenant_id", "idempotency_key"]
        assert "idempotency_key IS NOT NULL" in index["dialect_options"]["postgresql_where"]
        with engine.connect() as connection:
            after = dict(connection.execute(sa.text("SELECT * FROM sale_payments WHERE id=:id"), {"id": historical_id}).mappings().one())
        assert after.pop("idempotency_key") is None
        assert after.pop("idempotency_request_hash") is None
        assert after == dict(before)

        def insert(tenant_index, key, fingerprint):
            with engine.begin() as connection:
                connection.execute(sa.text("""
                    INSERT INTO sale_payments (id, tenant_id, sale_id, payment_method_id,
                        payment_method_label_snapshot, payment_method_type_snapshot, amount_ars, received_at,
                        idempotency_key, idempotency_request_hash)
                    VALUES (:id, :tenant, :sale, :method, 'Cash', 'cash', 10, '2026-10-01T12:00:00Z', :key, :fingerprint)
                """), {"id": uuid.uuid4(), "tenant": tenant_ids[tenant_index], "sale": sale_ids[tenant_index], "method": method_ids[tenant_index], "key": key, "fingerprint": fingerprint})

        insert(0, None, None)
        insert(0, None, None)  # Legacy requests remain repeatable.
        insert(0, "same-key", "a" * 64)
        insert(1, "same-key", "b" * 64)  # Tenant-scoped uniqueness.
        with pytest.raises(sa.exc.IntegrityError):
            insert(0, "same-key", "a" * 64)
        with engine.begin() as connection:
            connection.execute(sa.text("""
                UPDATE sale_payments SET is_active=false, voided_at=now(), void_reason='Correction'
                WHERE tenant_id=:tenant AND idempotency_key='same-key'
            """), {"tenant": tenant_ids[0]})
        with pytest.raises(sa.exc.IntegrityError):
            insert(0, "same-key", "a" * 64)  # Voiding cannot release a key.
        for key, fingerprint in (("", "a" * 64), ("key", None), (None, "a" * 64), ("key", "short")):
            with pytest.raises(sa.exc.IntegrityError):
                insert(0, key, fingerprint)
        command.downgrade(config, "0051_secretary_role")
        columns = {column["name"] for column in sa.inspect(engine).get_columns("sale_payments")}
        assert not {"idempotency_key", "idempotency_request_hash"} & columns
        assert "uq_sale_payments_tenant_idempotency_key" not in {index["name"] for index in sa.inspect(engine).get_indexes("sale_payments")}
        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT amount_ars FROM sale_payments WHERE id=:id"), {"id": historical_id}) == Decimal("20.00")
            assert connection.scalar(sa.text("SELECT count(*) FROM sale_payments")) == 5
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT count(*) FROM sale_payments WHERE idempotency_key IS NOT NULL")) == 0
    finally:
        engine.dispose()
        get_settings.cache_clear()

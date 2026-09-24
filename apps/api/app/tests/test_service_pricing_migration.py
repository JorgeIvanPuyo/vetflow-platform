import os
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.config import get_settings


def _config():
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    return config


def test_service_pricing_is_the_only_migration_head():
    assert ScriptDirectory.from_config(_config()).get_heads() == ["0050_service_pricing"]


def test_service_pricing_upgrade_preserves_legacy_rows_and_downgrade(monkeypatch):
    # Dedicated disposable DB only; never fall back to the application's URL.
    url = os.getenv("SERVICE_PRICING_MIGRATION_DATABASE_URL")
    if not url:
        pytest.skip("SERVICE_PRICING_MIGRATION_DATABASE_URL must point to an empty test database")
    engine = sa.create_engine(url)
    assert engine.dialect.name == "postgresql"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    config = _config()
    tenant_id, service_id = uuid.uuid4(), uuid.uuid4()
    try:
        assert not sa.inspect(engine).has_table("alembic_version"), "Use an empty dedicated migration test DB"
        command.upgrade(config, "0049_inventory_category_refs")
        with engine.begin() as connection:
            connection.execute(sa.text("INSERT INTO tenants (id, name) VALUES (:id, 'Migration clinic')"), {"id": tenant_id})
            connection.execute(sa.text("""
                INSERT INTO services (id, tenant_id, code, name, normalized_name, kind, default_duration_minutes)
                VALUES (:id, :tenant_id, 'LEGACY', 'Legacy service', 'legacy service', 'consultation', 30)
            """), {"id": service_id, "tenant_id": tenant_id})
        command.upgrade(config, "head")
        price_column = next(column for column in sa.inspect(engine).get_columns("services") if column["name"] == "price")
        assert price_column["nullable"] is True
        assert price_column["default"] is None
        assert (price_column["type"].precision, price_column["type"].scale) == (14, 2)
        with engine.begin() as connection:
            row = connection.execute(sa.text("SELECT name, price FROM services WHERE id = :id"), {"id": service_id}).one()
            assert row == ("Legacy service", None)
            connection.execute(sa.text("UPDATE services SET price = 25.50 WHERE id = :id"), {"id": service_id})
        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as connection:
                connection.execute(sa.text("UPDATE services SET price = -1 WHERE id = :id"), {"id": service_id})
        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT price FROM services WHERE id = :id"), {"id": service_id}) == Decimal("25.50")
        command.downgrade(config, "0049_inventory_category_refs")
        assert "price" not in {column["name"] for column in sa.inspect(engine).get_columns("services")}
        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT name FROM services WHERE id = :id"), {"id": service_id}) == "Legacy service"
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT price FROM services WHERE id = :id"), {"id": service_id}) is None
    finally:
        engine.dispose()
        get_settings.cache_clear()

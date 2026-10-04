import os
import uuid

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.script import ScriptDirectory

from app.core.config import get_settings
from app.tests.test_service_pricing_migration import _config


def test_secretary_is_followed_by_payment_idempotency():
    script = ScriptDirectory.from_config(_config())
    assert script.get_revision("0052_sale_payment_idempotency").down_revision == "0051_secretary_role"


def test_secretary_upgrade_and_safe_downgrade(monkeypatch):
    url = os.getenv("SECRETARY_MIGRATION_DATABASE_URL")
    if not url:
        pytest.skip("Requires a dedicated disposable PostgreSQL database")
    engine = sa.create_engine(url)
    assert engine.dialect.name == "postgresql"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    config = _config()
    tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
    try:
        assert not sa.inspect(engine).has_table("alembic_version"), "Use an empty test DB"
        command.upgrade(config, "0050_service_pricing")
        with engine.begin() as connection:
            connection.execute(sa.text("INSERT INTO tenants (id, name) VALUES (:id, 'Test')"), {"id": tenant_id})
            connection.execute(sa.text("""
                INSERT INTO users (id, tenant_id, email, full_name, role, is_active)
                VALUES (:id, :tenant, 'secretary@example.com', 'Secretary', 'contador', true)
            """), {"id": user_id, "tenant": tenant_id})
        command.upgrade(config, "head")
        with engine.begin() as connection:
            assert connection.scalar(sa.text("SELECT role FROM users WHERE id=:id"), {"id": user_id}) == "contador"
            connection.execute(sa.text("UPDATE users SET role='secretaria' WHERE id=:id"), {"id": user_id})
        with pytest.raises(RuntimeError, match="Reassign secretary"):
            command.downgrade(config, "0050_service_pricing")
        with engine.begin() as connection:
            assert connection.scalar(sa.text("SELECT role FROM users WHERE id=:id"), {"id": user_id}) == "secretaria"
            connection.execute(sa.text("UPDATE users SET role='contador' WHERE id=:id"), {"id": user_id})
        command.downgrade(config, "0050_service_pricing")
        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as connection:
                connection.execute(sa.text("UPDATE users SET role='secretaria' WHERE id=:id"), {"id": user_id})
        command.upgrade(config, "head")
        with engine.begin() as connection:
            connection.execute(sa.text("UPDATE users SET role='secretaria' WHERE id=:id"), {"id": user_id})
    finally:
        engine.dispose()
        get_settings.cache_clear()

"""Sale price mode backfill against an explicitly selected, empty PostgreSQL database."""

import os
import uuid

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.script import ScriptDirectory

from app.core.config import get_settings
from app.tests.test_service_pricing_migration import _config


def test_sale_price_mode_migration_is_single_head():
    script = ScriptDirectory.from_config(_config())
    assert script.get_heads() == ["0055_inventory_sale_price_mode"]
    assert (
        script.get_revision("0055_inventory_sale_price_mode").down_revision
        == "0054_receivables_foundation"
    )


def test_postgresql_backfill_marks_only_divergent_prices_manual(monkeypatch):
    url = os.getenv("SALE_PRICE_MODE_MIGRATION_DATABASE_URL")
    if not url:
        pytest.skip("Requires an empty disposable SALE_PRICE_MODE_MIGRATION_DATABASE_URL")
    engine = sa.create_engine(url)
    assert engine.dialect.name == "postgresql"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    config = _config()
    tenant_id = uuid.uuid4()
    # name -> (purchase, purchase tax, margin, sale price, round, expected manual)
    items = {
        "calculated": ("1000", "21", "35", "1633.50", False, False),
        "calculated_rounded": ("1013", "0", "35", "1370.00", True, False),
        "manual": ("26849.90", "0", "50", "64038.87", False, True),
        "manual_without_cost": (None, "0", "35", "500.00", False, True),
        "without_price": (None, "0", "35", None, False, False),
    }
    try:
        assert not sa.inspect(engine).has_table("alembic_version"), "Use an empty migration test DB"
        command.upgrade(config, "0054_receivables_foundation")
        with engine.begin() as connection:
            connection.execute(
                sa.text("INSERT INTO tenants (id, name) VALUES (:id, 'Sale price mode')"),
                {"id": tenant_id},
            )
            for index, (name, values) in enumerate(items.items()):
                purchase, tax, margin, sale, round_price, _ = values
                connection.execute(
                    sa.text("""
                        INSERT INTO inventory_items (
                            id, tenant_id, internal_code, name, category, unit,
                            current_stock, minimum_stock, purchase_price_ars,
                            purchase_tax_rate_percentage, profit_margin_percentage,
                            sale_price_ars, sale_tax_rate_percentage, round_sale_price, is_active
                        ) VALUES (
                            :id, :tenant, :code, :name, 'medication', 'tablet',
                            0, 0, :purchase, :tax, :margin, :sale, 0, :round_price, true
                        )
                    """),
                    {
                        "id": uuid.uuid4(),
                        "tenant": tenant_id,
                        "code": f"MED-{index:05d}",
                        "name": name,
                        "purchase": purchase,
                        "tax": tax,
                        "margin": margin,
                        "sale": sale,
                        "round_price": round_price,
                    },
                )

        command.upgrade(config, "head")
        with engine.connect() as connection:
            rows = dict(
                connection.execute(
                    sa.text("SELECT name, sale_price_is_manual FROM inventory_items")
                ).all()
            )
        assert rows == {name: values[5] for name, values in items.items()}

        command.downgrade(config, "0054_receivables_foundation")
        columns = {column["name"] for column in sa.inspect(engine).get_columns("inventory_items")}
        assert "sale_price_is_manual" not in columns
    finally:
        engine.dispose()
        get_settings.cache_clear()

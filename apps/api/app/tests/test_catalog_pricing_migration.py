"""Frozen data migration verified on disposable in-memory fixtures only."""
import importlib.util
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.inventory_pricing import calculate_catalog_sale_price


def _migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0060_inventory_calculated_prices.py"
    spec = importlib.util.spec_from_file_location("catalog_pricing_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_catalog_migration_head():
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0062_purchase_return_agreed"]
    assert script.get_revision("0060_inventory_calculated_prices").down_revision == "0059_merge_arca_inventory"


def test_upgrade_two_tenants_pending_zero_and_idempotence(caplog):
    migration = _migration()
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    items = sa.Table("inventory_items", metadata,
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("tenant_id", sa.Integer),
        sa.Column("purchase_price_ars", sa.Numeric(12, 2)),
        sa.Column("purchase_tax_rate_percentage", sa.Numeric(5, 2)),
        sa.Column("profit_margin_percentage", sa.Numeric(8, 2)),
        sa.Column("sale_price_ars", sa.Numeric(12, 2)),
        sa.Column("sale_price_is_manual", sa.Boolean), sa.Column("round_sale_price", sa.Boolean),
        sa.Column("updated_at", sa.DateTime),
    )
    preferences = sa.Table("tenant_preferences", metadata,
        sa.Column("tenant_id", sa.Integer, primary_key=True), sa.Column("money_rounding_increment", sa.Numeric(12, 2)))
    sa.Table("purchase_items", metadata, sa.Column("id", sa.Integer, primary_key=True), sa.Column("unit_price_without_tax_ars", sa.Numeric(12, 2)))
    metadata.create_all(engine)
    old = datetime(2020, 1, 1)
    fixtures = [
        (1, 1, "100", "21", "30", "999", True, True),
        (2, 2, "100", "21", "30", "999", True, True),
        (3, 1, None, "21", "30", "800", True, False),
        (4, 2, "100", "21", None, "700", True, False),
        (5, 2, "0", "21", "0", "500", True, False),
        (6, 1, "100", "21", "30", "157.30", False, False),
        (7, 3, "100", "21", "30", "999", True, True),
    ]
    try:
        with engine.begin() as bind:
            bind.execute(preferences.insert(), [{"tenant_id": 1, "money_rounding_increment": Decimal("10")}, {"tenant_id": 2, "money_rounding_increment": Decimal("25")}])
            for id_, tenant, cost, tax, margin, sale, manual, rounded in fixtures:
                bind.execute(items.insert().values(id=id_, tenant_id=tenant, purchase_price_ars=cost,
                    purchase_tax_rate_percentage=tax, profit_margin_percentage=margin, sale_price_ars=sale,
                    sale_price_is_manual=manual, round_sale_price=rounded, updated_at=old))
            bind.execute(sa.text("INSERT INTO purchase_items VALUES (1, 87)"))
            caplog.set_level("INFO", logger="alembic.runtime.migration")
            with Operations.context(MigrationContext.configure(bind)):
                migration.upgrade()
            rows = {row.id: row for row in bind.execute(sa.select(items)).mappings()}
            assert rows[1]["sale_price_ars"] == Decimal("160")
            assert rows[2]["sale_price_ars"] == Decimal("150")
            assert rows[3]["sale_price_ars"] == Decimal("800")
            assert rows[4]["sale_price_ars"] == Decimal("700")
            assert rows[5]["sale_price_ars"] == Decimal("0")
            for id_ in (1, 2, 5, 7):
                assert rows[id_]["sale_price_is_manual"] is False
                assert rows[id_]["updated_at"] > old
            for id_ in (3, 4, 6):
                assert rows[id_]["updated_at"] == old
            assert bind.scalar(sa.text("SELECT unit_price_without_tax_ars FROM purchase_items")) == 87
            assert bind.scalar(sa.text("SELECT catalog_cost_updated FROM purchase_items")) is None
            assert "'converted': 4, 'pending': 2" in caplog.text
            assert migration.normalize_catalog_prices(bind) == {"converted": 0, "pending": 2}
            for _, tenant, cost, tax, margin, _, _, rounded in fixtures:
                kwargs = dict(purchase_price_ars=None if cost is None else Decimal(cost),
                    purchase_tax_rate_percentage=Decimal(tax), profit_margin_percentage=None if margin is None else Decimal(margin),
                    round_sale_price=rounded, rounding_increment=Decimal("25" if tenant == 2 else "10"))
                assert calculate_catalog_sale_price(**kwargs) == migration._calculated_price(cost, tax, margin, rounded, kwargs["rounding_increment"])
    finally:
        engine.dispose()

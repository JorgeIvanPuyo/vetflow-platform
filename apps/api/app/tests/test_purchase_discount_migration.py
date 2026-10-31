import importlib.util
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory


def _migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0061_purchase_global_discount.py"
    spec = importlib.util.spec_from_file_location("purchase_discount_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_discount_migration_graph():
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0062_purchase_return_agreed"]
    assert script.get_revision("0062_purchase_return_agreed").down_revision == "0061_purchase_global_discount"
    assert script.get_revision("0061_purchase_global_discount").down_revision == "0060_inventory_calculated_prices"


def test_historical_defaults_old_writers_constraints_and_guarded_downgrade():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    purchases = sa.Table("purchases", metadata,
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("tenant_id", sa.Integer),
        sa.Column("total_ars", sa.Numeric(16, 2), nullable=False),
        sa.Column("tax_total_ars", sa.Numeric(16, 2)),
        sa.Column("updated_at", sa.DateTime), sa.Column("status", sa.String),
    )
    metadata.create_all(engine)
    migration = _migration()
    try:
        with engine.begin() as bind:
            bind.execute(purchases.insert(), [
                {"id": 1, "tenant_id": 1, "total_ars": Decimal("1000"), "tax_total_ars": Decimal("0"), "updated_at": datetime(2020, 1, 1), "status": "received"},
                {"id": 2, "tenant_id": 2, "total_ars": Decimal("1210.05"), "tax_total_ars": Decimal("210.05"), "updated_at": datetime(2020, 2, 1), "status": "draft"},
                {"id": 3, "tenant_id": 1, "total_ars": Decimal("0"), "tax_total_ars": Decimal("0"), "updated_at": datetime(2020, 3, 1), "status": "cancelled"},
            ])
            before = bind.execute(sa.select(purchases).order_by(purchases.c.id)).all()
            with Operations.context(MigrationContext.configure(bind)):
                migration.upgrade()
            assert bind.execute(sa.select(purchases).order_by(purchases.c.id)).all() == before
            assert bind.execute(sa.text("SELECT discount_type, discount_value, discount_amount_ars FROM purchases ORDER BY id")).all() == [("none", 0, 0)] * 3
            assert bind.execute(sa.text("SELECT total_ars - discount_amount_ars FROM purchases ORDER BY id")).scalars().all() == [1000, 1210.05, 0]
            # An older writer omits the new columns: payable remains gross, never zero.
            bind.execute(sa.text("INSERT INTO purchases (id, tenant_id, total_ars) VALUES (4, 2, 123)"))
            assert bind.scalar(sa.text("SELECT total_ars - discount_amount_ars FROM purchases WHERE id=4")) == 123
            for mode, value, amount in [("unknown", 0, 0), ("none", 1, 0), ("amount", -1, -1), ("amount", 101, 101), ("amount", 50, 40), ("percentage", 101, 100)]:
                with pytest.raises(sa.exc.IntegrityError):
                    with bind.begin_nested():
                        bind.execute(sa.text("INSERT INTO purchases (id,total_ars,discount_type,discount_value,discount_amount_ars) VALUES (9,100,:mode,:value,:amount)"), dict(mode=mode, value=value, amount=amount))
            bind.execute(sa.text("INSERT INTO purchases (id,total_ars,discount_type,discount_value,discount_amount_ars) VALUES (5,100,'amount',100,100)"))
            assert bind.scalar(sa.text("SELECT total_ars - discount_amount_ars FROM purchases WHERE id=5")) == 0
            with Operations.context(MigrationContext.configure(bind)):
                with pytest.raises(RuntimeError, match="rollback"):
                    migration.downgrade()
            assert "discount_amount_ars" in {column["name"] for column in sa.inspect(bind).get_columns("purchases")}
    finally:
        engine.dispose()

"""Normalize complete manual catalog prices; retain incomplete legacy references.

The arithmetic is intentionally frozen here, independent of application imports.
Old manual amounts are not archived: a downgrade cannot reconstruct them.
"""
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import logging

import sqlalchemy as sa
from alembic import op

revision = "0060_inventory_calculated_prices"
down_revision = "0059_merge_arca_inventory"
branch_labels = None
depends_on = None


def _calculated_price(cost, tax, margin, rounded, increment):
    if cost is None or margin is None:
        return None
    cost, tax, margin, increment = map(Decimal, (cost, tax or 0, margin, increment))
    if cost < 0 or margin < 0 or not 0 <= tax <= 100 or increment <= 0:
        raise ValueError("Invalid catalog pricing data; normalization aborted")
    quantum = Decimal("0.01")
    tax_amount = (cost * tax / 100).quantize(quantum, rounding=ROUND_HALF_UP)
    taxed_cost = (cost + tax_amount).quantize(quantum, rounding=ROUND_HALF_UP)
    price = (taxed_cost * (1 + margin / 100)).quantize(quantum, rounding=ROUND_HALF_UP)
    if rounded:
        price = (price / increment).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * increment
    if price > Decimal("9999999999.99"):
        raise ValueError("Calculated catalog price exceeds monetary limit; normalization aborted")
    return price


def normalize_catalog_prices(bind):
    metadata = sa.MetaData()
    items = sa.Table("inventory_items", metadata, autoload_with=bind)
    preferences = sa.Table("tenant_preferences", metadata, autoload_with=bind)
    # Explicit administrative data migration: all tenants, each joined to its own preferences.
    rows = bind.execute(sa.select(
        items.c.id, items.c.tenant_id, items.c.updated_at, items.c.purchase_price_ars,
        items.c.purchase_tax_rate_percentage, items.c.profit_margin_percentage,
        items.c.sale_price_ars, items.c.sale_price_is_manual, items.c.round_sale_price,
        sa.func.coalesce(preferences.c.money_rounding_increment, 10).label("increment"),
    ).select_from(items.outerjoin(preferences, preferences.c.tenant_id == items.c.tenant_id))).mappings()
    converted = pending = 0
    for row in rows:
        if row["purchase_price_ars"] is None or row["profit_margin_percentage"] is None:
            pending += 1
            continue
        if not row["sale_price_is_manual"]:
            continue
        price = _calculated_price(
            row["purchase_price_ars"], row["purchase_tax_rate_percentage"],
            row["profit_margin_percentage"], row["round_sale_price"], row["increment"],
        )
        now = datetime.now(UTC)
        previous = row["updated_at"]
        if previous is not None:
            previous = previous.replace(tzinfo=UTC) if previous.tzinfo is None else previous
            now = max(now, previous + timedelta(microseconds=1))
        bind.execute(items.update().where(
            items.c.id == row["id"], items.c.tenant_id == row["tenant_id"],
        ).values(sale_price_ars=price, sale_price_is_manual=False, updated_at=now))
        converted += 1
    summary = {"converted": converted, "pending": pending}
    logging.getLogger("alembic.runtime.migration").info("Inventory pricing normalization: %s", summary)
    return summary


def upgrade():
    op.add_column("purchase_items", sa.Column("catalog_cost_updated", sa.Boolean(), nullable=True))
    normalize_catalog_prices(op.get_bind())


def downgrade():
    raise RuntimeError("Irreversible data normalization: previous manual catalog prices were not archived")

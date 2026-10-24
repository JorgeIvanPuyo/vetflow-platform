"""persist whether an inventory sale price is manual or calculated from margin"""

import sqlalchemy as sa
from alembic import op


revision = "0055_inventory_sale_price_mode"
down_revision = "0054_receivables_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_items",
        sa.Column(
            "sale_price_is_manual",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    # Conservative backfill: a stored price is considered manual only when it
    # differs from what the current margin formula would produce. This mirrors
    # the heuristic the web client used before the mode was persisted, so no
    # sale price changes as a side effect of the migration.
    op.execute(
        """
        WITH calculated AS (
            SELECT
                item.id,
                ROUND(
                    ROUND(
                        item.purchase_price_ars
                        + ROUND(item.purchase_price_ars * item.purchase_tax_rate_percentage / 100, 2),
                        2
                    ) * (1 + item.profit_margin_percentage / 100),
                    2
                ) AS raw_price,
                item.round_sale_price,
                COALESCE(preferences.money_rounding_increment, 10) AS rounding_increment
            FROM inventory_items AS item
            LEFT JOIN tenant_preferences AS preferences
                ON preferences.tenant_id = item.tenant_id
            WHERE item.sale_price_ars IS NOT NULL
        )
        UPDATE inventory_items AS item
        SET sale_price_is_manual = true
        FROM calculated
        WHERE item.id = calculated.id
          AND (
              calculated.raw_price IS NULL
              OR ABS(
                  item.sale_price_ars
                  - CASE
                      WHEN calculated.round_sale_price AND calculated.rounding_increment > 0
                      THEN ROUND(calculated.raw_price / calculated.rounding_increment)
                          * calculated.rounding_increment
                      ELSE calculated.raw_price
                  END
              ) > 0.01
          )
        """
    )


def downgrade() -> None:
    op.drop_column("inventory_items", "sale_price_is_manual")

"""add tax rate, profit margin, and rounding increment to tenant preferences"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0042_tenant_pref_money"
down_revision = "0041_catalog_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_preferences",
        sa.Column(
            "default_purchase_tax_rate",
            sa.Numeric(5, 2),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "tenant_preferences",
        sa.Column(
            "default_sale_tax_rate",
            sa.Numeric(5, 2),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "tenant_preferences",
        sa.Column(
            "default_profit_margin",
            sa.Numeric(8, 2),
            server_default="35",
            nullable=False,
        ),
    )
    op.add_column(
        "tenant_preferences",
        sa.Column(
            "money_rounding_increment",
            sa.Numeric(12, 2),
            server_default="10",
            nullable=False,
        ),
    )

    # Preserve each existing tenant's observed inventory behavior instead of
    # imposing a single regional tax or margin value. For tenants with inventory,
    # seed each preference from the most common historical value. Deterministic
    # tie-breakers prefer the lower tax rate and the margin closest to the
    # application fallback of 35%. Tenants without inventory keep the column
    # defaults (0% purchase tax, 0% sale tax, 35% margin). Existing item snapshots
    # are never rewritten.
    op.execute(
        """
        UPDATE tenant_preferences AS tp
        SET
            default_purchase_tax_rate = COALESCE((
                SELECT ii.purchase_tax_rate_percentage
                FROM inventory_items AS ii
                WHERE ii.tenant_id = tp.tenant_id
                GROUP BY ii.purchase_tax_rate_percentage
                ORDER BY COUNT(*) DESC, ii.purchase_tax_rate_percentage ASC
                LIMIT 1
            ), 0),
            default_sale_tax_rate = COALESCE((
                SELECT ii.sale_tax_rate_percentage
                FROM inventory_items AS ii
                WHERE ii.tenant_id = tp.tenant_id
                GROUP BY ii.sale_tax_rate_percentage
                ORDER BY COUNT(*) DESC, ii.sale_tax_rate_percentage ASC
                LIMIT 1
            ), 0),
            default_profit_margin = COALESCE((
                SELECT ii.profit_margin_percentage
                FROM inventory_items AS ii
                WHERE ii.tenant_id = tp.tenant_id
                GROUP BY ii.profit_margin_percentage
                ORDER BY
                    COUNT(*) DESC,
                    ABS(ii.profit_margin_percentage - 35) ASC,
                    ii.profit_margin_percentage ASC
                LIMIT 1
            ), 35)
        """
    )


def downgrade() -> None:
    op.drop_column("tenant_preferences", "money_rounding_increment")
    op.drop_column("tenant_preferences", "default_profit_margin")
    op.drop_column("tenant_preferences", "default_sale_tax_rate")
    op.drop_column("tenant_preferences", "default_purchase_tax_rate")

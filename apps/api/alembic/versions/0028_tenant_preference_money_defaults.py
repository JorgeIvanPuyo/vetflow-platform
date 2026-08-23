"""add tax rate, profit margin, and rounding increment to tenant preferences"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0028_tenant_pref_money"
down_revision = "0027_catalog_items"
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


def downgrade() -> None:
    op.drop_column("tenant_preferences", "money_rounding_increment")
    op.drop_column("tenant_preferences", "default_profit_margin")
    op.drop_column("tenant_preferences", "default_sale_tax_rate")
    op.drop_column("tenant_preferences", "default_purchase_tax_rate")

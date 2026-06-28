"""add inventory item purchase and sale tax rates"""

import sqlalchemy as sa
from alembic import op

revision = "0023_inventory_item_tax_rates"
down_revision = "0022_consultation_ai_summary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_items",
        sa.Column(
            "purchase_tax_rate_percentage",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "inventory_items",
        sa.Column(
            "sale_tax_rate_percentage",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("inventory_items", "sale_tax_rate_percentage")
    op.drop_column("inventory_items", "purchase_tax_rate_percentage")

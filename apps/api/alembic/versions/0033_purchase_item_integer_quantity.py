"""require integer quantities in purchase items"""

from __future__ import annotations

from alembic import op


revision = "0033_purchase_quantity_integer"
down_revision = "0032_purchase_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_purchase_items_quantity_integer",
        "purchase_items",
        "quantity = trunc(quantity)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_purchase_items_quantity_integer",
        "purchase_items",
        type_="check",
    )

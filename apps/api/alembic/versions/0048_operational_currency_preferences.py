"""make operational currency and pricing defaults tenant-driven"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0048_operational_currency"
down_revision = "0047_backfill_species_refs"
branch_labels = None
depends_on = None


_CURRENCY_CHECK = "length(currency) = 3 AND currency = upper(currency)"


def upgrade() -> None:
    for table_name, constraint_name in (
        ("purchases", "ck_purchases_currency"),
        ("purchase_returns", "ck_purchase_returns_currency"),
        ("sales", "ck_sales_currency"),
    ):
        op.drop_constraint(constraint_name, table_name, type_="check")
        op.create_check_constraint(constraint_name, table_name, _CURRENCY_CHECK)
        op.alter_column(
            table_name,
            "currency",
            existing_type=sa.String(length=3),
            existing_nullable=False,
            server_default=None,
        )

    op.alter_column(
        "purchase_items",
        "tax_rate_percentage",
        existing_type=sa.Numeric(precision=5, scale=2),
        existing_nullable=False,
        server_default=None,
    )
    for column_name, column_type in (
        ("purchase_tax_rate_percentage", sa.Numeric(precision=5, scale=2)),
        ("sale_tax_rate_percentage", sa.Numeric(precision=5, scale=2)),
        ("profit_margin_percentage", sa.Numeric(precision=8, scale=2)),
    ):
        op.alter_column(
            "inventory_items",
            column_name,
            existing_type=column_type,
            existing_nullable=False,
            server_default=None,
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in ("purchases", "purchase_returns", "sales"):
        non_ars_count = bind.execute(
            sa.text(f"SELECT COUNT(*) FROM {table_name} WHERE currency <> 'ARS'")
        ).scalar_one()
        if non_ars_count:
            raise RuntimeError(
                f"Cannot downgrade 0048 while {table_name} contains non-ARS rows"
            )

    for table_name, constraint_name in (
        ("purchases", "ck_purchases_currency"),
        ("purchase_returns", "ck_purchase_returns_currency"),
        ("sales", "ck_sales_currency"),
    ):
        op.drop_constraint(constraint_name, table_name, type_="check")
        op.create_check_constraint(constraint_name, table_name, "currency = 'ARS'")
        op.alter_column(
            table_name,
            "currency",
            existing_type=sa.String(length=3),
            existing_nullable=False,
            server_default="ARS",
        )

    op.alter_column(
        "purchase_items",
        "tax_rate_percentage",
        existing_type=sa.Numeric(precision=5, scale=2),
        existing_nullable=False,
        server_default="21",
    )
    op.alter_column(
        "inventory_items",
        "purchase_tax_rate_percentage",
        existing_type=sa.Numeric(precision=5, scale=2),
        existing_nullable=False,
        server_default="21",
    )
    op.alter_column(
        "inventory_items",
        "sale_tax_rate_percentage",
        existing_type=sa.Numeric(precision=5, scale=2),
        existing_nullable=False,
        server_default="0",
    )
    op.alter_column(
        "inventory_items",
        "profit_margin_percentage",
        existing_type=sa.Numeric(precision=8, scale=2),
        existing_nullable=False,
        server_default="35",
    )

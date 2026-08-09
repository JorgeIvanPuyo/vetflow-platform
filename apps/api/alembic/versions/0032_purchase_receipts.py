"""add purchase receipt and reversal traceability"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0032_purchase_receipts"
down_revision = "0031_create_suppliers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_purchases_status", "purchases", type_="check")
    op.create_check_constraint(
        "ck_purchases_status",
        "purchases",
        "status IN ('draft', 'cancelled', 'received', 'partially_received', 'returned', 'reversed')",
    )
    op.add_column("purchases", sa.Column("received_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("purchases", sa.Column("received_by_user_id", sa.Uuid(), nullable=True))
    op.add_column("purchases", sa.Column("inventory_operation_id", sa.Uuid(), nullable=True))
    op.add_column("purchases", sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("purchases", sa.Column("reversed_by_user_id", sa.Uuid(), nullable=True))
    op.add_column("purchases", sa.Column("reversal_reason", sa.Text(), nullable=True))
    op.add_column("purchases", sa.Column("reversal_operation_id", sa.Uuid(), nullable=True))
    op.add_column(
        "purchases",
        sa.Column(
            "reversal_cost_warning",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_purchases_received_by_user_id_users",
        "purchases",
        "users",
        ["received_by_user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_purchases_reversed_by_user_id_users",
        "purchases",
        "users",
        ["reversed_by_user_id"],
        ["id"],
    )
    op.create_index(op.f("ix_purchases_received_by_user_id"), "purchases", ["received_by_user_id"])
    op.create_index(op.f("ix_purchases_inventory_operation_id"), "purchases", ["inventory_operation_id"])
    op.create_index(op.f("ix_purchases_reversed_by_user_id"), "purchases", ["reversed_by_user_id"])
    op.create_index(op.f("ix_purchases_reversal_operation_id"), "purchases", ["reversal_operation_id"])
    op.create_index(
        "ix_purchases_tenant_inventory_operation",
        "purchases",
        ["tenant_id", "inventory_operation_id"],
    )

    op.add_column(
        "purchase_items",
        sa.Column("previous_purchase_price_ars", sa.Numeric(precision=14, scale=2), nullable=True),
    )
    op.add_column(
        "purchase_items",
        sa.Column(
            "previous_purchase_tax_rate_percentage",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("purchase_items", "previous_purchase_tax_rate_percentage")
    op.drop_column("purchase_items", "previous_purchase_price_ars")

    op.drop_index("ix_purchases_tenant_inventory_operation", table_name="purchases")
    op.drop_index(op.f("ix_purchases_reversal_operation_id"), table_name="purchases")
    op.drop_index(op.f("ix_purchases_reversed_by_user_id"), table_name="purchases")
    op.drop_index(op.f("ix_purchases_inventory_operation_id"), table_name="purchases")
    op.drop_index(op.f("ix_purchases_received_by_user_id"), table_name="purchases")
    op.drop_constraint(
        "fk_purchases_reversed_by_user_id_users", "purchases", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_purchases_received_by_user_id_users", "purchases", type_="foreignkey"
    )
    op.drop_column("purchases", "reversal_cost_warning")
    op.drop_column("purchases", "reversal_operation_id")
    op.drop_column("purchases", "reversal_reason")
    op.drop_column("purchases", "reversed_by_user_id")
    op.drop_column("purchases", "reversed_at")
    op.drop_column("purchases", "inventory_operation_id")
    op.drop_column("purchases", "received_by_user_id")
    op.drop_column("purchases", "received_at")
    op.drop_constraint("ck_purchases_status", "purchases", type_="check")
    op.create_check_constraint(
        "ck_purchases_status",
        "purchases",
        "status IN ('draft', 'cancelled', 'received', 'partially_received', 'returned')",
    )

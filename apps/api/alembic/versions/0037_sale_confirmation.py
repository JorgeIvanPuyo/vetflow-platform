"""add sale confirmation and reversal traceability"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0037_sale_confirmation"
down_revision = "0036_sales_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sales", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sales", sa.Column("confirmed_by_user_id", sa.Uuid(), nullable=True))
    op.add_column("sales", sa.Column("inventory_operation_id", sa.Uuid(), nullable=True))
    op.add_column("sales", sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sales", sa.Column("reversed_by_user_id", sa.Uuid(), nullable=True))
    op.add_column("sales", sa.Column("reversal_reason", sa.Text(), nullable=True))
    op.add_column("sales", sa.Column("reversal_operation_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_sales_confirmed_by_user_id_users",
        "sales",
        "users",
        ["confirmed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_sales_reversed_by_user_id_users",
        "sales",
        "users",
        ["reversed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_sales_confirmed_by_user_id"), "sales", ["confirmed_by_user_id"])
    op.create_index(op.f("ix_sales_inventory_operation_id"), "sales", ["inventory_operation_id"])
    op.create_index(op.f("ix_sales_reversed_by_user_id"), "sales", ["reversed_by_user_id"])
    op.create_index(op.f("ix_sales_reversal_operation_id"), "sales", ["reversal_operation_id"])
    op.create_index(
        "ix_sales_tenant_inventory_operation",
        "sales",
        ["tenant_id", "inventory_operation_id"],
    )
    op.create_index(
        "ix_sales_tenant_reversal_operation",
        "sales",
        ["tenant_id", "reversal_operation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sales_tenant_reversal_operation", table_name="sales")
    op.drop_index("ix_sales_tenant_inventory_operation", table_name="sales")
    op.drop_index(op.f("ix_sales_reversal_operation_id"), table_name="sales")
    op.drop_index(op.f("ix_sales_reversed_by_user_id"), table_name="sales")
    op.drop_index(op.f("ix_sales_inventory_operation_id"), table_name="sales")
    op.drop_index(op.f("ix_sales_confirmed_by_user_id"), table_name="sales")
    op.drop_constraint("fk_sales_reversed_by_user_id_users", "sales", type_="foreignkey")
    op.drop_constraint("fk_sales_confirmed_by_user_id_users", "sales", type_="foreignkey")
    op.drop_column("sales", "reversal_operation_id")
    op.drop_column("sales", "reversal_reason")
    op.drop_column("sales", "reversed_by_user_id")
    op.drop_column("sales", "reversed_at")
    op.drop_column("sales", "inventory_operation_id")
    op.drop_column("sales", "confirmed_by_user_id")
    op.drop_column("sales", "confirmed_at")

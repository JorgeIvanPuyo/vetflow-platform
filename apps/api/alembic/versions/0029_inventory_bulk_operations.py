"""inventory bulk operations"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0029_inventory_bulk_operations"
down_revision = "0028_inventory_imports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_bulk_operations",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("operation_type", sa.String(length=80), nullable=False),
        sa.Column("selection_mode", sa.String(length=30), nullable=False),
        sa.Column("filters_json", sa.JSON(), nullable=True),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("selected_count", sa.Integer(), nullable=False),
        sa.Column("affected_count", sa.Integer(), nullable=False),
        sa.Column("unchanged_count", sa.Integer(), nullable=False),
        sa.Column("invalid_count", sa.Integer(), nullable=False),
        sa.Column("excluded_count", sa.Integer(), nullable=False),
        sa.Column("reversed_count", sa.Integer(), nullable=False),
        sa.Column("conflict_count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reversal_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reversed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inventory_bulk_operations_tenant_created_at", "inventory_bulk_operations", ["tenant_id", "created_at"])
    op.create_index("ix_inventory_bulk_operations_tenant_status", "inventory_bulk_operations", ["tenant_id", "status"])
    op.create_index("ix_inventory_bulk_operations_tenant_created_by", "inventory_bulk_operations", ["tenant_id", "created_by_user_id"])
    op.create_index(op.f("ix_inventory_bulk_operations_created_by_user_id"), "inventory_bulk_operations", ["created_by_user_id"])
    op.create_index(op.f("ix_inventory_bulk_operations_operation_type"), "inventory_bulk_operations", ["operation_type"])
    op.create_index(op.f("ix_inventory_bulk_operations_status"), "inventory_bulk_operations", ["status"])
    op.create_index(op.f("ix_inventory_bulk_operations_tenant_id"), "inventory_bulk_operations", ["tenant_id"])

    op.create_table(
        "inventory_bulk_operation_items",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.String(length=80), nullable=False),
        sa.Column("old_value_json", sa.JSON(), nullable=True),
        sa.Column("new_value_json", sa.JSON(), nullable=True),
        sa.Column("product_updated_at_snapshot", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"]),
        sa.ForeignKeyConstraint(["operation_id"], ["inventory_bulk_operations.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inventory_bulk_items_operation_status", "inventory_bulk_operation_items", ["operation_id", "status"])
    op.create_index("ix_inventory_bulk_items_tenant_inventory_item", "inventory_bulk_operation_items", ["tenant_id", "inventory_item_id"])
    op.create_index("ix_inventory_bulk_items_operation_inventory_item", "inventory_bulk_operation_items", ["operation_id", "inventory_item_id"])
    op.create_index(op.f("ix_inventory_bulk_operation_items_inventory_item_id"), "inventory_bulk_operation_items", ["inventory_item_id"])
    op.create_index(op.f("ix_inventory_bulk_operation_items_operation_id"), "inventory_bulk_operation_items", ["operation_id"])
    op.create_index(op.f("ix_inventory_bulk_operation_items_status"), "inventory_bulk_operation_items", ["status"])
    op.create_index(op.f("ix_inventory_bulk_operation_items_tenant_id"), "inventory_bulk_operation_items", ["tenant_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_inventory_bulk_operation_items_tenant_id"), table_name="inventory_bulk_operation_items")
    op.drop_index(op.f("ix_inventory_bulk_operation_items_status"), table_name="inventory_bulk_operation_items")
    op.drop_index(op.f("ix_inventory_bulk_operation_items_operation_id"), table_name="inventory_bulk_operation_items")
    op.drop_index(op.f("ix_inventory_bulk_operation_items_inventory_item_id"), table_name="inventory_bulk_operation_items")
    op.drop_index("ix_inventory_bulk_items_operation_inventory_item", table_name="inventory_bulk_operation_items")
    op.drop_index("ix_inventory_bulk_items_tenant_inventory_item", table_name="inventory_bulk_operation_items")
    op.drop_index("ix_inventory_bulk_items_operation_status", table_name="inventory_bulk_operation_items")
    op.drop_table("inventory_bulk_operation_items")

    op.drop_index(op.f("ix_inventory_bulk_operations_tenant_id"), table_name="inventory_bulk_operations")
    op.drop_index(op.f("ix_inventory_bulk_operations_status"), table_name="inventory_bulk_operations")
    op.drop_index(op.f("ix_inventory_bulk_operations_operation_type"), table_name="inventory_bulk_operations")
    op.drop_index(op.f("ix_inventory_bulk_operations_created_by_user_id"), table_name="inventory_bulk_operations")
    op.drop_index("ix_inventory_bulk_operations_tenant_created_by", table_name="inventory_bulk_operations")
    op.drop_index("ix_inventory_bulk_operations_tenant_status", table_name="inventory_bulk_operations")
    op.drop_index("ix_inventory_bulk_operations_tenant_created_at", table_name="inventory_bulk_operations")
    op.drop_table("inventory_bulk_operations")

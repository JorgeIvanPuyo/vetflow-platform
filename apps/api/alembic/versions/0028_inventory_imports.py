"""inventory imports"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0028_inventory_imports"
down_revision = "0027_inventory_traceability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_imports",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("mode", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("valid_count", sa.Integer(), nullable=False),
        sa.Column("warning_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inventory_imports_tenant_created_at", "inventory_imports", ["tenant_id", "created_at"])
    op.create_index("ix_inventory_imports_tenant_status", "inventory_imports", ["tenant_id", "status"])
    op.create_index("ix_inventory_imports_tenant_file_hash_mode", "inventory_imports", ["tenant_id", "file_hash", "mode"])
    op.create_index("ix_inventory_imports_tenant_operation_id", "inventory_imports", ["tenant_id", "operation_id"])
    op.create_index(op.f("ix_inventory_imports_created_by_user_id"), "inventory_imports", ["created_by_user_id"])
    op.create_index(op.f("ix_inventory_imports_file_hash"), "inventory_imports", ["file_hash"])
    op.create_index(op.f("ix_inventory_imports_mode"), "inventory_imports", ["mode"])
    op.create_index(op.f("ix_inventory_imports_status"), "inventory_imports", ["status"])
    op.create_index(op.f("ix_inventory_imports_tenant_id"), "inventory_imports", ["tenant_id"])

    op.create_table(
        "inventory_import_rows",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("normalized_data", sa.JSON(), nullable=False),
        sa.Column("existing_inventory_item_id", sa.Uuid(), nullable=True),
        sa.Column("match_type", sa.String(length=50), nullable=False),
        sa.Column("proposed_action", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("product_snapshot", sa.JSON(), nullable=True),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("stock_current", sa.Numeric(12, 2), nullable=True),
        sa.Column("stock_target", sa.Numeric(12, 2), nullable=True),
        sa.Column("stock_delta", sa.Numeric(12, 2), nullable=True),
        sa.Column("expected_movement_type", sa.String(length=50), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["existing_inventory_item_id"], ["inventory_items.id"]),
        sa.ForeignKeyConstraint(["import_id"], ["inventory_imports.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inventory_import_rows_import_row_number", "inventory_import_rows", ["import_id", "row_number"])
    op.create_index(op.f("ix_inventory_import_rows_existing_inventory_item_id"), "inventory_import_rows", ["existing_inventory_item_id"])
    op.create_index(op.f("ix_inventory_import_rows_import_id"), "inventory_import_rows", ["import_id"])
    op.create_index(op.f("ix_inventory_import_rows_status"), "inventory_import_rows", ["status"])
    op.create_index(op.f("ix_inventory_import_rows_tenant_id"), "inventory_import_rows", ["tenant_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_inventory_import_rows_tenant_id"), table_name="inventory_import_rows")
    op.drop_index(op.f("ix_inventory_import_rows_status"), table_name="inventory_import_rows")
    op.drop_index(op.f("ix_inventory_import_rows_import_id"), table_name="inventory_import_rows")
    op.drop_index(op.f("ix_inventory_import_rows_existing_inventory_item_id"), table_name="inventory_import_rows")
    op.drop_index("ix_inventory_import_rows_import_row_number", table_name="inventory_import_rows")
    op.drop_table("inventory_import_rows")

    op.drop_index(op.f("ix_inventory_imports_tenant_id"), table_name="inventory_imports")
    op.drop_index(op.f("ix_inventory_imports_status"), table_name="inventory_imports")
    op.drop_index(op.f("ix_inventory_imports_mode"), table_name="inventory_imports")
    op.drop_index(op.f("ix_inventory_imports_file_hash"), table_name="inventory_imports")
    op.drop_index(op.f("ix_inventory_imports_created_by_user_id"), table_name="inventory_imports")
    op.drop_index("ix_inventory_imports_tenant_operation_id", table_name="inventory_imports")
    op.drop_index("ix_inventory_imports_tenant_file_hash_mode", table_name="inventory_imports")
    op.drop_index("ix_inventory_imports_tenant_status", table_name="inventory_imports")
    op.drop_index("ix_inventory_imports_tenant_created_at", table_name="inventory_imports")
    op.drop_table("inventory_imports")

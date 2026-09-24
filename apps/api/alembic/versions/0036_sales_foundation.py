"""create sales foundation"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0036_sales_foundation"
down_revision = "0035_purchase_returns"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "sales",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("patient_id", sa.Uuid(), nullable=True),
        sa.Column("owner_name_snapshot", sa.String(length=255), nullable=True),
        sa.Column("owner_document_snapshot", sa.String(length=100), nullable=True),
        sa.Column("owner_email_snapshot", sa.String(length=255), nullable=True),
        sa.Column("patient_name_snapshot", sa.String(length=255), nullable=True),
        sa.Column("patient_species_snapshot", sa.String(length=100), nullable=True),
        sa.Column("sale_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="ARS", nullable=False),
        sa.Column("subtotal_ars", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column("discount_total_ars", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column("total_ars", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("status IN ('draft', 'cancelled', 'confirmed', 'invoiced', 'reversed')", name="ck_sales_status"),
        sa.CheckConstraint("currency = 'ARS'", name="ck_sales_currency"),
        sa.CheckConstraint("subtotal_ars >= 0 AND discount_total_ars >= 0 AND total_ars >= 0", name="ck_sales_totals_non_negative"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cancelled_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("tenant_id", "owner_id", "patient_id", "status", "created_by_user_id", "cancelled_by_user_id"):
        op.create_index(op.f(f"ix_sales_{column}"), "sales", [column])
    op.create_index("ix_sales_tenant_sale_date", "sales", ["tenant_id", "sale_date"])
    op.create_index("ix_sales_tenant_status_sale_date", "sales", ["tenant_id", "status", "sale_date"])
    op.create_index("ix_sales_tenant_owner", "sales", ["tenant_id", "owner_id"])
    op.create_index("ix_sales_tenant_patient", "sales", ["tenant_id", "patient_id"])
    op.create_index("ix_sales_tenant_created_by", "sales", ["tenant_id", "created_by_user_id"])

    op.create_table(
        "sale_items",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=False),
        sa.Column("line_type", sa.String(length=20), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=True),
        sa.Column("service_id", sa.Uuid(), nullable=True),
        sa.Column("description_snapshot", sa.String(length=255), nullable=False),
        sa.Column("internal_code_snapshot", sa.String(length=32), nullable=True),
        sa.Column("unit_snapshot", sa.String(length=50), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_price_ars", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_percentage", sa.Numeric(5, 2), server_default="0", nullable=False),
        sa.Column("line_subtotal_ars", sa.Numeric(16, 2), nullable=False),
        sa.Column("line_discount_ars", sa.Numeric(16, 2), nullable=False),
        sa.Column("line_total_ars", sa.Numeric(16, 2), nullable=False),
        sa.Column("line_order", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("line_type IN ('product', 'service')", name="ck_sale_items_line_type"),
        sa.CheckConstraint("quantity > 0", name="ck_sale_items_quantity_positive"),
        sa.CheckConstraint("quantity = trunc(quantity)", name="ck_sale_items_quantity_integer"),
        sa.CheckConstraint("unit_price_ars >= 0", name="ck_sale_items_unit_price_non_negative"),
        sa.CheckConstraint("discount_percentage >= 0 AND discount_percentage <= 100", name="ck_sale_items_discount_range"),
        sa.CheckConstraint("line_subtotal_ars >= 0 AND line_discount_ars >= 0 AND line_total_ars >= 0", name="ck_sale_items_totals_non_negative"),
        sa.CheckConstraint("(line_type = 'product' AND inventory_item_id IS NOT NULL) OR (line_type = 'service' AND inventory_item_id IS NULL)", name="ck_sale_items_product_reference"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sale_id", "line_order", name="uq_sale_items_sale_line_order"),
    )
    for column in ("tenant_id", "sale_id", "line_type", "inventory_item_id"):
        op.create_index(op.f(f"ix_sale_items_{column}"), "sale_items", [column])
    op.create_index("ix_sale_items_tenant_inventory_item", "sale_items", ["tenant_id", "inventory_item_id"])
    op.create_index("ix_sale_items_tenant_line_type", "sale_items", ["tenant_id", "line_type"])


def downgrade() -> None:
    op.drop_table("sale_items")
    op.drop_table("sales")

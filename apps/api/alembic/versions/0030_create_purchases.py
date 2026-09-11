"""create purchases"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0030_create_purchases"
down_revision = "0029_inventory_bulk_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchases",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_name", sa.String(length=255), nullable=False),
        sa.Column("supplier_tax_id", sa.String(length=80), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("document_type", sa.String(length=30), nullable=False),
        sa.Column("document_number", sa.String(length=120), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default="ARS", nullable=False),
        sa.Column("subtotal_ars", sa.Numeric(precision=16, scale=2), server_default="0", nullable=False),
        sa.Column("tax_total_ars", sa.Numeric(precision=16, scale=2), server_default="0", nullable=False),
        sa.Column("total_ars", sa.Numeric(precision=16, scale=2), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'cancelled', 'received', 'partially_received', 'returned')", name="ck_purchases_status"),
        sa.CheckConstraint("currency = 'ARS'", name="ck_purchases_currency"),
        sa.CheckConstraint("subtotal_ars >= 0", name="ck_purchases_subtotal_non_negative"),
        sa.CheckConstraint("tax_total_ars >= 0", name="ck_purchases_tax_total_non_negative"),
        sa.CheckConstraint("total_ars >= 0", name="ck_purchases_total_non_negative"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["cancelled_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchases_tenant_purchase_date", "purchases", ["tenant_id", "purchase_date"])
    op.create_index("ix_purchases_tenant_status_purchase_date", "purchases", ["tenant_id", "status", "purchase_date"])
    op.create_index("ix_purchases_tenant_supplier", "purchases", ["tenant_id", "supplier_name"])
    op.create_index("ix_purchases_tenant_document", "purchases", ["tenant_id", "document_number"])
    op.create_index("ix_purchases_tenant_created_by", "purchases", ["tenant_id", "created_by_user_id"])
    op.create_index(op.f("ix_purchases_tenant_id"), "purchases", ["tenant_id"])
    op.create_index(op.f("ix_purchases_document_type"), "purchases", ["document_type"])
    op.create_index(op.f("ix_purchases_status"), "purchases", ["status"])
    op.create_index(op.f("ix_purchases_created_by_user_id"), "purchases", ["created_by_user_id"])
    op.create_index(op.f("ix_purchases_cancelled_by_user_id"), "purchases", ["cancelled_by_user_id"])

    op.create_table(
        "purchase_items",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("description_snapshot", sa.String(length=255), nullable=False),
        sa.Column("internal_code_snapshot", sa.String(length=16), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("unit_price_without_tax_ars", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("tax_rate_percentage", sa.Numeric(precision=5, scale=2), server_default="21", nullable=False),
        sa.Column("unit_price_with_tax_ars", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("line_subtotal_ars", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("line_tax_ars", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("line_total_ars", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("line_number > 0", name="ck_purchase_items_line_number_positive"),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_items_quantity_positive"),
        sa.CheckConstraint("unit_price_without_tax_ars >= 0", name="ck_purchase_items_unit_price_non_negative"),
        sa.CheckConstraint("tax_rate_percentage >= 0 AND tax_rate_percentage <= 100", name="ck_purchase_items_tax_rate_range"),
        sa.CheckConstraint("unit_price_with_tax_ars >= 0 AND line_subtotal_ars >= 0 AND line_tax_ars >= 0 AND line_total_ars >= 0", name="ck_purchase_items_calculated_amounts_non_negative"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("purchase_id", "line_number", name="uq_purchase_items_purchase_line_number"),
        sa.UniqueConstraint("purchase_id", "inventory_item_id", name="uq_purchase_items_purchase_inventory_item"),
    )
    op.create_index(op.f("ix_purchase_items_tenant_id"), "purchase_items", ["tenant_id"])
    op.create_index(op.f("ix_purchase_items_purchase_id"), "purchase_items", ["purchase_id"])
    op.create_index(op.f("ix_purchase_items_inventory_item_id"), "purchase_items", ["inventory_item_id"])
    op.create_index("ix_purchase_items_tenant_inventory_item", "purchase_items", ["tenant_id", "inventory_item_id"])


def downgrade() -> None:
    op.drop_index("ix_purchase_items_tenant_inventory_item", table_name="purchase_items")
    op.drop_index(op.f("ix_purchase_items_inventory_item_id"), table_name="purchase_items")
    op.drop_index(op.f("ix_purchase_items_purchase_id"), table_name="purchase_items")
    op.drop_index(op.f("ix_purchase_items_tenant_id"), table_name="purchase_items")
    op.drop_table("purchase_items")

    op.drop_index(op.f("ix_purchases_cancelled_by_user_id"), table_name="purchases")
    op.drop_index(op.f("ix_purchases_created_by_user_id"), table_name="purchases")
    op.drop_index(op.f("ix_purchases_status"), table_name="purchases")
    op.drop_index(op.f("ix_purchases_document_type"), table_name="purchases")
    op.drop_index(op.f("ix_purchases_tenant_id"), table_name="purchases")
    op.drop_index("ix_purchases_tenant_created_by", table_name="purchases")
    op.drop_index("ix_purchases_tenant_document", table_name="purchases")
    op.drop_index("ix_purchases_tenant_supplier", table_name="purchases")
    op.drop_index("ix_purchases_tenant_status_purchase_date", table_name="purchases")
    op.drop_index("ix_purchases_tenant_purchase_date", table_name="purchases")
    op.drop_table("purchases")

"""add tenant-scoped purchase returns"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0035_purchase_returns"
down_revision = "0034_purchase_attachments"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "purchase_returns",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_name", sa.String(length=255), nullable=False),
        sa.Column("supplier_tax_id", sa.String(length=80), nullable=True),
        sa.Column("return_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("document_type", sa.String(length=30), nullable=True),
        sa.Column("document_number", sa.String(length=120), nullable=True),
        sa.Column(
            "currency", sa.String(length=3), server_default="ARS", nullable=False
        ),
        sa.Column(
            "subtotal_ars", sa.Numeric(precision=16, scale=2), server_default="0", nullable=False
        ),
        sa.Column(
            "tax_total_ars", sa.Numeric(precision=16, scale=2), server_default="0", nullable=False
        ),
        sa.Column(
            "total_ars", sa.Numeric(precision=16, scale=2), server_default="0", nullable=False
        ),
        sa.Column("inventory_operation_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('draft', 'confirmed', 'cancelled')",
            name="ck_purchase_returns_status",
        ),
        sa.CheckConstraint(
            "document_type IS NULL OR document_type IN "
            "('credit_note', 'return_delivery_note', 'other')",
            name="ck_purchase_returns_document_type",
        ),
        sa.CheckConstraint("currency = 'ARS'", name="ck_purchase_returns_currency"),
        sa.CheckConstraint(
            "subtotal_ars >= 0 AND tax_total_ars >= 0 AND total_ars >= 0",
            name="ck_purchase_returns_totals_non_negative",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["confirmed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["cancelled_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "tenant_id",
        "purchase_id",
        "supplier_id",
        "status",
        "inventory_operation_id",
        "created_by_user_id",
        "confirmed_by_user_id",
        "cancelled_by_user_id",
    ):
        op.create_index(
            op.f(f"ix_purchase_returns_{column}"), "purchase_returns", [column]
        )
    op.create_index(
        "ix_purchase_returns_tenant_return_date",
        "purchase_returns",
        ["tenant_id", "return_date"],
    )
    op.create_index(
        "ix_purchase_returns_tenant_status_return_date",
        "purchase_returns",
        ["tenant_id", "status", "return_date"],
    )
    op.create_index(
        "ix_purchase_returns_tenant_purchase",
        "purchase_returns",
        ["tenant_id", "purchase_id"],
    )
    op.create_index(
        "ix_purchase_returns_tenant_supplier",
        "purchase_returns",
        ["tenant_id", "supplier_id"],
    )
    op.create_index(
        "ix_purchase_returns_tenant_created_by",
        "purchase_returns",
        ["tenant_id", "created_by_user_id"],
    )
    op.create_index(
        "ix_purchase_returns_tenant_inventory_operation",
        "purchase_returns",
        ["tenant_id", "inventory_operation_id"],
    )

    op.create_table(
        "purchase_return_items",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_return_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_item_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("description_snapshot", sa.String(length=255), nullable=False),
        sa.Column("internal_code_snapshot", sa.String(length=16), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "unit_price_without_tax_ars", sa.Numeric(precision=14, scale=2), nullable=False
        ),
        sa.Column("tax_rate_percentage", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("line_subtotal_ars", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("line_tax_ars", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("line_total_ars", sa.Numeric(precision=16, scale=2), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "line_number > 0", name="ck_purchase_return_items_line_number_positive"
        ),
        sa.CheckConstraint(
            "quantity > 0", name="ck_purchase_return_items_quantity_positive"
        ),
        sa.CheckConstraint(
            "quantity = trunc(quantity)",
            name="ck_purchase_return_items_quantity_integer",
        ),
        sa.CheckConstraint(
            "unit_price_without_tax_ars >= 0",
            name="ck_purchase_return_items_unit_price_non_negative",
        ),
        sa.CheckConstraint(
            "tax_rate_percentage >= 0 AND tax_rate_percentage <= 100",
            name="ck_purchase_return_items_tax_rate_range",
        ),
        sa.CheckConstraint(
            "line_subtotal_ars >= 0 AND line_tax_ars >= 0 AND line_total_ars >= 0",
            name="ck_purchase_return_items_totals_non_negative",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["purchase_return_id"], ["purchase_returns.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["purchase_item_id"], ["purchase_items.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "purchase_return_id",
            "purchase_item_id",
            name="uq_purchase_return_items_return_purchase_item",
        ),
        sa.UniqueConstraint(
            "purchase_return_id",
            "line_number",
            name="uq_purchase_return_items_return_line_number",
        ),
    )
    for column in (
        "tenant_id",
        "purchase_return_id",
        "purchase_item_id",
        "inventory_item_id",
    ):
        op.create_index(
            op.f(f"ix_purchase_return_items_{column}"),
            "purchase_return_items",
            [column],
        )
    op.create_index(
        "ix_purchase_return_items_tenant_return",
        "purchase_return_items",
        ["tenant_id", "purchase_return_id"],
    )
    op.create_index(
        "ix_purchase_return_items_tenant_purchase_item",
        "purchase_return_items",
        ["tenant_id", "purchase_item_id"],
    )
    op.create_index(
        "ix_purchase_return_items_tenant_inventory_item",
        "purchase_return_items",
        ["tenant_id", "inventory_item_id"],
    )

    op.create_table(
        "purchase_return_attachments",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_return_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("bucket_name", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "size_bytes > 0", name="ck_purchase_return_attachments_size_positive"
        ),
        sa.CheckConstraint(
            "length(sha256) = 64",
            name="ck_purchase_return_attachments_sha256_length",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["purchase_return_id"], ["purchase_returns.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["replaced_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "tenant_id",
        "purchase_return_id",
    ):
        op.create_index(
            op.f(f"ix_purchase_return_attachments_{column}"),
            "purchase_return_attachments",
            [column],
        )
    op.create_index(
        "ix_purchase_return_attachments_tenant_return",
        "purchase_return_attachments",
        ["tenant_id", "purchase_return_id"],
    )
    op.create_index(
        "ix_purchase_return_attachments_tenant_sha256",
        "purchase_return_attachments",
        ["tenant_id", "sha256"],
    )
    op.create_index(
        "uq_purchase_return_attachments_active_return",
        "purchase_return_attachments",
        ["purchase_return_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_table("purchase_return_attachments")
    op.drop_table("purchase_return_items")
    op.drop_table("purchase_returns")

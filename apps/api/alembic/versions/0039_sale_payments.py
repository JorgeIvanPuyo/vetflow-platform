"""add payment methods and sale payments"""

import sqlalchemy as sa
from alembic import op


revision = "0039_sale_payments"
down_revision = "0038_sale_fiscal_documents"
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
        "payment_methods",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("normalized_label", sa.String(length=120), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("type IN ('cash', 'bank_transfer', 'debit_card', 'credit_card', 'digital_wallet', 'other')", name="ck_payment_methods_type"),
        sa.CheckConstraint("sort_order >= 0", name="ck_payment_methods_sort_order"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payment_methods_tenant_id"), "payment_methods", ["tenant_id"])
    op.create_index("ix_payment_methods_tenant_active_order", "payment_methods", ["tenant_id", "is_active", "sort_order"])
    op.create_index("ix_payment_methods_tenant_type", "payment_methods", ["tenant_id", "type"])
    op.create_index("uq_payment_methods_active_label", "payment_methods", ["tenant_id", "normalized_label"], unique=True, postgresql_where=sa.text("is_active"))

    op.create_table(
        "sale_payments",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=False),
        sa.Column("payment_method_id", sa.Uuid(), nullable=False),
        sa.Column("payment_method_label_snapshot", sa.String(length=120), nullable=False),
        sa.Column("payment_method_type_snapshot", sa.String(length=30), nullable=False),
        sa.Column("amount_ars", sa.Numeric(16, 2), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("amount_ars > 0", name="ck_sale_payments_amount_positive"),
        sa.CheckConstraint("payment_method_type_snapshot IN ('cash', 'bank_transfer', 'debit_card', 'credit_card', 'digital_wallet', 'other')", name="ck_sale_payments_method_type"),
        sa.CheckConstraint("(is_active AND voided_at IS NULL AND voided_by_user_id IS NULL AND void_reason IS NULL) OR (NOT is_active AND voided_at IS NOT NULL AND void_reason IS NOT NULL)", name="ck_sale_payments_void_state"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payment_method_id"], ["payment_methods.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["voided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("tenant_id", "sale_id", "payment_method_id"):
        op.create_index(op.f(f"ix_sale_payments_{column}"), "sale_payments", [column])
    op.create_index("ix_sale_payments_tenant_sale", "sale_payments", ["tenant_id", "sale_id"])
    op.create_index("ix_sale_payments_tenant_method", "sale_payments", ["tenant_id", "payment_method_id"])
    op.create_index("ix_sale_payments_tenant_received", "sale_payments", ["tenant_id", "received_at"])
    op.create_index("ix_sale_payments_tenant_creator", "sale_payments", ["tenant_id", "created_by_user_id"])
    op.create_index("ix_sale_payments_tenant_sale_active", "sale_payments", ["tenant_id", "sale_id"], postgresql_where=sa.text("is_active"))


def downgrade() -> None:
    op.drop_table("sale_payments")
    op.drop_table("payment_methods")

"""Persistent atomic split-payment confirmation identity and membership."""

from alembic import op
import sqlalchemy as sa


revision = "0053_sale_payment_batches"
down_revision = "0052_sale_payment_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_sales_tenant_id_id", "sales", ["tenant_id", "id"])
    op.create_table(
        "sale_payment_batches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_sale_payment_batches_tenant_key"),
        sa.UniqueConstraint("tenant_id", "sale_id", "id", name="uq_sale_payment_batches_membership"),
        sa.ForeignKeyConstraint(["tenant_id", "sale_id"], ["sales.tenant_id", "sales.id"],
                                name="fk_sale_payment_batches_tenant_sale", ondelete="RESTRICT"),
        sa.CheckConstraint("length(idempotency_key) BETWEEN 1 AND 128", name="ck_sale_payment_batches_key"),
        sa.CheckConstraint("length(request_hash) = 64", name="ck_sale_payment_batches_hash"),
    )
    op.create_index("ix_sale_payment_batches_tenant_id", "sale_payment_batches", ["tenant_id"])
    op.create_index("ix_sale_payment_batches_tenant_sale", "sale_payment_batches", ["tenant_id", "sale_id"])
    op.add_column("sale_payments", sa.Column("batch_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_sale_payments_batch_membership", "sale_payments", "sale_payment_batches",
        ["tenant_id", "sale_id", "batch_id"], ["tenant_id", "sale_id", "id"], ondelete="RESTRICT",
    )
    op.create_index("ix_sale_payments_tenant_batch", "sale_payments", ["tenant_id", "batch_id"])


def downgrade() -> None:
    op.drop_index("ix_sale_payments_tenant_batch", table_name="sale_payments")
    op.drop_constraint("fk_sale_payments_batch_membership", "sale_payments", type_="foreignkey")
    op.drop_column("sale_payments", "batch_id")
    op.drop_table("sale_payment_batches")
    op.drop_constraint("uq_sales_tenant_id_id", "sales", type_="unique")

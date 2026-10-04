"""Persist tenant-scoped idempotency for individual sale payments."""

from alembic import op
import sqlalchemy as sa


revision = "0052_sale_payment_idempotency"
down_revision = "0051_secretary_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sale_payments", sa.Column("idempotency_key", sa.String(128), nullable=True))
    op.add_column("sale_payments", sa.Column("idempotency_request_hash", sa.String(64), nullable=True))
    op.create_check_constraint(
        "ck_sale_payments_idempotency_pair", "sale_payments",
        "(idempotency_key IS NULL AND idempotency_request_hash IS NULL) OR "
        "(idempotency_key IS NOT NULL AND length(idempotency_key) > 0 AND "
        "idempotency_request_hash IS NOT NULL AND length(idempotency_request_hash) = 64)",
    )
    op.create_index(
        "uq_sale_payments_tenant_idempotency_key", "sale_payments",
        ["tenant_id", "idempotency_key"], unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_sale_payments_tenant_idempotency_key", table_name="sale_payments")
    op.drop_constraint("ck_sale_payments_idempotency_pair", "sale_payments", type_="check")
    op.drop_column("sale_payments", "idempotency_request_hash")
    op.drop_column("sale_payments", "idempotency_key")

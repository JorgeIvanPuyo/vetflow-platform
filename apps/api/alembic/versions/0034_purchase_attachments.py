"""add private purchase attachment history"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0034_purchase_attachments"
down_revision = "0033_purchase_quantity_integer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_attachments",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint(
            "size_bytes > 0", name="ck_purchase_attachments_size_positive"
        ),
        sa.CheckConstraint(
            "length(sha256) = 64", name="ck_purchase_attachments_sha256_length"
        ),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["replaced_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_purchase_attachments_purchase_id",
        "purchase_attachments",
        ["purchase_id"],
    )
    op.create_index(
        "ix_purchase_attachments_tenant_purchase",
        "purchase_attachments",
        ["tenant_id", "purchase_id"],
    )
    op.create_index(
        "ix_purchase_attachments_tenant_sha256",
        "purchase_attachments",
        ["tenant_id", "sha256"],
    )
    op.create_index(
        "uq_purchase_attachments_active_purchase",
        "purchase_attachments",
        ["purchase_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_purchase_attachments_active_purchase",
        table_name="purchase_attachments",
        postgresql_where=sa.text("is_active"),
    )
    op.drop_index(
        "ix_purchase_attachments_tenant_sha256", table_name="purchase_attachments"
    )
    op.drop_index(
        "ix_purchase_attachments_tenant_purchase", table_name="purchase_attachments"
    )
    op.drop_index(
        "ix_purchase_attachments_purchase_id", table_name="purchase_attachments"
    )
    op.drop_table("purchase_attachments")

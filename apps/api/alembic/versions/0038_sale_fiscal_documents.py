"""add fiscal issuers and sale fiscal documents"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0038_sale_fiscal_documents"
down_revision = "0037_sale_confirmation"
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
        "fiscal_issuers",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("tax_id", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "can_issue_service_receipt_c",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "can_issue_product_invoice_c",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("service_document_type", sa.String(length=30), nullable=True),
        sa.Column("service_document_code", sa.String(length=20), nullable=True),
        sa.Column("product_document_type", sa.String(length=30), nullable=True),
        sa.Column("product_document_code", sa.String(length=20), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "service_document_type IS NULL OR "
            "service_document_type IN ('receipt_c', 'invoice_c')",
            name="ck_fiscal_issuers_service_document_type",
        ),
        sa.CheckConstraint(
            "product_document_type IS NULL OR "
            "product_document_type IN ('receipt_c', 'invoice_c')",
            name="ck_fiscal_issuers_product_document_type",
        ),
        sa.CheckConstraint(
            "(can_issue_service_receipt_c AND service_document_type IS NOT NULL "
            "AND service_document_code IS NOT NULL) OR "
            "(NOT can_issue_service_receipt_c AND service_document_type IS NULL "
            "AND service_document_code IS NULL)",
            name="ck_fiscal_issuers_service_configuration",
        ),
        sa.CheckConstraint(
            "(can_issue_product_invoice_c AND product_document_type IS NOT NULL "
            "AND product_document_code IS NOT NULL) OR "
            "(NOT can_issue_product_invoice_c AND product_document_type IS NULL "
            "AND product_document_code IS NULL)",
            name="ck_fiscal_issuers_product_configuration",
        ),
        sa.CheckConstraint(
            "can_issue_service_receipt_c OR can_issue_product_invoice_c",
            name="ck_fiscal_issuers_has_capability",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "user_id", name="uq_fiscal_issuers_tenant_user"
        ),
    )
    op.create_index(op.f("ix_fiscal_issuers_tenant_id"), "fiscal_issuers", ["tenant_id"])
    op.create_index(
        "ix_fiscal_issuers_tenant_active", "fiscal_issuers", ["tenant_id", "is_active"]
    )

    op.create_table(
        "sale_fiscal_documents",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=False),
        sa.Column("fiscal_issuer_id", sa.Uuid(), nullable=False),
        sa.Column("issuer_user_id_snapshot", sa.Uuid(), nullable=False),
        sa.Column("issuer_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("issuer_tax_id_snapshot", sa.String(length=80), nullable=False),
        sa.Column("document_type", sa.String(length=30), nullable=False),
        sa.Column("document_code", sa.String(length=20), nullable=False),
        sa.Column("document_number", sa.String(length=120), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("total_ars_snapshot", sa.Numeric(16, 2), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("bucket_name", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "document_type IN ('receipt_c', 'invoice_c')",
            name="ck_sale_fiscal_documents_type",
        ),
        sa.CheckConstraint(
            "total_ars_snapshot >= 0", name="ck_sale_fiscal_documents_total"
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_sale_fiscal_documents_size"),
        sa.CheckConstraint(
            "length(sha256) = 64", name="ck_sale_fiscal_documents_sha256"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["fiscal_issuer_id"], ["fiscal_issuers.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "fiscal_issuer_id",
            "document_type",
            "document_number",
            name="uq_sale_fiscal_documents_number",
        ),
    )
    for column in ("tenant_id", "sale_id", "fiscal_issuer_id"):
        op.create_index(
            op.f(f"ix_sale_fiscal_documents_{column}"),
            "sale_fiscal_documents",
            [column],
        )
    op.create_index(
        "uq_sale_fiscal_documents_active_sale",
        "sale_fiscal_documents",
        ["sale_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "ix_sale_fiscal_documents_tenant_sale",
        "sale_fiscal_documents",
        ["tenant_id", "sale_id"],
    )
    op.create_index(
        "ix_sale_fiscal_documents_tenant_issuer",
        "sale_fiscal_documents",
        ["tenant_id", "fiscal_issuer_id"],
    )

    op.create_table(
        "sale_fiscal_document_file_versions",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("fiscal_document_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("bucket_name", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("replaced_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "size_bytes > 0", name="ck_sale_fiscal_document_versions_size"
        ),
        sa.CheckConstraint(
            "length(sha256) = 64", name="ck_sale_fiscal_document_versions_sha256"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["fiscal_document_id"],
            ["sale_fiscal_documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_sale_fiscal_document_file_versions_tenant_id"),
        "sale_fiscal_document_file_versions",
        ["tenant_id"],
    )
    op.create_index(
        op.f("ix_sale_fiscal_document_file_versions_fiscal_document_id"),
        "sale_fiscal_document_file_versions",
        ["fiscal_document_id"],
    )
    op.create_index(
        "ix_sale_fiscal_document_versions_tenant_document",
        "sale_fiscal_document_file_versions",
        ["tenant_id", "fiscal_document_id"],
    )


def downgrade() -> None:
    op.drop_table("sale_fiscal_document_file_versions")
    op.drop_table("sale_fiscal_documents")
    op.drop_table("fiscal_issuers")

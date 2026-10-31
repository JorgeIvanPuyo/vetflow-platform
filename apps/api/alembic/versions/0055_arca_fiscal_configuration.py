"""ARCA.1 opt-in fiscal policy, Argentine issuer identity and fiscal series.

All new identity fields remain NULL for historical rows. No customer data or
fiscal habilitation is inferred. This migration only adds configuration.
"""

import sqlalchemy as sa
from alembic import op


revision = "0055_arca_fiscal_configuration"
down_revision = "0054_receivables_foundation"
branch_labels = None
depends_on = None


def _base_columns():
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.add_column("fiscal_issuers", sa.Column("cuit", sa.String(11), nullable=True))
    op.add_column("fiscal_issuers", sa.Column("legal_name", sa.String(255), nullable=True))
    op.add_column("fiscal_issuers", sa.Column("tax_condition", sa.String(120), nullable=True))
    op.add_column("payment_methods", sa.Column("operational_reference", sa.String(255), nullable=True))
    op.add_column("payment_methods", sa.Column("suggested_fiscal_issuer_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_payment_methods_suggested_fiscal_issuer", "payment_methods", "fiscal_issuers", ["suggested_fiscal_issuer_id"], ["id"], ondelete="RESTRICT")
    op.create_table(
        "fiscal_policies",
        *_base_columns(),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("payment_scope", sa.String(30), server_default="electronic_only", nullable=False),
        sa.Column("accounting_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accounting_reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("accounting_review_note", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["accounting_reviewed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("tenant_id", name="uq_fiscal_policies_tenant"),
        sa.CheckConstraint("payment_scope IN ('electronic_only', 'all_payments')", name="ck_fiscal_policies_scope"),
        sa.CheckConstraint("revision > 0", name="ck_fiscal_policies_revision"),
        sa.CheckConstraint("(accounting_reviewed_at IS NULL AND accounting_reviewed_by_user_id IS NULL AND accounting_review_note IS NULL) OR (accounting_reviewed_at IS NOT NULL AND accounting_reviewed_by_user_id IS NOT NULL AND accounting_review_note IS NOT NULL)", name="ck_fiscal_policies_accounting_review"),
    )
    op.create_index("ix_fiscal_policies_tenant_id", "fiscal_policies", ["tenant_id"])
    op.create_table(
        "fiscal_series",
        *_base_columns(),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("fiscal_issuer_id", sa.Uuid(), nullable=False),
        sa.Column("cuit_snapshot", sa.String(11), nullable=True),
        sa.Column("environment", sa.String(20), server_default="homologation", nullable=False),
        sa.Column("point_of_sale", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(30), nullable=False),
        sa.Column("concept", sa.Integer(), nullable=False),
        sa.Column("authorization_mode", sa.String(4), server_default="CAE", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("credential_reference", sa.String(220), nullable=True),
        sa.Column("caea_reference", sa.String(220), nullable=True),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["fiscal_issuer_id"], ["fiscal_issuers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_fiscal_series_tenant_id"),
        sa.UniqueConstraint("tenant_id", "cuit_snapshot", "environment", "point_of_sale", "document_type", name="uq_fiscal_series_identity"),
        sa.UniqueConstraint("tenant_id", "fiscal_issuer_id", "environment", "point_of_sale", "document_type", name="uq_fiscal_series_issuer_identity"),
        sa.CheckConstraint("environment IN ('homologation', 'production')", name="ck_fiscal_series_environment"),
        sa.CheckConstraint("point_of_sale BETWEEN 1 AND 99999", name="ck_fiscal_series_point_of_sale"),
        sa.CheckConstraint("document_type IN ('receipt_c', 'invoice_c')", name="ck_fiscal_series_document_type"),
        sa.CheckConstraint("concept IN (1, 2, 3)", name="ck_fiscal_series_concept"),
        sa.CheckConstraint("authorization_mode IN ('CAE', 'CAEA')", name="ck_fiscal_series_authorization_mode"),
        sa.CheckConstraint("revision > 0", name="ck_fiscal_series_revision"),
    )
    op.create_index("ix_fiscal_series_tenant_id", "fiscal_series", ["tenant_id"])
    op.create_index("ix_fiscal_series_tenant_issuer", "fiscal_series", ["tenant_id", "fiscal_issuer_id"])
    op.create_table(
        "fiscal_policy_reviews",
        *_base_columns(),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("payment_scope", sa.String(30), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["policy_id"], ["fiscal_policies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_fiscal_policy_reviews_tenant_id", "fiscal_policy_reviews", ["tenant_id"])
    op.create_index("ix_fiscal_policy_reviews_tenant_policy", "fiscal_policy_reviews", ["tenant_id", "policy_id"])


def downgrade() -> None:
    # Reviewed as code only; never run against the preserved local copy.
    op.drop_table("fiscal_policy_reviews")
    op.drop_table("fiscal_series")
    op.drop_table("fiscal_policies")
    op.drop_constraint("fk_payment_methods_suggested_fiscal_issuer", "payment_methods", type_="foreignkey")
    op.drop_column("payment_methods", "suggested_fiscal_issuer_id")
    op.drop_column("payment_methods", "operational_reference")
    op.drop_column("fiscal_issuers", "tax_condition")
    op.drop_column("fiscal_issuers", "legal_name")
    op.drop_column("fiscal_issuers", "cuit")

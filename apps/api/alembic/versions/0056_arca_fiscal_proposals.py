"""Persistent fiscal review and whole-payment reservations; preserve manual history.

No provider calls or data backfills. Historical documents retain their manual
identity, attachments and totals. Existing primary keys make the added payment
membership uniqueness collision-free. Only the manual active-sale uniqueness
is retained; future ARCA documents use the explicit plural contract.
"""
import sqlalchemy as sa
from alembic import op


revision = "0056_arca_fiscal_proposals"
down_revision = "0055_arca_fiscal_configuration"
branch_labels = None
depends_on = None


def _base():
    return [sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade():
    op.add_column("sale_fiscal_documents", sa.Column("source", sa.String(20), server_default="manual", nullable=False))
    op.add_column("sale_fiscal_documents", sa.Column("authorization_status", sa.String(20), server_default="manual", nullable=False))
    op.add_column("sale_fiscal_documents", sa.Column("allocation_idempotency_key", sa.String(128), nullable=True))
    op.add_column("sale_fiscal_documents", sa.Column("allocation_request_hash", sa.String(64), nullable=True))
    op.add_column("sale_fiscal_documents", sa.Column("allocation_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sale_fiscal_documents", sa.Column("allocation_reviewed_by_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_sale_fiscal_documents_allocation_actor", "sale_fiscal_documents", "users", ["allocation_reviewed_by_user_id"], ["id"], ondelete="RESTRICT")
    op.create_unique_constraint("uq_sale_fiscal_documents_membership", "sale_fiscal_documents", ["tenant_id", "sale_id", "id"])
    op.create_unique_constraint("uq_sale_fiscal_documents_allocation_key", "sale_fiscal_documents", ["tenant_id", "allocation_idempotency_key"])
    for name in ("original_filename", "bucket_name", "storage_key", "content_type", "size_bytes", "sha256", "uploaded_at"):
        op.alter_column("sale_fiscal_documents", name, nullable=True)
    op.drop_index("uq_sale_fiscal_documents_active_sale", table_name="sale_fiscal_documents")
    op.create_index("uq_sale_fiscal_documents_active_manual_sale", "sale_fiscal_documents", ["tenant_id", "sale_id"], unique=True, postgresql_where=sa.text("is_active AND source = 'manual'"), sqlite_where=sa.text("is_active = 1 AND source = 'manual'"))
    for name, condition in {
        "ck_sale_fiscal_documents_source": "source IN ('manual','arca')",
        "ck_sale_fiscal_documents_authorization_status": "authorization_status IN ('manual','pending','unknown','authorized','rejected','caea_pending')",
        "ck_sale_fiscal_documents_source_authorization": "(source = 'manual' AND authorization_status = 'manual') OR (source = 'arca' AND authorization_status <> 'manual')",
        "ck_sale_fiscal_documents_manual_attachment": "source <> 'manual' OR (original_filename IS NOT NULL AND bucket_name IS NOT NULL AND storage_key IS NOT NULL AND content_type IS NOT NULL AND size_bytes IS NOT NULL AND sha256 IS NOT NULL AND uploaded_at IS NOT NULL)",
        "ck_sale_fiscal_documents_authorized_active": "authorization_status <> 'authorized' OR is_active",
    }.items():
        op.create_check_constraint(name, "sale_fiscal_documents", condition)
    op.create_unique_constraint("uq_sale_payments_fiscal_membership", "sale_payments", ["tenant_id", "sale_id", "id"])
    op.create_table(
        "fiscal_proposals", *_base(),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=False),
        sa.Column("fiscal_issuer_id", sa.Uuid(), nullable=False),
        sa.Column("fiscal_series_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("payment_ids", sa.JSON(), nullable=False),
        sa.Column("fiscal_description", sa.Text(), nullable=False),
        sa.Column("total_ars", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("concept", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("source_snapshot_hash", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("approval_request_hash", sa.String(64), nullable=True),
        sa.Column("cancelled_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("audit_log", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["fiscal_issuer_id"], ["fiscal_issuers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "sale_id"], ["sales.tenant_id", "sales.id"], name="fk_fiscal_proposals_tenant_sale", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "fiscal_series_id"], ["fiscal_series.tenant_id", "fiscal_series.id"], name="fk_fiscal_proposals_tenant_series", ondelete="RESTRICT"),
        *(sa.ForeignKeyConstraint([name], ["users.id"], ondelete="RESTRICT") for name in ("created_by_user_id", "updated_by_user_id", "approved_by_user_id", "cancelled_by_user_id")),
        sa.UniqueConstraint("tenant_id", "id", name="uq_fiscal_proposals_tenant_id"),
        sa.UniqueConstraint("tenant_id", "sale_id", "id", name="uq_fiscal_proposals_membership"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_fiscal_proposals_approval_key"),
        sa.CheckConstraint("status IN ('draft','approved','cancelled','sent','unknown','authorized','rejected','caea_pending')", name="ck_fiscal_proposals_status"),
        sa.CheckConstraint("currency = 'ARS' AND total_ars > 0", name="ck_fiscal_proposals_money"),
        sa.CheckConstraint("concept IN (1,2,3)", name="ck_fiscal_proposals_concept"),
        sa.CheckConstraint("length(content_hash) = 64 AND length(source_snapshot_hash) = 64", name="ck_fiscal_proposals_hashes"),
        sa.CheckConstraint("(status = 'draft' AND approved_at IS NULL) OR status = 'cancelled' OR (status NOT IN ('draft','cancelled') AND approved_at IS NOT NULL)", name="ck_fiscal_proposals_approval_state"),
        sa.CheckConstraint("status <> 'cancelled' OR (cancelled_at IS NOT NULL AND cancelled_by_user_id IS NOT NULL AND cancellation_reason IS NOT NULL)", name="ck_fiscal_proposals_cancellation_audit"),
        sa.CheckConstraint("(approved_at IS NULL AND approved_by_user_id IS NULL AND idempotency_key IS NULL AND approval_request_hash IS NULL) OR (approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL AND idempotency_key IS NOT NULL AND length(approval_request_hash) = 64)", name="ck_fiscal_proposals_approval_identity"),
    )
    op.create_index("ix_fiscal_proposals_tenant_id", "fiscal_proposals", ["tenant_id"])
    op.create_index("ix_fiscal_proposals_tenant_sale", "fiscal_proposals", ["tenant_id", "sale_id"])
    op.create_table(
        "fiscal_payment_allocations", *_base(),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=True),
        sa.Column("fiscal_document_id", sa.Uuid(), nullable=True),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("amount_ars", sa.Numeric(16, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("reserved_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "sale_id", "proposal_id"], ["fiscal_proposals.tenant_id", "fiscal_proposals.sale_id", "fiscal_proposals.id"], name="fk_fiscal_allocations_proposal", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "sale_id", "payment_id"], ["sale_payments.tenant_id", "sale_payments.sale_id", "sale_payments.id"], name="fk_fiscal_allocations_payment", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["fiscal_document_id"], ["sale_fiscal_documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "sale_id", "fiscal_document_id"], ["sale_fiscal_documents.tenant_id", "sale_fiscal_documents.sale_id", "sale_fiscal_documents.id"], name="fk_fiscal_allocations_document", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reserved_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["released_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("amount_ars > 0", name="ck_fiscal_allocations_positive"),
        sa.CheckConstraint("(proposal_id IS NOT NULL AND fiscal_document_id IS NULL) OR (proposal_id IS NULL AND fiscal_document_id IS NOT NULL)", name="ck_fiscal_allocations_owner"),
        sa.CheckConstraint("(is_active AND released_at IS NULL AND released_by_user_id IS NULL AND release_reason IS NULL) OR (NOT is_active AND released_at IS NOT NULL AND released_by_user_id IS NOT NULL AND release_reason IS NOT NULL)", name="ck_fiscal_allocations_release"),
    )
    op.create_index("ix_fiscal_payment_allocations_tenant_id", "fiscal_payment_allocations", ["tenant_id"])
    op.create_index("ix_fiscal_allocations_tenant_sale", "fiscal_payment_allocations", ["tenant_id", "sale_id"])
    op.create_index("ix_fiscal_allocations_tenant_proposal", "fiscal_payment_allocations", ["tenant_id", "proposal_id"])
    op.create_index("uq_fiscal_allocations_active_payment", "fiscal_payment_allocations", ["tenant_id", "payment_id"], unique=True, postgresql_where=sa.text("is_active"), sqlite_where=sa.text("is_active = 1"))


def downgrade():
    # Reviewed only. Never execute on the preserved local copy. Refuse lossy rollback.
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM fiscal_proposals) OR EXISTS (SELECT 1 FROM fiscal_payment_allocations) OR EXISTS (SELECT 1 FROM sale_fiscal_documents WHERE source <> 'manual' OR allocation_reviewed_at IS NOT NULL OR allocation_idempotency_key IS NOT NULL)")):
        raise RuntimeError("Cannot remove fiscal review while proposals, allocations or ARCA documents exist")
    op.drop_table("fiscal_payment_allocations")
    op.drop_table("fiscal_proposals")
    op.drop_constraint("uq_sale_payments_fiscal_membership", "sale_payments", type_="unique")
    op.drop_constraint("uq_sale_fiscal_documents_allocation_key", "sale_fiscal_documents", type_="unique")
    op.drop_constraint("uq_sale_fiscal_documents_membership", "sale_fiscal_documents", type_="unique")
    op.drop_constraint("fk_sale_fiscal_documents_allocation_actor", "sale_fiscal_documents", type_="foreignkey")
    for name in ("allocation_idempotency_key", "allocation_request_hash", "allocation_reviewed_at", "allocation_reviewed_by_user_id"):
        op.drop_column("sale_fiscal_documents", name)
    op.drop_index("uq_sale_fiscal_documents_active_manual_sale", table_name="sale_fiscal_documents")
    for name in ("ck_sale_fiscal_documents_authorized_active", "ck_sale_fiscal_documents_manual_attachment", "ck_sale_fiscal_documents_source_authorization", "ck_sale_fiscal_documents_authorization_status", "ck_sale_fiscal_documents_source"):
        op.drop_constraint(name, "sale_fiscal_documents", type_="check")
    for name in ("original_filename", "bucket_name", "storage_key", "content_type", "size_bytes", "sha256", "uploaded_at"):
        op.alter_column("sale_fiscal_documents", name, nullable=False)
    op.create_index("uq_sale_fiscal_documents_active_sale", "sale_fiscal_documents", ["sale_id"], unique=True, postgresql_where=sa.text("is_active"), sqlite_where=sa.text("is_active = 1"))
    op.drop_column("sale_fiscal_documents", "authorization_status")
    op.drop_column("sale_fiscal_documents", "source")

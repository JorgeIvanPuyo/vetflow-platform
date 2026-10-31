"""Recoverable homologation emission intents, exclusive series and file history.

No existing fiscal document is relabelled or backfilled. Authorization metadata
is additive; manual identities and attachments retain their original meaning.
"""
import sqlalchemy as sa
from alembic import op


revision = "0058_arca_emission"
down_revision = "0057_arca_auth"
branch_labels = None
depends_on = None


def _base():
    return [sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade():
    # Nullable additive metadata preserves every manual/historical row exactly.
    op.add_column("sale_fiscal_documents", sa.Column("environment", sa.String(20), nullable=True))
    op.add_column("sale_fiscal_documents", sa.Column("cae", sa.String(14), nullable=True))
    op.add_column("sale_fiscal_documents", sa.Column("cae_expiry", sa.Date(), nullable=True))
    op.add_column("sale_fiscal_documents", sa.Column("authorization_snapshot", sa.JSON(none_as_null=True), nullable=True))
    op.add_column("sale_fiscal_documents", sa.Column("emission_intent_id", sa.Uuid(), nullable=True))
    # Historical numbering remains unique with exactly its previous meaning;
    # homologation documents have an explicitly separate numbering namespace.
    op.drop_constraint("uq_sale_fiscal_documents_number", "sale_fiscal_documents", type_="unique")
    op.create_index("uq_sale_fiscal_documents_manual_number", "sale_fiscal_documents", ["tenant_id", "fiscal_issuer_id", "document_type", "document_number"], unique=True, postgresql_where=sa.text("source = 'manual'"), sqlite_where=sa.text("source = 'manual'"))
    op.create_index("uq_sale_fiscal_documents_arca_number", "sale_fiscal_documents", ["tenant_id", "environment", "fiscal_issuer_id", "document_type", "document_number"], unique=True, postgresql_where=sa.text("source = 'arca'"), sqlite_where=sa.text("source = 'arca'"))
    op.create_table(
        "arca_series_ownership", *_base(),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("series_key", sa.String(64), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("cuit", sa.String(11), nullable=False),
        sa.Column("point_of_sale", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.Integer(), nullable=False),
        sa.Column("active_intent_id", sa.Uuid(), nullable=True),
        sa.Column("lease_owner", sa.String(64), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fence", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.UniqueConstraint("series_key", name="uq_arca_series_remote_identity"),
        sa.UniqueConstraint("environment", "cuit", "point_of_sale", "document_type", name="uq_arca_series_remote_coordinates"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_arca_series_owner_tenant"),
        sa.CheckConstraint("environment = 'homologation'", name="ck_arca_series_owner_environment"),
        sa.CheckConstraint("fence >= 0", name="ck_arca_series_owner_fence"),
        sa.CheckConstraint("point_of_sale BETWEEN 1 AND 99999 AND document_type IN (11,15) AND length(cuit) = 11 AND length(series_key) = 64", name="ck_arca_series_remote_coordinates"),
        sa.CheckConstraint("(lease_owner IS NULL AND lease_until IS NULL) OR (lease_owner IS NOT NULL AND lease_until IS NOT NULL)", name="ck_arca_series_lease_pair"),
    )
    op.create_index("ix_arca_series_ownership_tenant_id", "arca_series_ownership", ["tenant_id"])
    op.create_table(
        "arca_emission_intents", *_base(),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("fiscal_issuer_id", sa.Uuid(), nullable=False),
        sa.Column("fiscal_series_id", sa.Uuid(), nullable=False),
        sa.Column("series_owner_id", sa.Uuid(), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("state", sa.String(20), server_default="prepared", nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("intent_fingerprint", sa.String(64), nullable=False),
        sa.Column("approval_content_hash", sa.String(64), nullable=False),
        sa.Column("business_snapshot", sa.JSON(), nullable=False),
        sa.Column("credential_reference", sa.String(220), nullable=False),
        sa.Column("number", sa.Integer(), nullable=True),
        sa.Column("request_payload", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("request_hash", sa.String(64), nullable=True),
        sa.Column("claim_owner", sa.String(64), nullable=True),
        sa.Column("claim_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claim_fence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_diagnostic", sa.String(120), nullable=True),
        sa.Column("diagnostics", sa.JSON(), nullable=False),
        sa.Column("cae", sa.String(14), nullable=True),
        sa.Column("cae_expiry", sa.Date(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("file_status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["tenant_id", "sale_id", "proposal_id"], ["fiscal_proposals.tenant_id", "fiscal_proposals.sale_id", "fiscal_proposals.id"], name="fk_arca_emission_proposal", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "series_owner_id"], ["arca_series_ownership.tenant_id", "arca_series_ownership.id"], name="fk_arca_emission_series_owner", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["fiscal_issuer_id"], ["fiscal_issuers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["fiscal_series_id"], ["fiscal_series.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["arca_emission_intents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["sale_fiscal_documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_arca_emission_tenant_id"),
        sa.UniqueConstraint("tenant_id", "sale_id", "id", name="uq_arca_emission_membership"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_arca_emission_intent_key"),
        sa.CheckConstraint("state IN ('prepared','processing','unknown','conflict','rejected','authorized')", name="ck_arca_emission_state"),
        sa.CheckConstraint("environment = 'homologation'", name="ck_arca_emission_environment"),
        sa.CheckConstraint("file_status IN ('pending','ready','failed')", name="ck_arca_emission_file_state"),
        sa.CheckConstraint("(number IS NULL AND request_payload IS NULL AND request_hash IS NULL) OR (number IS NOT NULL AND number > 0 AND request_payload IS NOT NULL AND request_hash IS NOT NULL AND length(request_hash) = 64)", name="ck_arca_emission_persisted_request"),
        sa.CheckConstraint("state <> 'authorized' OR (cae IS NOT NULL AND length(cae) = 14 AND cae_expiry IS NOT NULL AND document_id IS NOT NULL AND number IS NOT NULL)", name="ck_arca_emission_authorization"),
        sa.CheckConstraint("length(intent_fingerprint) = 64 AND length(approval_content_hash) = 64 AND length(idempotency_key) BETWEEN 1 AND 128 AND claim_fence >= 0", name="ck_arca_emission_identity"),
        sa.CheckConstraint("(claim_owner IS NULL AND claim_until IS NULL) OR (claim_owner IS NOT NULL AND claim_until IS NOT NULL)", name="ck_arca_emission_claim_pair"),
    )
    op.create_index("ix_arca_emission_intents_tenant_id", "arca_emission_intents", ["tenant_id"])
    op.create_index("uq_arca_emission_remote_number", "arca_emission_intents", ["series_owner_id", "number"], unique=True, postgresql_where=sa.text("state <> 'rejected'"), sqlite_where=sa.text("state <> 'rejected'"))
    op.create_index("uq_arca_emission_current_proposal", "arca_emission_intents", ["tenant_id", "proposal_id"], unique=True, postgresql_where=sa.text("is_current"), sqlite_where=sa.text("is_current = 1"))
    op.create_index("ix_arca_emission_tenant_sale", "arca_emission_intents", ["tenant_id", "sale_id"])
    op.create_index("ix_arca_emission_pending", "arca_emission_intents", ["tenant_id", "state", "next_action_at"])
    op.create_table(
        "arca_emission_attempts", *_base(),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("emission_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("outcome", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("fence", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["tenant_id", "emission_id"], ["arca_emission_intents.tenant_id", "arca_emission_intents.id"], name="fk_arca_attempt_emission", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_arca_emission_attempts_tenant_id", "arca_emission_attempts", ["tenant_id"])
    op.create_index("ix_arca_attempt_tenant_emission", "arca_emission_attempts", ["tenant_id", "emission_id"])
    op.create_table(
        "arca_document_files", *_base(),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("emission_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("bucket_name", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["tenant_id", "emission_id"], ["arca_emission_intents.tenant_id", "arca_emission_intents.id"], name="fk_arca_file_emission", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["sale_fiscal_documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("environment = 'homologation' AND length(sha256) = 64 AND size_bytes > 0", name="ck_arca_file_identity"),
    )
    op.create_index("ix_arca_document_files_tenant_id", "arca_document_files", ["tenant_id"])
    op.create_index("ix_arca_file_tenant_emission", "arca_document_files", ["tenant_id", "emission_id"])
    # Add the second side of the document/intent cycle only after both exist.
    op.create_foreign_key("fk_sale_fiscal_document_emission", "sale_fiscal_documents", "arca_emission_intents", ["emission_intent_id"], ["id"], ondelete="RESTRICT")
    op.create_unique_constraint("uq_sale_fiscal_document_emission", "sale_fiscal_documents", ["emission_intent_id"])
    op.create_foreign_key("fk_arca_series_active_intent", "arca_series_ownership", "arca_emission_intents", ["tenant_id", "active_intent_id"], ["tenant_id", "id"], ondelete="RESTRICT")
    op.create_table(
        "arca_parameter_cache", *_base(),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("scope_key", sa.String(64), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("cuit", sa.String(11), nullable=False),
        sa.Column("method", sa.String(80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.UniqueConstraint("tenant_id", "scope_key", name="uq_arca_parameter_scope"),
    )
    op.create_index("ix_arca_parameter_cache_tenant_id", "arca_parameter_cache", ["tenant_id"])


def downgrade():
    # Code-review only. Refuse to erase operations, ownership or file history.
    has_data = op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM arca_emission_intents) OR EXISTS (SELECT 1 FROM arca_emission_attempts) OR EXISTS (SELECT 1 FROM arca_document_files) OR EXISTS (SELECT 1 FROM arca_series_ownership) OR EXISTS (SELECT 1 FROM arca_parameter_cache) OR EXISTS (SELECT 1 FROM sale_fiscal_documents WHERE source = 'arca' OR environment IS NOT NULL OR cae IS NOT NULL OR cae_expiry IS NOT NULL OR authorization_snapshot IS NOT NULL OR emission_intent_id IS NOT NULL)")).scalar()
    if has_data:
        raise RuntimeError("Refusing to remove persisted ARCA emission or audit data")
    op.drop_constraint("fk_sale_fiscal_document_emission", "sale_fiscal_documents", type_="foreignkey")
    op.drop_constraint("uq_sale_fiscal_document_emission", "sale_fiscal_documents", type_="unique")
    op.drop_constraint("fk_arca_series_active_intent", "arca_series_ownership", type_="foreignkey")
    op.drop_table("arca_parameter_cache")
    op.drop_table("arca_document_files")
    op.drop_table("arca_emission_attempts")
    op.drop_table("arca_emission_intents")
    op.drop_table("arca_series_ownership")
    op.drop_index("uq_sale_fiscal_documents_arca_number", table_name="sale_fiscal_documents")
    op.drop_index("uq_sale_fiscal_documents_manual_number", table_name="sale_fiscal_documents")
    op.create_unique_constraint("uq_sale_fiscal_documents_number", "sale_fiscal_documents", ["tenant_id", "fiscal_issuer_id", "document_type", "document_number"])
    for column in ("emission_intent_id", "authorization_snapshot", "cae_expiry", "cae", "environment"):
        op.drop_column("sale_fiscal_documents", column)

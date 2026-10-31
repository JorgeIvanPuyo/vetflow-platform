"""Durable encrypted WSAA tickets and fenced authentication claims.

The global cache coordinates certificate-level WSAA authentication; tenant grants
remain separate, scoped and cryptographically bound. No credential backfill.
"""
import sqlalchemy as sa
from alembic import op

revision = "0057_arca_auth"
down_revision = "0056_arca_fiscal_proposals"
branch_labels = None
depends_on = None


def _base():
    return [sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade():
    op.create_table(
        "arca_auth_cache", *_base(),
        sa.Column("cache_key", sa.String(64), nullable=False),
        sa.Column("certificate_fingerprint", sa.String(64), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("service", sa.String(20), nullable=False),
        sa.Column("auth_scope", sa.String(120), nullable=False),
        sa.Column("state", sa.String(20), server_default="idle", nullable=False),
        sa.Column("encrypted_ticket", sa.LargeBinary(), nullable=True),
        sa.Column("encryption_key_version", sa.String(80), nullable=True),
        sa.Column("encryption_key_scope", sa.String(120), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_request_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_not_before", sa.DateTime(timezone=True), nullable=True),
        sa.Column("diagnostic_code", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cache_key", name="uq_arca_auth_cache_scope"),
        sa.UniqueConstraint("certificate_fingerprint", "environment", "service", name="uq_arca_auth_remote_identity"),
        sa.CheckConstraint("environment IN ('homologation','production')", name="ck_arca_auth_environment"),
        sa.CheckConstraint("service = 'wsfe'", name="ck_arca_auth_service"),
        sa.CheckConstraint("state IN ('idle','renewing','ready','backoff','blocked')", name="ck_arca_auth_state"),
        sa.CheckConstraint("fence >= 0", name="ck_arca_auth_fence"),
    )
    op.create_index("ix_arca_auth_retry", "arca_auth_cache", ["state", "retry_not_before"])
    op.create_table(
        "arca_tenant_ticket_grants", *_base(),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("reference", sa.String(220), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("represented_cuit", sa.String(11), nullable=False),
        sa.Column("cache_id", sa.Uuid(), nullable=False),
        sa.Column("encrypted_ticket", sa.LargeBinary(), nullable=False),
        sa.Column("encryption_key_version", sa.String(80), nullable=False),
        sa.Column("encryption_key_scope", sa.String(120), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["cache_id"], ["arca_auth_cache.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("tenant_id", "reference", "environment", "represented_cuit", name="uq_arca_tenant_ticket_grant"),
    )
    op.create_index("ix_arca_tenant_ticket_grants_tenant_id", "arca_tenant_ticket_grants", ["tenant_id"])
    op.create_index("ix_arca_ticket_grants_tenant_cache", "arca_tenant_ticket_grants", ["tenant_id", "cache_id"])


def downgrade():
    # Code review only; never executed against the preserved local copy.
    op.drop_table("arca_tenant_ticket_grants")
    op.drop_table("arca_auth_cache")

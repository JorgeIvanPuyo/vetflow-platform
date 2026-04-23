"""create owners and patients tables"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_create_owners_and_patients"
down_revision = "0001_create_tenants_and_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "owners",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("document_id", sa.String(length=100), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_owners_full_name"), "owners", ["full_name"], unique=False)
    op.create_index(op.f("ix_owners_phone"), "owners", ["phone"], unique=False)
    op.create_index(op.f("ix_owners_tenant_id"), "owners", ["tenant_id"], unique=False)

    op.create_table(
        "patients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("species", sa.String(length=100), nullable=False),
        sa.Column("breed", sa.String(length=100), nullable=True),
        sa.Column("sex", sa.String(length=50), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("weight_kg", sa.Numeric(10, 2), nullable=True),
        sa.Column("allergies", sa.Text(), nullable=True),
        sa.Column("chronic_conditions", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_patients_name"), "patients", ["name"], unique=False)
    op.create_index(op.f("ix_patients_owner_id"), "patients", ["owner_id"], unique=False)
    op.create_index(op.f("ix_patients_species"), "patients", ["species"], unique=False)
    op.create_index(op.f("ix_patients_tenant_id"), "patients", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_patients_tenant_id"), table_name="patients")
    op.drop_index(op.f("ix_patients_species"), table_name="patients")
    op.drop_index(op.f("ix_patients_owner_id"), table_name="patients")
    op.drop_index(op.f("ix_patients_name"), table_name="patients")
    op.drop_table("patients")
    op.drop_index(op.f("ix_owners_tenant_id"), table_name="owners")
    op.drop_index(op.f("ix_owners_phone"), table_name="owners")
    op.drop_index(op.f("ix_owners_full_name"), table_name="owners")
    op.drop_table("owners")

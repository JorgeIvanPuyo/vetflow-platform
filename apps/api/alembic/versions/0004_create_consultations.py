"""create consultations table"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_create_consultations"
down_revision = "0003_patient_est_age"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consultations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("visit_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("anamnesis", sa.Text(), nullable=True),
        sa.Column("clinical_exam", sa.Text(), nullable=True),
        sa.Column("presumptive_diagnosis", sa.Text(), nullable=True),
        sa.Column("diagnostic_plan", sa.Text(), nullable=True),
        sa.Column("therapeutic_plan", sa.Text(), nullable=True),
        sa.Column("final_diagnosis", sa.Text(), nullable=True),
        sa.Column("indications", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_consultations_patient_id"),
        "consultations",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_consultations_tenant_id"),
        "consultations",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_consultations_visit_date"),
        "consultations",
        ["visit_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_consultations_visit_date"), table_name="consultations")
    op.drop_index(op.f("ix_consultations_tenant_id"), table_name="consultations")
    op.drop_index(op.f("ix_consultations_patient_id"), table_name="consultations")
    op.drop_table("consultations")

"""create patient preventive care and file reference tables"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_patient_detail_records"
down_revision = "0005_create_exams"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_preventive_care",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("care_type", sa.String(length=50), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lot_number", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        op.f("ix_patient_preventive_care_applied_at"),
        "patient_preventive_care",
        ["applied_at"],
    )
    op.create_index(
        op.f("ix_patient_preventive_care_care_type"),
        "patient_preventive_care",
        ["care_type"],
    )
    op.create_index(
        op.f("ix_patient_preventive_care_patient_id"),
        "patient_preventive_care",
        ["patient_id"],
    )
    op.create_index(
        op.f("ix_patient_preventive_care_tenant_id"),
        "patient_preventive_care",
        ["tenant_id"],
    )

    op.create_table(
        "patient_file_references",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("external_url", sa.Text(), nullable=True),
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
        op.f("ix_patient_file_references_file_type"),
        "patient_file_references",
        ["file_type"],
    )
    op.create_index(
        op.f("ix_patient_file_references_patient_id"),
        "patient_file_references",
        ["patient_id"],
    )
    op.create_index(
        op.f("ix_patient_file_references_tenant_id"),
        "patient_file_references",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_patient_file_references_tenant_id"),
        table_name="patient_file_references",
    )
    op.drop_index(
        op.f("ix_patient_file_references_patient_id"),
        table_name="patient_file_references",
    )
    op.drop_index(
        op.f("ix_patient_file_references_file_type"),
        table_name="patient_file_references",
    )
    op.drop_table("patient_file_references")

    op.drop_index(
        op.f("ix_patient_preventive_care_tenant_id"),
        table_name="patient_preventive_care",
    )
    op.drop_index(
        op.f("ix_patient_preventive_care_patient_id"),
        table_name="patient_preventive_care",
    )
    op.drop_index(
        op.f("ix_patient_preventive_care_care_type"),
        table_name="patient_preventive_care",
    )
    op.drop_index(
        op.f("ix_patient_preventive_care_applied_at"),
        table_name="patient_preventive_care",
    )
    op.drop_table("patient_preventive_care")

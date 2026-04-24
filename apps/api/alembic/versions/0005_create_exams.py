"""create exams table"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_create_exams"
down_revision = "0004_create_consultations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exams",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consultation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("exam_type", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("result_detail", sa.Text(), nullable=True),
        sa.Column("observations", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["consultation_id"], ["consultations.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_exams_consultation_id"), "exams", ["consultation_id"])
    op.create_index(op.f("ix_exams_patient_id"), "exams", ["patient_id"])
    op.create_index(op.f("ix_exams_requested_at"), "exams", ["requested_at"])
    op.create_index(op.f("ix_exams_status"), "exams", ["status"])
    op.create_index(op.f("ix_exams_tenant_id"), "exams", ["tenant_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_exams_tenant_id"), table_name="exams")
    op.drop_index(op.f("ix_exams_status"), table_name="exams")
    op.drop_index(op.f("ix_exams_requested_at"), table_name="exams")
    op.drop_index(op.f("ix_exams_patient_id"), table_name="exams")
    op.drop_index(op.f("ix_exams_consultation_id"), table_name="exams")
    op.drop_table("exams")

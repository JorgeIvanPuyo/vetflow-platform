"""structured consultations v2"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_structured_consultations_v2"
down_revision = "0006_patient_detail_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "consultations",
        sa.Column("status", sa.String(length=50), server_default="draft", nullable=False),
    )
    op.add_column("consultations", sa.Column("current_step", sa.Integer(), nullable=True))
    op.add_column("consultations", sa.Column("symptoms", sa.Text(), nullable=True))
    op.add_column(
        "consultations",
        sa.Column("symptom_duration", sa.String(length=255), nullable=True),
    )
    op.add_column("consultations", sa.Column("relevant_history", sa.Text(), nullable=True))
    op.add_column("consultations", sa.Column("habits_and_diet", sa.Text(), nullable=True))
    op.add_column("consultations", sa.Column("temperature_c", sa.Float(), nullable=True))
    op.add_column(
        "consultations",
        sa.Column("current_weight_kg", sa.Float(), nullable=True),
    )
    op.add_column("consultations", sa.Column("heart_rate", sa.Integer(), nullable=True))
    op.add_column(
        "consultations",
        sa.Column("respiratory_rate", sa.Integer(), nullable=True),
    )
    op.add_column(
        "consultations",
        sa.Column("mucous_membranes", sa.String(length=255), nullable=True),
    )
    op.add_column("consultations", sa.Column("hydration", sa.String(length=255), nullable=True))
    op.add_column(
        "consultations",
        sa.Column("physical_exam_findings", sa.Text(), nullable=True),
    )
    op.add_column("consultations", sa.Column("diagnostic_tags", sa.JSON(), nullable=True))
    op.add_column(
        "consultations",
        sa.Column("diagnostic_plan_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "consultations",
        sa.Column("therapeutic_plan_notes", sa.Text(), nullable=True),
    )
    op.add_column("consultations", sa.Column("next_control_date", sa.Date(), nullable=True))
    op.add_column(
        "consultations",
        sa.Column("consultation_summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "consultations",
        sa.Column(
            "reminder_requested",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_consultations_status"), "consultations", ["status"])

    op.create_table(
        "consultation_medications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consultation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("medication_name", sa.String(length=255), nullable=False),
        sa.Column("dose_or_quantity", sa.String(length=255), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_consultation_medications_consultation_id"),
        "consultation_medications",
        ["consultation_id"],
    )
    op.create_index(
        op.f("ix_consultation_medications_tenant_id"),
        "consultation_medications",
        ["tenant_id"],
    )

    op.create_table(
        "consultation_study_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consultation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("study_type", sa.String(length=50), nullable=False),
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
        sa.ForeignKeyConstraint(["consultation_id"], ["consultations.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_consultation_study_requests_consultation_id"),
        "consultation_study_requests",
        ["consultation_id"],
    )
    op.create_index(
        op.f("ix_consultation_study_requests_study_type"),
        "consultation_study_requests",
        ["study_type"],
    )
    op.create_index(
        op.f("ix_consultation_study_requests_tenant_id"),
        "consultation_study_requests",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_consultation_study_requests_tenant_id"),
        table_name="consultation_study_requests",
    )
    op.drop_index(
        op.f("ix_consultation_study_requests_study_type"),
        table_name="consultation_study_requests",
    )
    op.drop_index(
        op.f("ix_consultation_study_requests_consultation_id"),
        table_name="consultation_study_requests",
    )
    op.drop_table("consultation_study_requests")

    op.drop_index(
        op.f("ix_consultation_medications_tenant_id"),
        table_name="consultation_medications",
    )
    op.drop_index(
        op.f("ix_consultation_medications_consultation_id"),
        table_name="consultation_medications",
    )
    op.drop_table("consultation_medications")

    op.drop_index(op.f("ix_consultations_status"), table_name="consultations")
    op.drop_column("consultations", "reminder_requested")
    op.drop_column("consultations", "consultation_summary")
    op.drop_column("consultations", "next_control_date")
    op.drop_column("consultations", "therapeutic_plan_notes")
    op.drop_column("consultations", "diagnostic_plan_notes")
    op.drop_column("consultations", "diagnostic_tags")
    op.drop_column("consultations", "physical_exam_findings")
    op.drop_column("consultations", "hydration")
    op.drop_column("consultations", "mucous_membranes")
    op.drop_column("consultations", "respiratory_rate")
    op.drop_column("consultations", "heart_rate")
    op.drop_column("consultations", "current_weight_kg")
    op.drop_column("consultations", "temperature_c")
    op.drop_column("consultations", "habits_and_diet")
    op.drop_column("consultations", "relevant_history")
    op.drop_column("consultations", "symptom_duration")
    op.drop_column("consultations", "symptoms")
    op.drop_column("consultations", "current_step")
    op.drop_column("consultations", "status")

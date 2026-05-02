"""create follow ups"""

import sqlalchemy as sa
from alembic import op

revision = "0014_create_follow_ups"
down_revision = "0013_add_clinic_logo_object_path"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "follow_ups",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("follow_up_type", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"]),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_follow_ups_appointment_id"), "follow_ups", ["appointment_id"])
    op.create_index(op.f("ix_follow_ups_assigned_user_id"), "follow_ups", ["assigned_user_id"])
    op.create_index(op.f("ix_follow_ups_created_by_user_id"), "follow_ups", ["created_by_user_id"])
    op.create_index(op.f("ix_follow_ups_due_at"), "follow_ups", ["due_at"])
    op.create_index(op.f("ix_follow_ups_follow_up_type"), "follow_ups", ["follow_up_type"])
    op.create_index(op.f("ix_follow_ups_owner_id"), "follow_ups", ["owner_id"])
    op.create_index(op.f("ix_follow_ups_patient_id"), "follow_ups", ["patient_id"])
    op.create_index(op.f("ix_follow_ups_source_id"), "follow_ups", ["source_id"])
    op.create_index(op.f("ix_follow_ups_status"), "follow_ups", ["status"])
    op.create_index(op.f("ix_follow_ups_tenant_id"), "follow_ups", ["tenant_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_follow_ups_tenant_id"), table_name="follow_ups")
    op.drop_index(op.f("ix_follow_ups_status"), table_name="follow_ups")
    op.drop_index(op.f("ix_follow_ups_source_id"), table_name="follow_ups")
    op.drop_index(op.f("ix_follow_ups_patient_id"), table_name="follow_ups")
    op.drop_index(op.f("ix_follow_ups_owner_id"), table_name="follow_ups")
    op.drop_index(op.f("ix_follow_ups_follow_up_type"), table_name="follow_ups")
    op.drop_index(op.f("ix_follow_ups_due_at"), table_name="follow_ups")
    op.drop_index(op.f("ix_follow_ups_created_by_user_id"), table_name="follow_ups")
    op.drop_index(op.f("ix_follow_ups_assigned_user_id"), table_name="follow_ups")
    op.drop_index(op.f("ix_follow_ups_appointment_id"), table_name="follow_ups")
    op.drop_table("follow_ups")

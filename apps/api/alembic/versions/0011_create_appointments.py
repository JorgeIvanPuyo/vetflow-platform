"""create appointments"""

import sqlalchemy as sa
from alembic import op

revision = "0011_create_appointments"
down_revision = "0010_clinical_file_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "appointments",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("appointment_type", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="scheduled",
            nullable=False,
        ),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_appointments_tenant_id"), "appointments", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_appointments_patient_id"), "appointments", ["patient_id"], unique=False)
    op.create_index(op.f("ix_appointments_owner_id"), "appointments", ["owner_id"], unique=False)
    op.create_index(op.f("ix_appointments_assigned_user_id"), "appointments", ["assigned_user_id"], unique=False)
    op.create_index(op.f("ix_appointments_created_by_user_id"), "appointments", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_appointments_appointment_type"), "appointments", ["appointment_type"], unique=False)
    op.create_index(op.f("ix_appointments_status"), "appointments", ["status"], unique=False)
    op.create_index(op.f("ix_appointments_start_at"), "appointments", ["start_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_appointments_start_at"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_status"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_appointment_type"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_created_by_user_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_assigned_user_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_owner_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_patient_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_tenant_id"), table_name="appointments")
    op.drop_table("appointments")

"""add user traceability"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_add_user_traceability"
down_revision = "0007_structured_consultations_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patients",
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        op.f("ix_patients_created_by_user_id"),
        "patients",
        ["created_by_user_id"],
    )
    op.create_foreign_key(
        "fk_patients_created_by_user_id_users",
        "patients",
        "users",
        ["created_by_user_id"],
        ["id"],
    )

    op.add_column(
        "consultations",
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "consultations",
        sa.Column("attending_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        op.f("ix_consultations_created_by_user_id"),
        "consultations",
        ["created_by_user_id"],
    )
    op.create_index(
        op.f("ix_consultations_attending_user_id"),
        "consultations",
        ["attending_user_id"],
    )
    op.create_foreign_key(
        "fk_consultations_created_by_user_id_users",
        "consultations",
        "users",
        ["created_by_user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_consultations_attending_user_id_users",
        "consultations",
        "users",
        ["attending_user_id"],
        ["id"],
    )

    op.add_column(
        "exams",
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        op.f("ix_exams_requested_by_user_id"),
        "exams",
        ["requested_by_user_id"],
    )
    op.create_foreign_key(
        "fk_exams_requested_by_user_id_users",
        "exams",
        "users",
        ["requested_by_user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_exams_requested_by_user_id_users",
        "exams",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_exams_requested_by_user_id"), table_name="exams")
    op.drop_column("exams", "requested_by_user_id")

    op.drop_constraint(
        "fk_consultations_attending_user_id_users",
        "consultations",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_consultations_created_by_user_id_users",
        "consultations",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_consultations_attending_user_id"),
        table_name="consultations",
    )
    op.drop_index(
        op.f("ix_consultations_created_by_user_id"),
        table_name="consultations",
    )
    op.drop_column("consultations", "attending_user_id")
    op.drop_column("consultations", "created_by_user_id")

    op.drop_constraint(
        "fk_patients_created_by_user_id_users",
        "patients",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_patients_created_by_user_id"), table_name="patients")
    op.drop_column("patients", "created_by_user_id")

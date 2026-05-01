"""add detail record traceability"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_detail_record_trace"
down_revision = "0008_add_user_traceability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patient_preventive_care",
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        op.f("ix_patient_preventive_care_created_by_user_id"),
        "patient_preventive_care",
        ["created_by_user_id"],
    )
    op.create_foreign_key(
        "fk_patient_preventive_care_created_by_user_id_users",
        "patient_preventive_care",
        "users",
        ["created_by_user_id"],
        ["id"],
    )

    op.add_column(
        "patient_file_references",
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        op.f("ix_patient_file_references_created_by_user_id"),
        "patient_file_references",
        ["created_by_user_id"],
    )
    op.create_foreign_key(
        "fk_patient_file_references_created_by_user_id_users",
        "patient_file_references",
        "users",
        ["created_by_user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_patient_file_references_created_by_user_id_users",
        "patient_file_references",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_patient_file_references_created_by_user_id"),
        table_name="patient_file_references",
    )
    op.drop_column("patient_file_references", "created_by_user_id")

    op.drop_constraint(
        "fk_patient_preventive_care_created_by_user_id_users",
        "patient_preventive_care",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_patient_preventive_care_created_by_user_id"),
        table_name="patient_preventive_care",
    )
    op.drop_column("patient_preventive_care", "created_by_user_id")

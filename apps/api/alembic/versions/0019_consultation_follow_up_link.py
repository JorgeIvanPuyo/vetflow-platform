"""add consultation follow-up link"""

import sqlalchemy as sa
from alembic import op

revision = "0019_consult_follow_up_link"
down_revision = "0018_add_timezone_to_tenants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "consultations",
        sa.Column(
            "consultation_type",
            sa.String(length=50),
            nullable=False,
            server_default="initial",
        ),
    )
    op.add_column(
        "consultations",
        sa.Column("parent_consultation_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        op.f("ix_consultations_consultation_type"),
        "consultations",
        ["consultation_type"],
    )
    op.create_index(
        op.f("ix_consultations_parent_consultation_id"),
        "consultations",
        ["parent_consultation_id"],
    )
    op.create_check_constraint(
        "ck_consultations_consultation_type",
        "consultations",
        "consultation_type IN ('initial', 'follow_up')",
    )
    op.create_foreign_key(
        "fk_consultations_parent_consultation",
        "consultations",
        "consultations",
        ["parent_consultation_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_consultations_parent_consultation",
        "consultations",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_consultations_consultation_type",
        "consultations",
        type_="check",
    )
    op.drop_index(
        op.f("ix_consultations_parent_consultation_id"),
        table_name="consultations",
    )
    op.drop_index(
        op.f("ix_consultations_consultation_type"),
        table_name="consultations",
    )
    op.drop_column("consultations", "parent_consultation_id")
    op.drop_column("consultations", "consultation_type")

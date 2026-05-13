"""add consultation ai summary fields"""

import sqlalchemy as sa
from alembic import op

revision = "0022_consultation_ai_summary"
down_revision = "0021_patient_profile_photo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("consultations", sa.Column("ai_summary", sa.Text(), nullable=True))
    op.add_column(
        "consultations",
        sa.Column("ai_summary_generated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "consultations",
        sa.Column("ai_summary_model", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("consultations", "ai_summary_model")
    op.drop_column("consultations", "ai_summary_generated_at")
    op.drop_column("consultations", "ai_summary")

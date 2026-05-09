"""add diagnostic results to consultations"""

import sqlalchemy as sa
from alembic import op

revision = "0020_consult_diagnostic_results"
down_revision = "0019_consult_follow_up_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "consultations",
        sa.Column("diagnostic_results", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("consultations", "diagnostic_results")

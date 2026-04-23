"""add estimated age to patients"""

import sqlalchemy as sa
from alembic import op

revision = "0003_patient_est_age"
down_revision = "0002_create_owners_and_patients"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patients",
        sa.Column("estimated_age", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("patients", "estimated_age")

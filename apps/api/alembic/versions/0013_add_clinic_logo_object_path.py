"""add clinic logo object path"""

import sqlalchemy as sa
from alembic import op

revision = "0013_add_clinic_logo_object_path"
down_revision = "0012_add_clinic_profile_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("logo_object_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "logo_object_path")

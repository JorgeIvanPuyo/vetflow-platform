"""add clinic profile fields"""

import sqlalchemy as sa
from alembic import op

revision = "0012_add_clinic_profile_fields"
down_revision = "0011_create_appointments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("display_name", sa.String(length=255), nullable=True))
    op.add_column("tenants", sa.Column("logo_url", sa.String(length=1024), nullable=True))
    op.add_column("tenants", sa.Column("phone", sa.String(length=50), nullable=True))
    op.add_column("tenants", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("tenants", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "notes")
    op.drop_column("tenants", "address")
    op.drop_column("tenants", "email")
    op.drop_column("tenants", "phone")
    op.drop_column("tenants", "logo_url")
    op.drop_column("tenants", "display_name")

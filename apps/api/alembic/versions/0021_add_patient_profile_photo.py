"""add patient profile photo fields"""

import sqlalchemy as sa
from alembic import op

revision = "0021_patient_profile_photo"
down_revision = "0020_consult_diagnostic_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("photo_url", sa.Text(), nullable=True))
    op.add_column(
        "patients",
        sa.Column("photo_bucket_name", sa.String(length=255), nullable=True),
    )
    op.add_column("patients", sa.Column("photo_object_path", sa.Text(), nullable=True))
    op.add_column(
        "patients",
        sa.Column("photo_original_filename", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "patients",
        sa.Column("photo_content_type", sa.String(length=100), nullable=True),
    )
    op.add_column("patients", sa.Column("photo_size_bytes", sa.Integer(), nullable=True))
    op.add_column(
        "patients",
        sa.Column("photo_uploaded_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("patients", "photo_uploaded_at")
    op.drop_column("patients", "photo_size_bytes")
    op.drop_column("patients", "photo_content_type")
    op.drop_column("patients", "photo_original_filename")
    op.drop_column("patients", "photo_object_path")
    op.drop_column("patients", "photo_bucket_name")
    op.drop_column("patients", "photo_url")

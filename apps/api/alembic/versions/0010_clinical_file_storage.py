"""add clinical file storage metadata"""

import sqlalchemy as sa
from alembic import op

revision = "0010_clinical_file_storage"
down_revision = "0009_detail_record_trace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patient_file_references",
        sa.Column("bucket_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "patient_file_references",
        sa.Column("object_path", sa.Text(), nullable=True),
    )
    op.add_column(
        "patient_file_references",
        sa.Column("original_filename", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "patient_file_references",
        sa.Column("content_type", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "patient_file_references",
        sa.Column("size_bytes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "patient_file_references",
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("patient_file_references", "uploaded_at")
    op.drop_column("patient_file_references", "size_bytes")
    op.drop_column("patient_file_references", "content_type")
    op.drop_column("patient_file_references", "original_filename")
    op.drop_column("patient_file_references", "object_path")
    op.drop_column("patient_file_references", "bucket_name")

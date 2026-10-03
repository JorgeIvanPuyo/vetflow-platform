"""preserve sale owners and add an explicit nullable receivables cutoff"""

import sqlalchemy as sa
from alembic import op


revision = "0054_receivables_foundation"
down_revision = "0053_sale_payment_batches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("owners", sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("tenant_preferences", sa.Column("receivables_tracking_started_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint("sales_owner_id_fkey", "sales", type_="foreignkey")
    op.create_foreign_key("fk_sales_owner_id_preserve_history", "sales", "owners", ["owner_id"], ["id"], ondelete="RESTRICT")


def downgrade() -> None:
    op.drop_constraint("fk_sales_owner_id_preserve_history", "sales", type_="foreignkey")
    op.create_foreign_key("sales_owner_id_fkey", "sales", "owners", ["owner_id"], ["id"], ondelete="SET NULL")
    op.drop_column("tenant_preferences", "receivables_tracking_started_at")
    op.drop_column("owners", "is_active")

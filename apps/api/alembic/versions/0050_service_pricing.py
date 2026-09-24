"""Add optional service pricing in the clinic's currency."""

import sqlalchemy as sa
from alembic import op

revision = "0050_service_pricing"
down_revision = "0049_inventory_category_refs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No default or backfill: existing services have an unknown price.
    op.add_column("services", sa.Column("price", sa.Numeric(14, 2), nullable=True))
    op.create_check_constraint("ck_services_price_non_negative", "services", "price >= 0")


def downgrade() -> None:
    op.drop_constraint("ck_services_price_non_negative", "services", type_="check")
    op.drop_column("services", "price")

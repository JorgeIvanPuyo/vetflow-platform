"""Merge ARCA and inventory pricing migration branches."""

revision = "0059_merge_arca_inventory"
down_revision = (
    "0058_arca_emission",
    "0055_inventory_sale_price_mode",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

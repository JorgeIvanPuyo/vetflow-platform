"""Purchase-global discounts; historical totals remain gross and unchanged."""
import sqlalchemy as sa
from alembic import op

revision = "0061_purchase_global_discount"
down_revision = "0060_inventory_calculated_prices"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("purchases") as batch:
        batch.add_column(sa.Column("discount_type", sa.String(20), nullable=False, server_default="none"))
        batch.add_column(sa.Column("discount_value", sa.Numeric(16, 2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("discount_amount_ars", sa.Numeric(16, 2), nullable=False, server_default="0"))
        batch.create_check_constraint("ck_purchases_discount_type", "discount_type IN ('none', 'percentage', 'amount')")
        batch.create_check_constraint("ck_purchases_discount_amounts", "discount_value >= 0 AND discount_amount_ars >= 0 AND discount_amount_ars <= total_ars")
        batch.create_check_constraint("ck_purchases_discount_mode_value", "(discount_type = 'none' AND discount_value = 0 AND discount_amount_ars = 0) OR (discount_type = 'percentage' AND discount_value <= 100) OR (discount_type = 'amount' AND discount_value = discount_amount_ars)")


def downgrade():
    # Older application versions use gross amounts and do not understand discounts.
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM purchases WHERE discount_type <> 'none' OR discount_value <> 0 OR discount_amount_ars <> 0")):
        raise RuntimeError("Cannot remove purchase discounts while discounted purchases exist; application rollback would use gross amounts")
    with op.batch_alter_table("purchases") as batch:
        batch.drop_constraint("ck_purchases_discount_mode_value", type_="check")
        batch.drop_constraint("ck_purchases_discount_amounts", type_="check")
        batch.drop_constraint("ck_purchases_discount_type", type_="check")
        batch.drop_column("discount_amount_ars")
        batch.drop_column("discount_value")
        batch.drop_column("discount_type")

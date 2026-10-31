"""Store supplier-agreed return amounts separately from historical gross totals."""
import sqlalchemy as sa
from alembic import op

revision = "0062_purchase_return_agreed"
down_revision = "0061_purchase_global_discount"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("purchase_returns") as batch:
        batch.add_column(sa.Column("agreed_amount_ars", sa.Numeric(16, 2), nullable=True))
        batch.create_check_constraint(
            "ck_purchase_returns_agreed_amount",
            "agreed_amount_ars IS NULL OR "
            "(agreed_amount_ars >= 0 AND agreed_amount_ars < 100000000000000)",
        )


def downgrade():
    if op.get_bind().scalar(sa.text(
        "SELECT count(*) FROM purchase_returns WHERE agreed_amount_ars IS NOT NULL"
    )):
        raise RuntimeError("Cannot remove supplier-agreed return amounts while agreements exist, including zero")
    with op.batch_alter_table("purchase_returns") as batch:
        batch.drop_constraint("ck_purchase_returns_agreed_amount", type_="check")
        batch.drop_column("agreed_amount_ars")

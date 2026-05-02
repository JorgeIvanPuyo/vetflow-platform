"""add inventory links to consultation medications"""

import sqlalchemy as sa
from alembic import op

revision = "0017_consult_med_inventory"
down_revision = "0016_inventory_ts_defaults"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "consultation_medications",
        sa.Column("inventory_item_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "consultation_medications",
        sa.Column("inventory_movement_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "consultation_medications",
        sa.Column(
            "supplied_by_clinic",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "consultation_medications",
        sa.Column("quantity_used", sa.Numeric(12, 2), nullable=True),
    )
    op.create_index(
        op.f("ix_consultation_medications_inventory_item_id"),
        "consultation_medications",
        ["inventory_item_id"],
    )
    op.create_index(
        op.f("ix_consultation_medications_inventory_movement_id"),
        "consultation_medications",
        ["inventory_movement_id"],
    )
    op.create_foreign_key(
        "fk_consult_med_inventory_item",
        "consultation_medications",
        "inventory_items",
        ["inventory_item_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_consult_med_inventory_movement",
        "consultation_medications",
        "inventory_movements",
        ["inventory_movement_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_consult_med_inventory_movement",
        "consultation_medications",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_consult_med_inventory_item",
        "consultation_medications",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_consultation_medications_inventory_movement_id"),
        table_name="consultation_medications",
    )
    op.drop_index(
        op.f("ix_consultation_medications_inventory_item_id"),
        table_name="consultation_medications",
    )
    op.drop_column("consultation_medications", "quantity_used")
    op.drop_column("consultation_medications", "supplied_by_clinic")
    op.drop_column("consultation_medications", "inventory_movement_id")
    op.drop_column("consultation_medications", "inventory_item_id")

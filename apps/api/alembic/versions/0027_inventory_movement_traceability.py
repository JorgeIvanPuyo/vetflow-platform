"""inventory movement traceability"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0027_inventory_traceability"
down_revision = "0026_inventory_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_movements",
        sa.Column("stock_before", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "inventory_movements",
        sa.Column("stock_after", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "inventory_movements",
        sa.Column("unit", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "inventory_movements",
        sa.Column("source_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "inventory_movements",
        sa.Column("source_id", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "inventory_movements",
        sa.Column("operation_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "inventory_movements",
        sa.Column("reverses_movement_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_inventory_movements_reverses_movement_id",
        "inventory_movements",
        "inventory_movements",
        ["reverses_movement_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_inventory_movements_reverses_movement_id",
        "inventory_movements",
        ["reverses_movement_id"],
    )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE inventory_movements AS movement
            SET unit = item.unit
            FROM inventory_items AS item
            WHERE movement.inventory_item_id = item.id
              AND movement.tenant_id = item.tenant_id
              AND movement.unit IS NULL
            """
        )
    )

    op.create_index(
        "ix_inventory_movements_tenant_created_at",
        "inventory_movements",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_inventory_movements_tenant_item_created_at",
        "inventory_movements",
        ["tenant_id", "inventory_item_id", "created_at"],
    )
    op.create_index(
        "ix_inventory_movements_tenant_type_created_at",
        "inventory_movements",
        ["tenant_id", "movement_type", "created_at"],
    )
    op.create_index(
        "ix_inventory_movements_tenant_operation_id",
        "inventory_movements",
        ["tenant_id", "operation_id"],
    )
    op.create_index(
        "ix_inventory_movements_tenant_source",
        "inventory_movements",
        ["tenant_id", "source_type", "source_id"],
    )
    op.create_index(
        "ix_inventory_movements_reverses_movement_id",
        "inventory_movements",
        ["reverses_movement_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_movements_reverses_movement_id", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_tenant_source", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_tenant_operation_id", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_tenant_type_created_at", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_tenant_item_created_at", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_tenant_created_at", table_name="inventory_movements")
    op.drop_constraint(
        "uq_inventory_movements_reverses_movement_id",
        "inventory_movements",
        type_="unique",
    )
    op.drop_constraint(
        "fk_inventory_movements_reverses_movement_id",
        "inventory_movements",
        type_="foreignkey",
    )
    op.drop_column("inventory_movements", "reverses_movement_id")
    op.drop_column("inventory_movements", "operation_id")
    op.drop_column("inventory_movements", "source_id")
    op.drop_column("inventory_movements", "source_type")
    op.drop_column("inventory_movements", "unit")
    op.drop_column("inventory_movements", "stock_after")
    op.drop_column("inventory_movements", "stock_before")

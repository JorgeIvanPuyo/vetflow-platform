"""extend suppliers for soft deactivation and link inventory items"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0043_supplier_inventory"
down_revision = "0042_tenant_pref_money"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0031_create_suppliers already created the canonical supplier directory and
    # linked purchases to it. Replace the unconditional name uniqueness constraint
    # with active-only uniqueness so an inactive historical supplier can coexist
    # with a newly created active supplier of the same normalized name.
    op.drop_constraint(
        "uq_suppliers_tenant_normalized_name",
        "suppliers",
        type_="unique",
    )
    op.create_index(
        "ux_suppliers_tenant_normalized_name_active",
        "suppliers",
        ["tenant_id", "normalized_name"],
        unique=True,
        postgresql_where=sa.text("is_active IS TRUE"),
        sqlite_where=sa.text("is_active = 1"),
    )
    op.create_index(op.f("ix_suppliers_is_active"), "suppliers", ["is_active"])

    op.add_column("inventory_items", sa.Column("supplier_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_inventory_items_supplier_id"),
        "inventory_items",
        ["supplier_id"],
    )
    op.create_foreign_key(
        "fk_inventory_items_supplier_id_suppliers",
        "inventory_items",
        "suppliers",
        ["supplier_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_inventory_items_supplier_id_suppliers",
        "inventory_items",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_inventory_items_supplier_id"), table_name="inventory_items")
    op.drop_column("inventory_items", "supplier_id")

    op.drop_index(op.f("ix_suppliers_is_active"), table_name="suppliers")
    op.drop_index(
        "ux_suppliers_tenant_normalized_name_active",
        table_name="suppliers",
    )

    # A downgrade can only restore the old unconditional uniqueness rule when no
    # duplicate normalized names exist across active/inactive rows. Fail clearly
    # rather than silently deleting or renaming supplier history.
    bind = op.get_bind()
    duplicate = bind.execute(
        sa.text(
            """
            SELECT tenant_id, normalized_name, COUNT(*) AS row_count
            FROM suppliers
            GROUP BY tenant_id, normalized_name
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).mappings().first()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot downgrade 0043_supplier_inventory: duplicate supplier names "
            "exist across active/inactive history"
        )

    op.create_unique_constraint(
        "uq_suppliers_tenant_normalized_name",
        "suppliers",
        ["tenant_id", "normalized_name"],
    )

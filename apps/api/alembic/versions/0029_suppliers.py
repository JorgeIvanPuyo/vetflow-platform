"""add tenant-owned suppliers directory and inventory_items.supplier_id"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0029_suppliers"
down_revision = "0028_tenant_pref_money"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("document_id", sa.String(length=80), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_suppliers_tenant_id"), "suppliers", ["tenant_id"])
    op.create_index(op.f("ix_suppliers_is_active"), "suppliers", ["is_active"])
    op.create_index(
        op.f("ix_suppliers_created_by_user_id"),
        "suppliers",
        ["created_by_user_id"],
    )
    op.create_index(
        "ux_suppliers_tenant_normalized_name_active",
        "suppliers",
        ["tenant_id", "normalized_name"],
        unique=True,
        postgresql_where=sa.text("is_active IS TRUE"),
        sqlite_where=sa.text("is_active = 1"),
    )

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

    op.drop_index(
        "ux_suppliers_tenant_normalized_name_active",
        table_name="suppliers",
    )
    op.drop_index(op.f("ix_suppliers_created_by_user_id"), table_name="suppliers")
    op.drop_index(op.f("ix_suppliers_is_active"), table_name="suppliers")
    op.drop_index(op.f("ix_suppliers_tenant_id"), table_name="suppliers")
    op.drop_table("suppliers")

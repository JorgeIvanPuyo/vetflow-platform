"""create inventory tables"""

import sqlalchemy as sa
from alembic import op

revision = "0015_create_inventory"
down_revision = "0014_create_follow_ups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_items",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("subcategory", sa.String(length=100), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("supplier", sa.String(length=255), nullable=True),
        sa.Column("lot_number", sa.String(length=120), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("current_stock", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("minimum_stock", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("purchase_price_ars", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "profit_margin_percentage",
            sa.Numeric(8, 2),
            nullable=False,
            server_default="35",
        ),
        sa.Column("sale_price_ars", sa.Numeric(12, 2), nullable=True),
        sa.Column("round_sale_price", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inventory_items_category"), "inventory_items", ["category"])
    op.create_index(
        op.f("ix_inventory_items_created_by_user_id"),
        "inventory_items",
        ["created_by_user_id"],
    )
    op.create_index(
        op.f("ix_inventory_items_expiration_date"),
        "inventory_items",
        ["expiration_date"],
    )
    op.create_index(op.f("ix_inventory_items_is_active"), "inventory_items", ["is_active"])
    op.create_index(op.f("ix_inventory_items_name"), "inventory_items", ["name"])
    op.create_index(op.f("ix_inventory_items_supplier"), "inventory_items", ["supplier"])
    op.create_index(op.f("ix_inventory_items_tenant_id"), "inventory_items", ["tenant_id"])
    op.create_index(op.f("ix_inventory_items_unit"), "inventory_items", ["unit"])

    op.create_table(
        "inventory_movements",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column("movement_type", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_cost_ars", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_cost_ars", sa.Numeric(12, 2), nullable=True),
        sa.Column("unit_sale_price_ars", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_sale_price_ars", sa.Numeric(12, 2), nullable=True),
        sa.Column("supplier", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("related_patient_id", sa.Uuid(), nullable=True),
        sa.Column("related_consultation_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"]),
        sa.ForeignKeyConstraint(["related_consultation_id"], ["consultations.id"]),
        sa.ForeignKeyConstraint(["related_patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_inventory_movements_created_by_user_id"),
        "inventory_movements",
        ["created_by_user_id"],
    )
    op.create_index(
        op.f("ix_inventory_movements_inventory_item_id"),
        "inventory_movements",
        ["inventory_item_id"],
    )
    op.create_index(
        op.f("ix_inventory_movements_movement_type"),
        "inventory_movements",
        ["movement_type"],
    )
    op.create_index(op.f("ix_inventory_movements_reason"), "inventory_movements", ["reason"])
    op.create_index(
        op.f("ix_inventory_movements_related_consultation_id"),
        "inventory_movements",
        ["related_consultation_id"],
    )
    op.create_index(
        op.f("ix_inventory_movements_related_patient_id"),
        "inventory_movements",
        ["related_patient_id"],
    )
    op.create_index(op.f("ix_inventory_movements_tenant_id"), "inventory_movements", ["tenant_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_inventory_movements_tenant_id"), table_name="inventory_movements")
    op.drop_index(
        op.f("ix_inventory_movements_related_patient_id"),
        table_name="inventory_movements",
    )
    op.drop_index(
        op.f("ix_inventory_movements_related_consultation_id"),
        table_name="inventory_movements",
    )
    op.drop_index(op.f("ix_inventory_movements_reason"), table_name="inventory_movements")
    op.drop_index(op.f("ix_inventory_movements_movement_type"), table_name="inventory_movements")
    op.drop_index(
        op.f("ix_inventory_movements_inventory_item_id"),
        table_name="inventory_movements",
    )
    op.drop_index(
        op.f("ix_inventory_movements_created_by_user_id"),
        table_name="inventory_movements",
    )
    op.drop_table("inventory_movements")

    op.drop_index(op.f("ix_inventory_items_unit"), table_name="inventory_items")
    op.drop_index(op.f("ix_inventory_items_tenant_id"), table_name="inventory_items")
    op.drop_index(op.f("ix_inventory_items_supplier"), table_name="inventory_items")
    op.drop_index(op.f("ix_inventory_items_name"), table_name="inventory_items")
    op.drop_index(op.f("ix_inventory_items_is_active"), table_name="inventory_items")
    op.drop_index(op.f("ix_inventory_items_expiration_date"), table_name="inventory_items")
    op.drop_index(
        op.f("ix_inventory_items_created_by_user_id"),
        table_name="inventory_items",
    )
    op.drop_index(op.f("ix_inventory_items_category"), table_name="inventory_items")
    op.drop_table("inventory_items")

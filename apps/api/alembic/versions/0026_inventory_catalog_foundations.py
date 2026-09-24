"""inventory catalog foundations"""

from __future__ import annotations

import uuid
from collections import defaultdict

import sqlalchemy as sa
from alembic import op

revision = "0026_inventory_catalog"
down_revision = "0025_consult_steps_6"
branch_labels = None
depends_on = None


CATEGORY_PREFIXES = {
    "medication": "MED",
    "vaccine": "VAC",
    "supply": "INS",
    "food": "ALI",
    "accessory": "ACC",
    "other": "OTR",
}


def upgrade() -> None:
    op.create_table(
        "inventory_code_sequences",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "category",
            name="uq_inventory_code_sequences_tenant_category",
        ),
    )
    op.create_index(
        op.f("ix_inventory_code_sequences_category"),
        "inventory_code_sequences",
        ["category"],
    )
    op.create_index(
        op.f("ix_inventory_code_sequences_tenant_id"),
        "inventory_code_sequences",
        ["tenant_id"],
    )

    op.add_column("inventory_items", sa.Column("brand", sa.String(length=150), nullable=True))
    op.create_index(op.f("ix_inventory_items_brand"), "inventory_items", ["brand"])
    op.add_column(
        "inventory_items",
        sa.Column("internal_code", sa.String(length=16), nullable=True),
    )
    op.create_index(
        op.f("ix_inventory_items_internal_code"),
        "inventory_items",
        ["internal_code"],
    )

    _backfill_internal_codes()

    op.alter_column(
        "inventory_items",
        "internal_code",
        existing_type=sa.String(length=16),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_inventory_items_tenant_internal_code",
        "inventory_items",
        ["tenant_id", "internal_code"],
    )
    op.alter_column(
        "inventory_items",
        "purchase_tax_rate_percentage",
        existing_type=sa.Numeric(5, 2),
        server_default="21",
    )


def downgrade() -> None:
    op.alter_column(
        "inventory_items",
        "purchase_tax_rate_percentage",
        existing_type=sa.Numeric(5, 2),
        server_default="0",
    )
    op.drop_constraint(
        "uq_inventory_items_tenant_internal_code",
        "inventory_items",
        type_="unique",
    )
    op.drop_index(op.f("ix_inventory_items_internal_code"), table_name="inventory_items")
    op.drop_column("inventory_items", "internal_code")
    op.drop_index(op.f("ix_inventory_items_brand"), table_name="inventory_items")
    op.drop_column("inventory_items", "brand")
    op.drop_index(
        op.f("ix_inventory_code_sequences_tenant_id"),
        table_name="inventory_code_sequences",
    )
    op.drop_index(
        op.f("ix_inventory_code_sequences_category"),
        table_name="inventory_code_sequences",
    )
    op.drop_table("inventory_code_sequences")


def _backfill_internal_codes() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, tenant_id, category
            FROM inventory_items
            ORDER BY tenant_id, category, created_at, id
            """
        )
    ).mappings()

    counters: dict[tuple[object, str], int] = defaultdict(int)
    for row in rows:
        key = (row["tenant_id"], row["category"])
        counters[key] += 1
        prefix = CATEGORY_PREFIXES.get(row["category"], "OTR")
        bind.execute(
            sa.text(
                """
                UPDATE inventory_items
                SET internal_code = :internal_code
                WHERE id = :id
                """
            ),
            {"internal_code": f"{prefix}-{counters[key]:05d}", "id": str(row["id"])},
        )

    for (tenant_id, category), last_value in counters.items():
        bind.execute(
            sa.text(
                """
                INSERT INTO inventory_code_sequences (
                    id,
                    tenant_id,
                    category,
                    last_value,
                    created_at,
                    updated_at
                )
                VALUES (
                    :id,
                    :tenant_id,
                    :category,
                    :last_value,
                    now(),
                    now()
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": str(tenant_id),
                "category": category,
                "last_value": last_value,
            },
        )

"""add tenant-owned catalog items with mucous membrane and hydration presets"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0041_catalog_items"
down_revision = "0040_tenant_prefs_services"
branch_labels = None
depends_on = None


# These presets replicate the option lists previously hardcoded in the consultation
# form (apps/web consultation-workflow.tsx), so every existing tenant keeps seeing
# exactly the same choices and can customize them afterwards.
CATALOG_SEED_TEMPLATES_V1: dict[str, tuple[dict[str, object], ...]] = {
    "mucous_membrane": (
        {"name": "Rosas", "normalized_name": "rosas", "sort_order": 10},
        {"name": "Rosas pálidas", "normalized_name": "rosas palidas", "sort_order": 20},
        {"name": "Pálidas", "normalized_name": "palidas", "sort_order": 30},
        {"name": "Congestionadas", "normalized_name": "congestionadas", "sort_order": 40},
        {"name": "Cianóticas", "normalized_name": "cianoticas", "sort_order": 50},
        {"name": "Ictéricas", "normalized_name": "ictericas", "sort_order": 60},
    ),
    "hydration": (
        {"name": "Normal", "normalized_name": "normal", "sort_order": 10},
        {"name": "Leve deshidratación", "normalized_name": "leve deshidratacion", "sort_order": 20},
        {"name": "Moderada", "normalized_name": "moderada", "sort_order": 30},
        {"name": "Severa", "normalized_name": "severa", "sort_order": 40},
    ),
}


def upgrade() -> None:
    op.create_table(
        "catalog_items",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("catalog_type", sa.String(length=80), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(length=80), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
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
        sa.ForeignKeyConstraint(["parent_id"], ["catalog_items.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_catalog_items_tenant_id"), "catalog_items", ["tenant_id"])
    op.create_index(op.f("ix_catalog_items_catalog_type"), "catalog_items", ["catalog_type"])
    op.create_index(op.f("ix_catalog_items_sort_order"), "catalog_items", ["sort_order"])
    op.create_index(op.f("ix_catalog_items_is_active"), "catalog_items", ["is_active"])
    op.create_index(
        op.f("ix_catalog_items_created_by_user_id"),
        "catalog_items",
        ["created_by_user_id"],
    )
    op.create_index(
        "ix_catalog_items_tenant_type_active_sort",
        "catalog_items",
        ["tenant_id", "catalog_type", "is_active", "sort_order"],
    )
    op.create_index(
        "ux_catalog_items_tenant_type_normalized_name_active",
        "catalog_items",
        ["tenant_id", "catalog_type", "normalized_name"],
        unique=True,
        postgresql_where=sa.text("is_active IS TRUE"),
        sqlite_where=sa.text("is_active = 1"),
    )

    _seed_existing_tenants()


def downgrade() -> None:
    op.drop_index(
        "ux_catalog_items_tenant_type_normalized_name_active",
        table_name="catalog_items",
    )
    op.drop_index("ix_catalog_items_tenant_type_active_sort", table_name="catalog_items")
    op.drop_index(op.f("ix_catalog_items_created_by_user_id"), table_name="catalog_items")
    op.drop_index(op.f("ix_catalog_items_is_active"), table_name="catalog_items")
    op.drop_index(op.f("ix_catalog_items_sort_order"), table_name="catalog_items")
    op.drop_index(op.f("ix_catalog_items_catalog_type"), table_name="catalog_items")
    op.drop_index(op.f("ix_catalog_items_tenant_id"), table_name="catalog_items")
    op.drop_table("catalog_items")


def _seed_existing_tenants() -> None:
    bind = op.get_bind()
    tenant_ids = [
        row["id"] for row in bind.execute(sa.text("SELECT id FROM tenants")).mappings()
    ]
    if not tenant_ids:
        return

    catalog_items_table = sa.table(
        "catalog_items",
        sa.column("id", sa.Uuid()),
        sa.column("tenant_id", sa.Uuid()),
        sa.column("catalog_type", sa.String()),
        sa.column("name", sa.String()),
        sa.column("normalized_name", sa.String()),
        sa.column("metadata", sa.JSON()),
        sa.column("sort_order", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
    )

    rows = []
    for tenant_id in tenant_ids:
        tenant_uuid = tenant_id if isinstance(tenant_id, uuid.UUID) else uuid.UUID(str(tenant_id))
        for catalog_type, templates in CATALOG_SEED_TEMPLATES_V1.items():
            existing = bind.execute(
                sa.text(
                    "SELECT 1 FROM catalog_items "
                    "WHERE tenant_id = :tenant_id AND catalog_type = :catalog_type "
                    "LIMIT 1"
                ),
                {"tenant_id": str(tenant_uuid), "catalog_type": catalog_type},
            ).first()
            if existing is not None:
                continue
            for template in templates:
                rows.append(
                    {
                        "id": uuid.uuid4(),
                        "tenant_id": tenant_uuid,
                        "catalog_type": catalog_type,
                        "metadata": {},
                        "is_active": True,
                        **template,
                    }
                )

    if rows:
        op.bulk_insert(catalog_items_table, rows)

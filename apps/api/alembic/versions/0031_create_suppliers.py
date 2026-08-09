"""create suppliers and link purchases"""

from __future__ import annotations

import uuid
from collections import defaultdict

import sqlalchemy as sa
from alembic import op


revision = "0031_create_suppliers"
down_revision = "0030_create_purchases"
branch_labels = None
depends_on = None


def _clean(value: str) -> str:
    return " ".join(value.split())


def _normalized(value: str) -> str:
    return _clean(value).casefold()


def _optional(value: str | None) -> str | None:
    cleaned = _clean(value) if value else ""
    return cleaned or None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("tax_id", sa.String(length=80), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
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
    op.create_index(
        op.f("ix_suppliers_created_by_user_id"), "suppliers", ["created_by_user_id"]
    )
    op.add_column("purchases", sa.Column("supplier_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_purchases_supplier_id_suppliers",
        "purchases",
        "suppliers",
        ["supplier_id"],
        ["id"],
    )

    connection = op.get_bind()
    purchases = connection.execute(
        sa.text(
            """
            SELECT id, tenant_id, supplier_name, supplier_tax_id,
                   created_by_user_id, created_at, updated_at
            FROM purchases
            ORDER BY tenant_id, created_at, id
            """
        )
    ).mappings()
    groups: dict[tuple[uuid.UUID, str], list[dict]] = defaultdict(list)
    for purchase in purchases:
        groups[(purchase["tenant_id"], _normalized(purchase["supplier_name"]))].append(
            dict(purchase)
        )

    claimed_tax_ids: set[tuple[uuid.UUID, str]] = set()
    for (tenant_id, normalized_name), rows in groups.items():
        first = rows[0]
        tax_ids = {_optional(row["supplier_tax_id"]) for row in rows}
        tax_ids.discard(None)
        tax_id = next(iter(tax_ids)) if len(tax_ids) == 1 else None
        if tax_id is not None and (tenant_id, tax_id) in claimed_tax_ids:
            tax_id = None
        if tax_id is not None:
            claimed_tax_ids.add((tenant_id, tax_id))
        supplier_id = uuid.uuid4()
        connection.execute(
            sa.text(
                """
                INSERT INTO suppliers (
                    id, tenant_id, name, normalized_name, tax_id, is_active,
                    created_by_user_id, created_at, updated_at
                ) VALUES (
                    :id, :tenant_id, :name, :normalized_name, :tax_id, true,
                    :created_by_user_id, :created_at, :updated_at
                )
                """
            ),
            {
                "id": supplier_id,
                "tenant_id": tenant_id,
                "name": _clean(first["supplier_name"]),
                "normalized_name": normalized_name,
                "tax_id": tax_id,
                "created_by_user_id": first["created_by_user_id"],
                "created_at": first["created_at"],
                "updated_at": max(row["updated_at"] for row in rows),
            },
        )
        connection.execute(
            sa.text("UPDATE purchases SET supplier_id = :supplier_id WHERE id IN :ids").bindparams(
                sa.bindparam("ids", expanding=True)
            ),
            {"supplier_id": supplier_id, "ids": [row["id"] for row in rows]},
        )

    op.alter_column("purchases", "supplier_id", nullable=False)
    op.create_index(op.f("ix_purchases_supplier_id"), "purchases", ["supplier_id"])
    op.create_index(
        "ix_purchases_tenant_supplier_id", "purchases", ["tenant_id", "supplier_id"]
    )
    op.create_unique_constraint(
        "uq_suppliers_tenant_normalized_name",
        "suppliers",
        ["tenant_id", "normalized_name"],
    )
    op.create_unique_constraint(
        "uq_suppliers_tenant_tax_id", "suppliers", ["tenant_id", "tax_id"]
    )
    op.create_index(
        "ix_suppliers_tenant_active_name",
        "suppliers",
        ["tenant_id", "is_active", "name"],
    )
    op.create_index(
        "ix_suppliers_tenant_updated_at", "suppliers", ["tenant_id", "updated_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_purchases_tenant_supplier_id", table_name="purchases")
    op.drop_index(op.f("ix_purchases_supplier_id"), table_name="purchases")
    op.drop_constraint(
        "fk_purchases_supplier_id_suppliers", "purchases", type_="foreignkey"
    )
    op.drop_column("purchases", "supplier_id")

    op.drop_index("ix_suppliers_tenant_updated_at", table_name="suppliers")
    op.drop_index("ix_suppliers_tenant_active_name", table_name="suppliers")
    op.drop_constraint("uq_suppliers_tenant_tax_id", "suppliers", type_="unique")
    op.drop_constraint(
        "uq_suppliers_tenant_normalized_name", "suppliers", type_="unique"
    )
    op.drop_index(op.f("ix_suppliers_created_by_user_id"), table_name="suppliers")
    op.drop_index(op.f("ix_suppliers_tenant_id"), table_name="suppliers")
    op.drop_table("suppliers")

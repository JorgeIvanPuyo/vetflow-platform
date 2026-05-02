"""add inventory timestamp defaults"""

import sqlalchemy as sa
from alembic import op

revision = "0016_inventory_ts_defaults"
down_revision = "0015_create_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE inventory_items
        SET created_at = now()
        WHERE created_at IS NULL
        """
    )
    op.execute(
        """
        UPDATE inventory_items
        SET updated_at = now()
        WHERE updated_at IS NULL
        """
    )
    op.execute(
        """
        UPDATE inventory_movements
        SET created_at = now()
        WHERE created_at IS NULL
        """
    )
    op.execute(
        """
        UPDATE inventory_movements
        SET updated_at = now()
        WHERE updated_at IS NULL
        """
    )

    op.alter_column(
        "inventory_items",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )
    op.alter_column(
        "inventory_items",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )
    op.alter_column(
        "inventory_movements",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )
    op.alter_column(
        "inventory_movements",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "inventory_movements",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        "inventory_movements",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        "inventory_items",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        "inventory_items",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=False,
    )

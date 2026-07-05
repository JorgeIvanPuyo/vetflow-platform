"""add role to users"""

import sqlalchemy as sa
from alembic import op

revision = "0024_add_user_role"
down_revision = "0023_inventory_item_tax_rates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=32),
            nullable=False,
            server_default="medico_veterinario",
        ),
    )
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('superadmin', 'medico_veterinario', 'contador')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")

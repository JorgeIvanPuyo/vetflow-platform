"""Allow the operational secretary role."""
from alembic import op
import sqlalchemy as sa

revision = "0051_secretary_role"
down_revision = "0050_service_pricing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role", "users",
        "role IN ('superadmin', 'clinic_admin', 'medico_veterinario', 'contador', 'secretaria')",
    )


def downgrade() -> None:
    # Never silently promote secretaries to clinical staff on rollback.
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM users WHERE role = 'secretaria')")):
        raise RuntimeError("Reassign secretary users explicitly before downgrading")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role", "users",
        "role IN ('superadmin', 'clinic_admin', 'medico_veterinario', 'contador')",
    )

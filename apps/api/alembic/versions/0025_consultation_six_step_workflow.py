"""normalize consultation current_step for six-step workflow"""

from alembic import op

revision = "0025_consult_steps_6"
down_revision = "0024_add_user_role"
branch_labels = None
depends_on = None


def upgrade_current_step(value: int | None) -> int | None:
    if value is None:
        return None
    if value in {1, 2, 3, 4}:
        return value
    if value == 5:
        return 4
    if value in {6, 7}:
        return 6
    if value == 8:
        return 5
    return 1


def downgrade_current_step(value: int | None) -> int | None:
    if value is None:
        return None
    if value in {1, 2, 3, 4}:
        return value
    if value == 5:
        return 8
    if value == 6:
        return 6
    return 1


def upgrade() -> None:
    op.execute(
        """
        UPDATE consultations
        SET current_step = CASE
            WHEN current_step IN (1, 2, 3, 4) THEN current_step
            WHEN current_step = 5 THEN 4
            WHEN current_step IN (6, 7) THEN 6
            WHEN current_step = 8 THEN 5
            ELSE 1
        END
        WHERE current_step IS NOT NULL
        """
    )


def downgrade() -> None:
    # Canonical only: combined six-step positions cannot reconstruct the exact old subsection.
    op.execute(
        """
        UPDATE consultations
        SET current_step = CASE
            WHEN current_step IN (1, 2, 3, 4) THEN current_step
            WHEN current_step = 5 THEN 8
            WHEN current_step = 6 THEN 6
            ELSE 1
        END
        WHERE current_step IS NOT NULL
        """
    )

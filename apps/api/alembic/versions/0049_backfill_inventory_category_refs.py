"""backfill inventory category catalog references where mapping is unambiguous"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0049_inventory_category_refs"
down_revision = "0048_operational_currency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Link legacy inventory category codes to the tenant-owned seeded catalog rows.

    Existing inventory keeps the legacy ``category`` code for API compatibility.
    The optional FK is populated only when exactly one active catalog item in the
    same tenant has a matching ``inventory_category`` code, avoiding ambiguous or
    cross-tenant assignments.
    """
    op.get_bind().execute(
        sa.text(
            """
            WITH category_candidates AS (
                SELECT
                    id,
                    tenant_id,
                    code,
                    COUNT(*) OVER (PARTITION BY tenant_id, code) AS candidate_count
                FROM catalog_items
                WHERE catalog_type = 'inventory_category'
                  AND is_active IS TRUE
                  AND code IS NOT NULL
            )
            UPDATE inventory_items AS item
            SET category_catalog_item_id = candidate.id
            FROM category_candidates AS candidate
            WHERE item.category_catalog_item_id IS NULL
              AND candidate.candidate_count = 1
              AND candidate.tenant_id = item.tenant_id
              AND candidate.code = item.category
            """
        )
    )


def downgrade() -> None:
    # This is a conservative data backfill into an already-optional FK column.
    # Clearing references on downgrade could remove links created or edited by a
    # clinic after the upgrade, so the data is intentionally retained.
    pass

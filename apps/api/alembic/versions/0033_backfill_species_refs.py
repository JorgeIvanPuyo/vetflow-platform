"""backfill patients.species_catalog_item_id from existing text where unambiguous"""

from __future__ import annotations

import re
import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "0033_backfill_species_refs"
down_revision = "0032_clinical_catalog_ext"
branch_labels = None
depends_on = None


# Mirrors app/services/normalization.py:normalize_name. Duplicated on purpose: this
# migration is a frozen historical snapshot and must not import from application code
# that can keep evolving.
def _normalize_name(value: str) -> str:
    stripped = value.strip().lower()
    collapsed = re.sub(r"\s+", " ", stripped)
    decomposed = unicodedata.normalize("NFKD", collapsed)
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def upgrade() -> None:
    bind = op.get_bind()

    patients = sa.table(
        "patients",
        sa.column("id", sa.Uuid()),
        sa.column("tenant_id", sa.Uuid()),
        sa.column("species", sa.String()),
        sa.column("species_catalog_item_id", sa.Uuid()),
    )
    catalog_items = sa.table(
        "catalog_items",
        sa.column("id", sa.Uuid()),
        sa.column("tenant_id", sa.Uuid()),
        sa.column("catalog_type", sa.String()),
        sa.column("normalized_name", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )

    rows = bind.execute(
        sa.select(patients.c.id, patients.c.tenant_id, patients.c.species).where(
            patients.c.species_catalog_item_id.is_(None),
            patients.c.species.is_not(None),
        )
    ).all()
    if not rows:
        return

    match_cache: dict[tuple[str, str], str | None] = {}
    for row in rows:
        normalized = _normalize_name(row.species) if row.species else None
        if not normalized:
            continue
        cache_key = (str(row.tenant_id), normalized)
        if cache_key not in match_cache:
            matches = bind.execute(
                sa.select(catalog_items.c.id).where(
                    catalog_items.c.tenant_id == row.tenant_id,
                    catalog_items.c.catalog_type == "species",
                    catalog_items.c.normalized_name == normalized,
                    catalog_items.c.is_active.is_(True),
                )
            ).all()
            match_cache[cache_key] = str(matches[0][0]) if len(matches) == 1 else None
        catalog_item_id = match_cache[cache_key]
        if catalog_item_id is not None:
            bind.execute(
                patients.update()
                .where(patients.c.id == row.id)
                .values(species_catalog_item_id=catalog_item_id)
            )


def downgrade() -> None:
    # See 0031's downgrade for why backfilled references are left in place.
    pass

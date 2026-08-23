"""backfill exam/preventive-care/document catalog references from existing text"""

from __future__ import annotations

import re
import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "0031_backfill_catalog_refs"
down_revision = "0030_operational_catalog_refs"
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
    # Inventory items are intentionally excluded: product has scoped the inventory
    # side of this catalog work for a later pass, so its category_catalog_item_id
    # column stays unbackfilled for now.
    _backfill_by_normalized_name(
        bind,
        table="exams",
        text_column="exam_type",
        fk_column="exam_catalog_item_id",
        catalog_type="exam_type",
    )
    _backfill_by_normalized_name(
        bind,
        table="consultation_study_requests",
        text_column="name",
        fk_column="exam_catalog_item_id",
        catalog_type="exam_type",
    )
    _backfill_by_normalized_name(
        bind,
        table="patient_preventive_care",
        text_column="name",
        fk_column="catalog_item_id",
        catalog_type="preventive_care_type",
    )
    # file_type stores a stable technical code (e.g. "radiography"), not a display
    # name, so matching on catalog_items.code is the unambiguous path here.
    _backfill_by_code(
        bind,
        table="patient_file_references",
        text_column="file_type",
        fk_column="file_type_catalog_item_id",
        catalog_type="document_type",
    )


def downgrade() -> None:
    # Values backfilled by upgrade() are left in place: they only ever link a record
    # to a catalog item that already unambiguously matched its own text, so there is
    # nothing unsafe about keeping that link once the columns exist (dropping the
    # columns themselves is handled by downgrading 0030).
    pass


def _backfill_by_normalized_name(
    bind,
    *,
    table: str,
    text_column: str,
    fk_column: str,
    catalog_type: str,
) -> None:
    source = sa.table(
        table,
        sa.column("id", sa.Uuid()),
        sa.column("tenant_id", sa.Uuid()),
        sa.column(text_column, sa.String()),
        sa.column(fk_column, sa.Uuid()),
    )
    rows = bind.execute(
        sa.select(source.c.id, source.c.tenant_id, source.c[text_column]).where(
            source.c[fk_column].is_(None),
            source.c[text_column].is_not(None),
        )
    ).all()
    _apply_matches(
        bind,
        table=table,
        fk_column=fk_column,
        rows=rows,
        catalog_type=catalog_type,
        match_column="normalized_name",
        key_fn=lambda text_value: _normalize_name(text_value) if text_value else None,
    )


def _backfill_by_code(
    bind,
    *,
    table: str,
    text_column: str,
    fk_column: str,
    catalog_type: str,
) -> None:
    source = sa.table(
        table,
        sa.column("id", sa.Uuid()),
        sa.column("tenant_id", sa.Uuid()),
        sa.column(text_column, sa.String()),
        sa.column(fk_column, sa.Uuid()),
    )
    rows = bind.execute(
        sa.select(source.c.id, source.c.tenant_id, source.c[text_column]).where(
            source.c[fk_column].is_(None),
            source.c[text_column].is_not(None),
        )
    ).all()
    _apply_matches(
        bind,
        table=table,
        fk_column=fk_column,
        rows=rows,
        catalog_type=catalog_type,
        match_column="code",
        key_fn=lambda text_value: text_value or None,
    )


def _apply_matches(
    bind,
    *,
    table: str,
    fk_column: str,
    rows,
    catalog_type: str,
    match_column: str,
    key_fn,
) -> None:
    if not rows:
        return

    catalog_items = sa.table(
        "catalog_items",
        sa.column("id", sa.Uuid()),
        sa.column("tenant_id", sa.Uuid()),
        sa.column("catalog_type", sa.String()),
        sa.column("normalized_name", sa.String()),
        sa.column("code", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    target = sa.table(
        table,
        sa.column("id", sa.Uuid()),
        sa.column(fk_column, sa.Uuid()),
    )

    match_cache: dict[tuple[str, str], str | None] = {}
    for row in rows:
        text_value = row[2]
        key = key_fn(text_value)
        if not key:
            continue
        cache_key = (str(row.tenant_id), key)
        if cache_key not in match_cache:
            matches = bind.execute(
                sa.select(catalog_items.c.id).where(
                    catalog_items.c.tenant_id == row.tenant_id,
                    catalog_items.c.catalog_type == catalog_type,
                    catalog_items.c[match_column] == key,
                    catalog_items.c.is_active.is_(True),
                )
            ).all()
            match_cache[cache_key] = str(matches[0][0]) if len(matches) == 1 else None
        catalog_item_id = match_cache[cache_key]
        if catalog_item_id is not None:
            bind.execute(
                target.update()
                .where(target.c.id == row.id)
                .values({fk_column: catalog_item_id})
            )

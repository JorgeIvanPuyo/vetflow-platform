"""add species/breed/diagnostic-tag/prescription-template catalogs and patient refs"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0032_clinical_catalog_ext"
down_revision = "0031_backfill_catalog_refs"
branch_labels = None
depends_on = None


# Species mirror the options already hardcoded in the patient form
# (apps/web patients-screen.tsx); breed and prescription_template start empty since
# they are clinic- and region-specific. Diagnostic tag categories are generic enough
# to ship as a starting point for the free-text diagnostic_tags autocomplete.
CATALOG_SEED_TEMPLATES_V3: dict[str, tuple[dict[str, object], ...]] = {
    "species": (
        {"name": "Canino", "normalized_name": "canino", "sort_order": 10},
        {"name": "Felino", "normalized_name": "felino", "sort_order": 20},
        {"name": "Otro", "normalized_name": "otro", "sort_order": 30},
    ),
    "diagnostic_tag": (
        {"name": "Respiratorio", "normalized_name": "respiratorio", "sort_order": 10},
        {"name": "Digestivo", "normalized_name": "digestivo", "sort_order": 20},
        {"name": "Dermatológico", "normalized_name": "dermatologico", "sort_order": 30},
        {"name": "Musculoesquelético", "normalized_name": "musculoesqueletico", "sort_order": 40},
        {"name": "Renal", "normalized_name": "renal", "sort_order": 50},
        {"name": "Agudo", "normalized_name": "agudo", "sort_order": 60},
        {"name": "Crónico", "normalized_name": "cronico", "sort_order": 70},
    ),
}

_PATIENT_REFERENCE_COLUMNS = (
    ("species_catalog_item_id", "fk_patients_species_catalog_item_id_catalog_items"),
    ("breed_catalog_item_id", "fk_patients_breed_catalog_item_id_catalog_items"),
)


def upgrade() -> None:
    for column_name, fk_name in _PATIENT_REFERENCE_COLUMNS:
        op.add_column("patients", sa.Column(column_name, sa.Uuid(), nullable=True))
        op.create_index(
            op.f(f"ix_patients_{column_name}"),
            "patients",
            [column_name],
        )
        op.create_foreign_key(
            fk_name,
            "patients",
            "catalog_items",
            [column_name],
            ["id"],
        )

    _seed_existing_tenants()


def downgrade() -> None:
    # See 0030's downgrade for why seeded catalog_items rows are left in place.
    for column_name, fk_name in reversed(_PATIENT_REFERENCE_COLUMNS):
        op.drop_constraint(fk_name, "patients", type_="foreignkey")
        op.drop_index(op.f(f"ix_patients_{column_name}"), table_name="patients")
        op.drop_column("patients", column_name)


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
        for catalog_type, templates in CATALOG_SEED_TEMPLATES_V3.items():
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

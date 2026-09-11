"""add operational catalog types, seed defaults, and optional catalog references"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0044_operational_catalog_refs"
down_revision = "0043_supplier_inventory"
branch_labels = None
depends_on = None


# These presets mirror the fixed option lists already hardcoded across the frontend
# and backend (inventory categories, document types) or introduce a sensible starting
# point for freeform names (exam/study names, preventive care names, follow-up
# templates), so every existing tenant gets a usable catalog it can then customize.
CATALOG_SEED_TEMPLATES_V2: dict[str, tuple[dict[str, object], ...]] = {
    "inventory_category": (
        {"name": "Medicamento", "normalized_name": "medicamento", "code": "medication", "sort_order": 10},
        {"name": "Vacuna", "normalized_name": "vacuna", "code": "vaccine", "sort_order": 20},
        {"name": "Insumo", "normalized_name": "insumo", "code": "supply", "sort_order": 30},
        {"name": "Alimento", "normalized_name": "alimento", "code": "food", "sort_order": 40},
        {"name": "Otro", "normalized_name": "otro", "code": "other", "sort_order": 50},
    ),
    "document_type": (
        {"name": "Laboratorio", "normalized_name": "laboratorio", "code": "laboratory", "sort_order": 10},
        {"name": "Radiografía", "normalized_name": "radiografia", "code": "radiography", "sort_order": 20},
        {"name": "Ecografía", "normalized_name": "ecografia", "code": "ultrasound", "sort_order": 30},
        {"name": "Foto clínica", "normalized_name": "foto clinica", "code": "clinical_photo", "sort_order": 40},
        {"name": "Documento", "normalized_name": "documento", "code": "document", "sort_order": 50},
        {"name": "Otro", "normalized_name": "otro", "code": "other", "sort_order": 60},
    ),
    "exam_type": (
        {"name": "Hemograma completo", "normalized_name": "hemograma completo", "code": None, "sort_order": 10},
        {"name": "Perfil bioquímico", "normalized_name": "perfil bioquimico", "code": None, "sort_order": 20},
        {"name": "Urianálisis", "normalized_name": "urianalisis", "code": None, "sort_order": 30},
        {"name": "Coproparasitológico", "normalized_name": "coproparasitologico", "code": None, "sort_order": 40},
        {"name": "Radiografía", "normalized_name": "radiografia", "code": None, "sort_order": 50},
        {"name": "Ecografía abdominal", "normalized_name": "ecografia abdominal", "code": None, "sort_order": 60},
    ),
    "preventive_care_type": (
        {"name": "Vacuna antirrábica", "normalized_name": "vacuna antirrabica", "code": None, "sort_order": 10},
        {"name": "Vacuna polivalente", "normalized_name": "vacuna polivalente", "code": None, "sort_order": 20},
        {"name": "Desparasitación interna", "normalized_name": "desparasitacion interna", "code": None, "sort_order": 30},
        {"name": "Desparasitación externa", "normalized_name": "desparasitacion externa", "code": None, "sort_order": 40},
        {"name": "Control antipulgas y garrapatas", "normalized_name": "control antipulgas y garrapatas", "code": None, "sort_order": 50},
    ),
    "follow_up_template": (
        {"name": "Control posterior a consulta", "normalized_name": "control posterior a consulta", "code": None, "sort_order": 10},
        {"name": "Recordatorio de vacunación", "normalized_name": "recordatorio de vacunacion", "code": None, "sort_order": 20},
        {"name": "Recordatorio de desparasitación", "normalized_name": "recordatorio de desparasitacion", "code": None, "sort_order": 30},
        {"name": "Revisión de resultado de examen", "normalized_name": "revision de resultado de examen", "code": None, "sort_order": 40},
        {"name": "Seguimiento general", "normalized_name": "seguimiento general", "code": None, "sort_order": 50},
    ),
}

#: (table, column, fk_constraint_name) — the constraint name is spelled out explicitly
# (rather than derived) because Postgres caps identifiers at 63 characters and the
# `fk_<table>_<column>_catalog_items` pattern overflows for the longer table names.
_REFERENCE_COLUMNS = (
    ("inventory_items", "category_catalog_item_id", "fk_inventory_items_category_catalog_item_id_catalog_items"),
    ("exams", "exam_catalog_item_id", "fk_exams_exam_catalog_item_id_catalog_items"),
    (
        "consultation_study_requests",
        "exam_catalog_item_id",
        "fk_consultation_study_requests_exam_catalog_item_id",
    ),
    (
        "patient_preventive_care",
        "catalog_item_id",
        "fk_patient_preventive_care_catalog_item_id_catalog_items",
    ),
    (
        "patient_file_references",
        "file_type_catalog_item_id",
        "fk_patient_file_references_file_type_catalog_item_id",
    ),
)


def upgrade() -> None:
    for table_name, column_name, fk_name in _REFERENCE_COLUMNS:
        op.add_column(table_name, sa.Column(column_name, sa.Uuid(), nullable=True))
        op.create_index(
            op.f(f"ix_{table_name}_{column_name}"),
            table_name,
            [column_name],
        )
        op.create_foreign_key(
            fk_name,
            table_name,
            "catalog_items",
            [column_name],
            ["id"],
        )

    _seed_existing_tenants()


def downgrade() -> None:
    # Seeded catalog_items rows are left in place: a clinic may have already edited or
    # referenced them, and this migration only ever added optional FK columns, never a
    # required dependency on them, so removing rows here is unnecessary and risks
    # dropping a tenant's own customizations.
    for table_name, column_name, fk_name in reversed(_REFERENCE_COLUMNS):
        op.drop_constraint(fk_name, table_name, type_="foreignkey")
        op.drop_index(op.f(f"ix_{table_name}_{column_name}"), table_name=table_name)
        op.drop_column(table_name, column_name)


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
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("normalized_name", sa.String()),
        sa.column("metadata", sa.JSON()),
        sa.column("sort_order", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
    )

    rows = []
    for tenant_id in tenant_ids:
        tenant_uuid = tenant_id if isinstance(tenant_id, uuid.UUID) else uuid.UUID(str(tenant_id))
        for catalog_type, templates in CATALOG_SEED_TEMPLATES_V2.items():
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

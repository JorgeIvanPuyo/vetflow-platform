# Single source of truth for what a "default" service/catalog item looks like today.
# New tenants get these via TenantProvisioningService, and RF-05's restore-defaults
# flow (CatalogItemService.restore_defaults / ServiceCatalogService.restore_defaults)
# re-applies them to existing tenants without overwriting local customizations.
#
# Historical alembic seed migrations (0026, 0027, 0030, 0032) keep their own frozen
# copies of these same values on purpose: a migration must never depend on
# application code that can keep evolving after it has already shipped.

DEFAULT_SERVICE_TEMPLATES = (
    {
        "code": "CONSULTA",
        "name": "Consulta general",
        "description": "Atencion clinica general",
        "kind": "consultation",
        "default_duration_minutes": 30,
        "calendar_color": "#2563eb",
        "is_bookable": True,
        "sort_order": 10,
    },
    {
        "code": "SEGUIMIENTO",
        "name": "Seguimiento",
        "description": "Control posterior a consulta o tratamiento",
        "kind": "follow_up",
        "default_duration_minutes": 30,
        "calendar_color": "#0891b2",
        "is_bookable": True,
        "sort_order": 20,
    },
    {
        "code": "VACUNA",
        "name": "Vacunacion",
        "description": "Aplicacion de vacunas",
        "kind": "vaccine",
        "default_duration_minutes": 20,
        "calendar_color": "#16a34a",
        "is_bookable": True,
        "sort_order": 30,
    },
    {
        "code": "DESPARASITACION",
        "name": "Desparasitacion",
        "description": "Control y aplicacion antiparasitaria",
        "kind": "deworming",
        "default_duration_minutes": 20,
        "calendar_color": "#ca8a04",
        "is_bookable": True,
        "sort_order": 40,
    },
    {
        "code": "EXAMEN",
        "name": "Examen",
        "description": "Toma o revision de examenes",
        "kind": "exam",
        "default_duration_minutes": 30,
        "calendar_color": "#9333ea",
        "is_bookable": True,
        "sort_order": 50,
    },
)

DEFAULT_CATALOG_ITEM_TEMPLATES: dict[str, tuple[dict[str, object], ...]] = {
    "mucous_membrane": (
        {"name": "Rosas", "sort_order": 10},
        {"name": "Rosas pálidas", "sort_order": 20},
        {"name": "Pálidas", "sort_order": 30},
        {"name": "Congestionadas", "sort_order": 40},
        {"name": "Cianóticas", "sort_order": 50},
        {"name": "Ictéricas", "sort_order": 60},
    ),
    "hydration": (
        {"name": "Normal", "sort_order": 10},
        {"name": "Leve deshidratación", "sort_order": 20},
        {"name": "Moderada", "sort_order": 30},
        {"name": "Severa", "sort_order": 40},
    ),
    "inventory_category": (
        {"name": "Medicamento", "code": "medication", "sort_order": 10},
        {"name": "Vacuna", "code": "vaccine", "sort_order": 20},
        {"name": "Insumo", "code": "supply", "sort_order": 30},
        {"name": "Alimento", "code": "food", "sort_order": 40},
        {"name": "Otro", "code": "other", "sort_order": 50},
    ),
    "document_type": (
        {"name": "Laboratorio", "code": "laboratory", "sort_order": 10},
        {"name": "Radiografía", "code": "radiography", "sort_order": 20},
        {"name": "Ecografía", "code": "ultrasound", "sort_order": 30},
        {"name": "Foto clínica", "code": "clinical_photo", "sort_order": 40},
        {"name": "Documento", "code": "document", "sort_order": 50},
        {"name": "Otro", "code": "other", "sort_order": 60},
    ),
    "exam_type": (
        {"name": "Hemograma completo", "sort_order": 10},
        {"name": "Perfil bioquímico", "sort_order": 20},
        {"name": "Urianálisis", "sort_order": 30},
        {"name": "Coproparasitológico", "sort_order": 40},
        {"name": "Radiografía", "sort_order": 50},
        {"name": "Ecografía abdominal", "sort_order": 60},
    ),
    "preventive_care_type": (
        {"name": "Vacuna antirrábica", "sort_order": 10},
        {"name": "Vacuna polivalente", "sort_order": 20},
        {"name": "Desparasitación interna", "sort_order": 30},
        {"name": "Desparasitación externa", "sort_order": 40},
        {"name": "Control antipulgas y garrapatas", "sort_order": 50},
    ),
    "follow_up_template": (
        {"name": "Control posterior a consulta", "sort_order": 10},
        {"name": "Recordatorio de vacunación", "sort_order": 20},
        {"name": "Recordatorio de desparasitación", "sort_order": 30},
        {"name": "Revisión de resultado de examen", "sort_order": 40},
        {"name": "Seguimiento general", "sort_order": 50},
    ),
    # breed and prescription_template start empty: they are clinic- and
    # region-specific, so there is no sensible platform-wide default to restore.
    "species": (
        {"name": "Canino", "sort_order": 10},
        {"name": "Felino", "sort_order": 20},
        {"name": "Otro", "sort_order": 30},
    ),
    "diagnostic_tag": (
        {"name": "Respiratorio", "sort_order": 10},
        {"name": "Digestivo", "sort_order": 20},
        {"name": "Dermatológico", "sort_order": 30},
        {"name": "Musculoesquelético", "sort_order": 40},
        {"name": "Renal", "sort_order": 50},
        {"name": "Agudo", "sort_order": 60},
        {"name": "Crónico", "sort_order": 70},
    ),
}

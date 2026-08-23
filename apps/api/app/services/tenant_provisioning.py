import uuid

from sqlalchemy.orm import Session

from app.models.catalog_item import CatalogItem
from app.models.service import Service
from app.models.tenant import Tenant
from app.models.tenant_preference import TenantPreference
from app.repositories.catalog_item import CatalogItemRepository
from app.repositories.clinic import ClinicRepository
from app.repositories.service import ServiceRepository
from app.schemas.admin_users import CreateTenantRequest
from app.services.clinic import DEFAULT_DURATION_OPTIONS
from app.services.normalization import normalize_name

# New tenants get the same defaults every existing tenant already sees today
# (ClinicService.get_preferences' lazy default, and the SERVICE_TEMPLATES_V1 /
# CATALOG_SEED_TEMPLATES_V1 seeded by alembic/versions/0026 and 0027). This is a
# deliberate separate copy: those migrations are frozen historical snapshots and
# must not import from application code that can keep evolving.
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

DEFAULT_CATALOG_ITEM_TEMPLATES = {
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
    # These mirror alembic/versions/0030_operational_catalog_references.py's
    # CATALOG_SEED_TEMPLATES_V2 (a frozen historical snapshot for existing tenants);
    # this copy is what new tenants get going forward and can evolve independently.
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
}


class TenantProvisioningService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.clinic_repository = ClinicRepository(db)
        self.service_repository = ServiceRepository(db)
        self.catalog_item_repository = CatalogItemRepository(db)

    def create_tenant(self, payload: CreateTenantRequest) -> Tenant:
        tenant = Tenant(id=uuid.uuid4(), name=payload.name)
        self.db.add(tenant)
        self.db.flush()

        self.clinic_repository.create_preferences(
            TenantPreference(
                tenant_id=tenant.id,
                currency_code="USD",
                locale="es-PA",
                default_appointment_duration_minutes=30,
                appointment_duration_options=DEFAULT_DURATION_OPTIONS,
                catalog_template_version="regional-v1",
            )
        )

        for template in DEFAULT_SERVICE_TEMPLATES:
            self.service_repository.create(
                Service(
                    tenant_id=tenant.id,
                    normalized_name=normalize_name(template["name"]),
                    **template,
                )
            )

        for catalog_type, templates in DEFAULT_CATALOG_ITEM_TEMPLATES.items():
            for template in templates:
                self.catalog_item_repository.create(
                    CatalogItem(
                        tenant_id=tenant.id,
                        catalog_type=catalog_type,
                        normalized_name=normalize_name(template["name"]),
                        **template,
                    )
                )

        self.db.commit()
        self.db.refresh(tenant)
        return tenant

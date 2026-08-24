import secrets
import uuid

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.firebase import (
    FirebaseUserProvisioningError,
    create_firebase_user,
    generate_password_reset_link,
)
from app.models.catalog_item import CatalogItem
from app.models.service import Service
from app.models.tenant import Tenant
from app.models.tenant_preference import TenantPreference
from app.models.user import User
from app.repositories.catalog_item import CatalogItemRepository
from app.repositories.clinic import ClinicRepository
from app.repositories.service import ServiceRepository
from app.repositories.user import UserRepository
from app.schemas.admin_users import CreateTenantRequest
from app.services.catalog_defaults import (
    DEFAULT_CATALOG_ITEM_TEMPLATES,
    DEFAULT_SERVICE_TEMPLATES,
)
from app.services.clinic import DEFAULT_DURATION_OPTIONS
from app.services.normalization import normalize_name


class TenantProvisioningService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.clinic_repository = ClinicRepository(db)
        self.service_repository = ServiceRepository(db)
        self.catalog_item_repository = CatalogItemRepository(db)
        self.user_repository = UserRepository(db)

    def create_tenant(
        self,
        payload: CreateTenantRequest,
    ) -> tuple[Tenant, dict, str | None]:
        if self.user_repository.get_by_email(payload.admin_email) is not None:
            raise AppError(
                409,
                "user_already_exists",
                "Ya existe un usuario con ese correo",
            )

        # Provision the Firebase account before touching the database: if this fails,
        # no tenant should end up partially provisioned (RF-07).
        temporary_password = secrets.token_urlsafe(16)
        try:
            create_firebase_user(
                email=payload.admin_email,
                display_name=payload.admin_full_name,
                password=temporary_password,
            )
        except FirebaseUserProvisioningError as exc:
            raise AppError(
                502,
                "firebase_user_create_failed",
                "No se pudo crear la cuenta de acceso",
            ) from exc

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

        admin_user = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email=payload.admin_email,
            full_name=payload.admin_full_name,
            role="clinic_admin",
            is_active=True,
        )
        self.db.add(admin_user)

        self.db.commit()
        self.db.refresh(tenant)
        self.db.refresh(admin_user)

        reset_link: str | None = None
        try:
            reset_link = generate_password_reset_link(payload.admin_email)
        except FirebaseUserProvisioningError:
            reset_link = None

        admin_user_response = {
            "id": admin_user.id,
            "full_name": admin_user.full_name,
            "email": admin_user.email,
            "role": admin_user.role,
            "is_active": admin_user.is_active,
            "tenant_id": admin_user.tenant_id,
            "tenant_name": tenant.display_name or tenant.name,
            "created_at": admin_user.created_at,
            "updated_at": admin_user.updated_at,
        }
        return tenant, admin_user_response, reset_link

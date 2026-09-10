import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.inventory_item import InventoryItem
from app.models.purchase import Purchase
from app.models.sale import Sale
from app.models.tenant_preference import TenantPreference
from app.models.tenant import Tenant


class ClinicRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_profile(self, tenant_id: uuid.UUID) -> Tenant | None:
        return self.db.get(Tenant, tenant_id)

    def update_profile(self, tenant: Tenant, updates: dict) -> Tenant:
        for field, value in updates.items():
            setattr(tenant, field, value)

        self.db.add(tenant)
        self.db.flush()
        self.db.refresh(tenant)
        return tenant

    def get_preferences(self, tenant_id: uuid.UUID) -> TenantPreference | None:
        return self.db.query(TenantPreference).filter(
            TenantPreference.tenant_id == tenant_id
        ).one_or_none()

    def create_preferences(self, preferences: TenantPreference) -> TenantPreference:
        self.db.add(preferences)
        self.db.flush()
        self.db.refresh(preferences)
        return preferences

    def has_monetary_activity(self, tenant_id: uuid.UUID) -> bool:
        if (
            self.db.query(Purchase.id)
            .filter(Purchase.tenant_id == tenant_id)
            .first()
            is not None
        ):
            return True
        if (
            self.db.query(Sale.id)
            .filter(Sale.tenant_id == tenant_id)
            .first()
            is not None
        ):
            return True
        return (
            self.db.query(InventoryItem.id)
            .filter(
                InventoryItem.tenant_id == tenant_id,
                or_(
                    InventoryItem.purchase_price_ars.is_not(None),
                    InventoryItem.sale_price_ars.is_not(None),
                ),
            )
            .first()
            is not None
        )

    def update_preferences(
        self,
        preferences: TenantPreference,
        updates: dict,
    ) -> TenantPreference:
        for field, value in updates.items():
            setattr(preferences, field, value)

        self.db.add(preferences)
        self.db.flush()
        self.db.refresh(preferences)
        return preferences

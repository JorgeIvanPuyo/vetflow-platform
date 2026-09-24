from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.inventory_item import InventoryItem
from app.repositories.inventory import InventoryRepository
from app.schemas.inventory import (
    InventoryBulkOperationListItemRead,
    InventoryDashboardAlertRead,
    InventoryDashboardAttentionItemRead,
    InventoryDashboardRead,
    InventoryImportListItemRead,
    InventoryMovementRead,
)


DASHBOARD_DEFAULT_DAYS = 30
DASHBOARD_MAX_DAYS = 365
DASHBOARD_ATTENTION_LIMIT = 10
DASHBOARD_RECENT_MOVEMENT_LIMIT = 10
DASHBOARD_RECENT_ACTIVITY_LIMIT = 5
MONEY_QUANTUM = Decimal("0.01")
DASHBOARD_DISCLAIMER = (
    "Estimación operativa basada en existencias actuales. No reemplaza información contable."
)
ALERT_LABELS = {
    "negative_stock": "Stock negativo",
    "out_of_stock": "Agotados",
    "low_stock": "Stock bajo",
    "inactive_with_stock": "Inactivos con stock",
    "missing_purchase_cost": "Sin costo de compra",
    "missing_sale_price": "Sin precio de venta",
    "missing_brand": "Sin marca",
    "missing_supplier": "Sin proveedor",
}
ALERT_PRIORITIES = {
    "negative_stock": "critical",
    "out_of_stock": "high",
    "missing_purchase_cost": "high",
    "missing_sale_price": "high",
    "low_stock": "medium",
    "inactive_with_stock": "medium",
    "missing_brand": "info",
    "missing_supplier": "info",
}
PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "info": 3}


class InventoryDashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.inventory_repository = InventoryRepository(db)

    def get_dashboard(
        self,
        tenant_id: uuid.UUID,
        *,
        category: str | None,
        brand: str | None,
        supplier: str | None,
        is_active: bool | None,
        date_from: date | None,
        date_to: date | None,
    ) -> InventoryDashboardRead:
        normalized_brand = self._normalize_optional_string(brand)
        normalized_supplier = self._normalize_optional_string(supplier)
        start_date, end_date, start_dt, end_dt = self._resolve_date_range(date_from, date_to)

        catalog_metrics = self.inventory_repository.get_dashboard_catalog_metrics(
            tenant_id,
            category=category,
            brand=normalized_brand,
            supplier=normalized_supplier,
            is_active=is_active,
        )
        movement_metrics = self.inventory_repository.get_dashboard_movement_metrics(
            tenant_id,
            date_from=start_dt,
            date_to=end_dt,
        )
        attention_items = self.inventory_repository.list_dashboard_attention_items(
            tenant_id,
            category=category,
            brand=normalized_brand,
            supplier=normalized_supplier,
            is_active=is_active,
            limit=DASHBOARD_ATTENTION_LIMIT,
        )
        recent_movements = self.inventory_repository.list_dashboard_recent_movements(
            tenant_id,
            date_from=start_dt,
            date_to=end_dt,
            limit=DASHBOARD_RECENT_MOVEMENT_LIMIT,
        )
        recent_imports = self.inventory_repository.list_dashboard_recent_imports(
            tenant_id,
            date_from=start_dt,
            date_to=end_dt,
            limit=DASHBOARD_RECENT_ACTIVITY_LIMIT,
        )
        recent_bulk_operations = self.inventory_repository.list_dashboard_recent_bulk_operations(
            tenant_id,
            date_from=start_dt,
            date_to=end_dt,
            limit=DASHBOARD_RECENT_ACTIVITY_LIMIT,
        )

        return InventoryDashboardRead(
            generated_at=datetime.now(UTC),
            filters={
                "category": category,
                "brand": normalized_brand,
                "supplier": normalized_supplier,
                "is_active": is_active,
                "date_from": start_date,
                "date_to": end_date,
            },
            indicators={
                "total_products": int(catalog_metrics["total_products"] or 0),
                "active_products": int(catalog_metrics["active_products"] or 0),
                "inactive_products": int(catalog_metrics["inactive_products"] or 0),
                "in_stock_products": int(catalog_metrics["in_stock_products"] or 0),
                "low_stock_products": int(catalog_metrics["low_stock_products"] or 0),
                "out_of_stock_products": int(catalog_metrics["out_of_stock_products"] or 0),
                "negative_stock_products": int(catalog_metrics["negative_stock_products"] or 0),
            },
            valuation={
                "estimated_cost_value_ars": self._money(catalog_metrics["estimated_cost_value_ars"]),
                "estimated_sale_value_ars": self._money(catalog_metrics["estimated_sale_value_ars"]),
                "includes_negative_stock": True,
                "disclaimer": DASHBOARD_DISCLAIMER,
            },
            movement_metrics={
                "total_movements": int(movement_metrics["total_movements"] or 0),
                "entry_movements": int(movement_metrics["entry_movements"] or 0),
                "exit_movements": int(movement_metrics["exit_movements"] or 0),
                "adjustment_movements": int(movement_metrics["adjustment_movements"] or 0),
                "reversal_movements": int(movement_metrics["reversal_movements"] or 0),
                "clinical_consumption_movements": int(
                    movement_metrics["clinical_consumption_movements"] or 0
                ),
            },
            alerts=self._build_alerts(catalog_metrics),
            attention_items=[
                InventoryDashboardAttentionItemRead(
                    id=item.id,
                    internal_code=item.internal_code,
                    name=item.name,
                    category=item.category,
                    current_stock=item.current_stock,
                    minimum_stock=item.minimum_stock,
                    sale_price_ars=item.sale_price_ars,
                    alerts=self._item_alerts(item),
                    priority=self._item_priority(item),
                )
                for item in attention_items
            ],
            activity={
                "recent_movements": [
                    InventoryMovementRead.model_validate(movement) for movement in recent_movements
                ],
                "recent_imports": [
                    InventoryImportListItemRead.model_validate(inventory_import)
                    for inventory_import in recent_imports
                ],
                "recent_bulk_operations": [
                    InventoryBulkOperationListItemRead.model_validate(operation)
                    for operation in recent_bulk_operations
                ],
            },
        )

    def _resolve_date_range(
        self,
        date_from: date | None,
        date_to: date | None,
    ) -> tuple[date, date, datetime, datetime]:
        end_date = date_to or datetime.now(UTC).date()
        start_date = date_from or (end_date - timedelta(days=DASHBOARD_DEFAULT_DAYS))
        if start_date > end_date:
            raise AppError(422, "invalid_date_range", "date_from cannot be after date_to")
        if (end_date - start_date).days > DASHBOARD_MAX_DAYS:
            raise AppError(422, "date_range_too_large", "Dashboard date range cannot exceed 365 days")
        return (
            start_date,
            end_date,
            datetime.combine(start_date, time.min),
            datetime.combine(end_date, time.max),
        )

    def _build_alerts(self, metrics: dict) -> list[InventoryDashboardAlertRead]:
        alerts = [
            self._alert("negative_stock", metrics["negative_stock_products"]),
            self._alert("out_of_stock", metrics["out_of_stock_products"]),
            self._alert("low_stock", metrics["low_stock_products"]),
            self._alert("inactive_with_stock", metrics["inactive_with_stock_products"]),
            self._alert("missing_purchase_cost", metrics["missing_purchase_cost_products"]),
            self._alert("missing_sale_price", metrics["missing_sale_price_products"]),
            self._alert("missing_brand", metrics["missing_brand_products"]),
            self._alert("missing_supplier", metrics["missing_supplier_products"]),
        ]
        return sorted(
            alerts,
            key=lambda alert: (PRIORITY_ORDER[alert.priority], alert.alert_type),
        )

    def _alert(self, alert_type: str, count: int) -> InventoryDashboardAlertRead:
        return InventoryDashboardAlertRead(
            alert_type=alert_type,
            priority=ALERT_PRIORITIES[alert_type],
            count=int(count or 0),
            label=ALERT_LABELS[alert_type],
        )

    def _item_alerts(self, item: InventoryItem) -> list[str]:
        alerts: list[str] = []
        if item.current_stock < 0:
            alerts.append("negative_stock")
        if item.current_stock == 0:
            alerts.append("out_of_stock")
        if item.current_stock > 0 and item.current_stock <= item.minimum_stock:
            alerts.append("low_stock")
        if not item.is_active and item.current_stock != 0:
            alerts.append("inactive_with_stock")
        if item.is_active and item.purchase_price_ars is None:
            alerts.append("missing_purchase_cost")
        if item.is_active and item.sale_price_ars is None:
            alerts.append("missing_sale_price")
        if not item.brand or not item.brand.strip():
            alerts.append("missing_brand")
        if not item.supplier or not item.supplier.strip():
            alerts.append("missing_supplier")
        return alerts

    def _item_priority(self, item: InventoryItem) -> str:
        alerts = self._item_alerts(item)
        return min((ALERT_PRIORITIES[alert] for alert in alerts), key=lambda priority: PRIORITY_ORDER[priority])

    def _money(self, value) -> Decimal:
        return Decimal(str(value or 0)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)

    def _normalize_optional_string(self, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

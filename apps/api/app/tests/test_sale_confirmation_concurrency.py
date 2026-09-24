import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier

import pytest
from sqlalchemy import delete, func, select

from app.core.errors import AppError
from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.sale import Sale, SaleItem
from app.models.tenant import Tenant
from app.services.sale import SaleService


def _sale(tenant_id: uuid.UUID, item: InventoryItem, quantity: Decimal) -> Sale:
    sale = Sale(
        tenant_id=tenant_id,
        sale_date=date(2026, 8, 9),
        currency="ARS",
        subtotal_ars=quantity * Decimal("10"),
        discount_total_ars=Decimal("0"),
        total_ars=quantity * Decimal("10"),
        status="draft",
    )
    sale.items.append(
        SaleItem(
            tenant_id=tenant_id,
            line_type="product",
            inventory_item_id=item.id,
            service_id=None,
            description_snapshot=item.name,
            internal_code_snapshot=item.internal_code,
            unit_snapshot=item.unit,
            quantity=quantity,
            unit_price_ars=Decimal("10"),
            discount_percentage=Decimal("0"),
            line_subtotal_ars=quantity * Decimal("10"),
            line_discount_ars=Decimal("0"),
            line_total_ars=quantity * Decimal("10"),
            line_order=1,
        )
    )
    return sale


def _confirm_concurrently(
    session_factory,
    tenant_id: uuid.UUID,
    sale_ids: list[uuid.UUID],
):
    barrier = Barrier(len(sale_ids))

    def confirm(sale_id: uuid.UUID):
        session = session_factory()
        try:
            barrier.wait(timeout=10)
            result = SaleService(session).confirm(
                tenant_id, sale_id, confirmed_by_user_id=None
            )
            return result.status, None
        except AppError as exc:
            return None, exc.code
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=len(sale_ids)) as executor:
        return list(executor.map(confirm, sale_ids))


def test_postgresql_locks_prevent_overselling_and_duplicate_confirmation(
    postgres_test_session_factory,
):
    SessionLocal = postgres_test_session_factory
    setup = SessionLocal()
    tenant = Tenant(id=uuid.uuid4(), name=f"Concurrency {uuid.uuid4()}")
    first_item = InventoryItem(
        tenant_id=tenant.id,
        internal_code=f"CON-{uuid.uuid4().hex[:8]}",
        name="Stock limitado",
        category="supply",
        unit="unit",
        current_stock=Decimal("5"),
        minimum_stock=Decimal("0"),
        purchase_tax_rate_percentage=Decimal("21"),
        profit_margin_percentage=Decimal("35"),
        sale_price_ars=Decimal("10"),
        sale_tax_rate_percentage=Decimal("0"),
        is_active=True,
    )
    duplicate_item = InventoryItem(
        tenant_id=tenant.id,
        internal_code=f"DUP-{uuid.uuid4().hex[:8]}",
        name="Confirmación única",
        category="supply",
        unit="unit",
        current_stock=Decimal("4"),
        minimum_stock=Decimal("0"),
        purchase_tax_rate_percentage=Decimal("21"),
        profit_margin_percentage=Decimal("35"),
        sale_price_ars=Decimal("10"),
        sale_tax_rate_percentage=Decimal("0"),
        is_active=True,
    )
    setup.add_all([tenant, first_item, duplicate_item])
    setup.flush()
    competing_sales = [
        _sale(tenant.id, first_item, Decimal("4")),
        _sale(tenant.id, first_item, Decimal("4")),
    ]
    single_sale = _sale(tenant.id, duplicate_item, Decimal("2"))
    setup.add_all([*competing_sales, single_sale])
    setup.commit()
    tenant_id = tenant.id
    first_item_id = first_item.id
    duplicate_item_id = duplicate_item.id
    competing_ids = [sale.id for sale in competing_sales]
    single_sale_id = single_sale.id
    setup.close()

    try:
        competing_results = _confirm_concurrently(
            SessionLocal, tenant_id, competing_ids
        )
        duplicate_results = _confirm_concurrently(
            SessionLocal, tenant_id, [single_sale_id, single_sale_id]
        )

        check = SessionLocal()
        assert set(competing_results) == {
            (None, "sale_insufficient_stock"),
            ("confirmed", None),
        }
        assert set(duplicate_results) == {
            (None, "sale_not_editable"),
            ("confirmed", None),
        }
        assert check.get(InventoryItem, first_item_id).current_stock == Decimal("1")
        assert check.get(InventoryItem, duplicate_item_id).current_stock == Decimal("2")
        assert check.scalar(
            select(func.count()).select_from(InventoryMovement).where(
                InventoryMovement.tenant_id == tenant_id,
                InventoryMovement.movement_type == "sale",
                InventoryMovement.inventory_item_id == first_item_id,
            )
        ) == 1
        assert check.scalar(
            select(func.count()).select_from(InventoryMovement).where(
                InventoryMovement.tenant_id == tenant_id,
                InventoryMovement.movement_type == "sale",
                InventoryMovement.inventory_item_id == duplicate_item_id,
            )
        ) == 1
        assert sorted(
            check.scalars(
                select(Sale.status).where(Sale.id.in_(competing_ids))
            ).all()
        ) == ["confirmed", "draft"]
        check.close()
    finally:
        cleanup = SessionLocal()
        cleanup.execute(
            delete(InventoryMovement).where(InventoryMovement.tenant_id == tenant_id)
        )
        cleanup.execute(delete(SaleItem).where(SaleItem.tenant_id == tenant_id))
        cleanup.execute(delete(Sale).where(Sale.tenant_id == tenant_id))
        cleanup.execute(
            delete(InventoryItem).where(InventoryItem.tenant_id == tenant_id)
        )
        cleanup.execute(delete(Tenant).where(Tenant.id == tenant_id))
        cleanup.commit()
        cleanup.close()

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import DataError

from app.core.errors import AppError
from app.core.sale_limits import INVENTORY_MONEY_MAX, SALE_PRICE_MAX, SALE_QUANTITY_MAX, SALE_TOTAL_MAX
from app.models.inventory_item import InventoryItem
from app.models.inventory_movement import InventoryMovement
from app.models.payment import PaymentMethod, SalePayment
from app.models.sale import Sale, SaleItem
from app.models.tenant import Tenant
from app.models.tenant_preference import TenantPreference
from app.schemas.payment import SalePaymentCreate
from app.schemas.sale import SaleCreate, SaleProductItemInput, SaleServiceItemInput
from app.services.payment import SalePaymentService
from app.services.sale import SaleService


def _line(kind="service", **overrides):
    values = {"line_type": kind, "quantity": "1", "unit_price_ars": "1.00", "discount_percentage": "0"}
    values.update({"inventory_item_id": str(uuid.uuid4())} if kind == "product" else {"description": "Servicio"})
    return {**values, **overrides}


def _payload(lines):
    return {"sale_date": "2026-10-01", "items": lines}


def _headers(tenant):
    return {"X-Tenant-Id": str(tenant.id)}


def _inventory(db, tenant, *, price=Decimal("1.00"), stock=Decimal("2")):
    item = InventoryItem(
        tenant_id=tenant.id, internal_code=f"P2-{uuid.uuid4().hex[:10]}", name="Producto P.2",
        category="supply", unit="unit", current_stock=stock, minimum_stock=Decimal("0"),
        purchase_tax_rate_percentage=Decimal("0"), profit_margin_percentage=Decimal("0"),
        sale_tax_rate_percentage=Decimal("0"), sale_price_ars=price, is_active=True,
    )
    db.add(item)
    db.commit()
    return item


@pytest.mark.parametrize("kind,maximum", [("service", SALE_PRICE_MAX), ("product", INVENTORY_MONEY_MAX)])
@pytest.mark.parametrize("value", ["0", "0.01", "0.05", "maximum"])
def test_price_accepts_zero_cents_and_exact_maximum(kind, maximum, value):
    schema = SaleProductItemInput if kind == "product" else SaleServiceItemInput
    price = maximum if value == "maximum" else Decimal(value)
    assert schema.model_validate(_line(kind, unit_price_ars=str(price))).unit_price_ars == price


@pytest.mark.parametrize("kind", ["service", "product"])
@pytest.mark.parametrize("field,value", [
    ("unit_price_ars", "0.001"), ("unit_price_ars", "-0.01"),
    ("unit_price_ars", "1000000000000"), ("unit_price_ars", "1e100"),
    ("unit_price_ars", "NaN"), ("unit_price_ars", "Infinity"),
    ("discount_percentage", "10.555"), ("discount_percentage", "100.01"),
    ("discount_percentage", "-0.01"), ("quantity", "0"),
    ("quantity", "1.5"), ("quantity", "10000000000"),
])
def test_create_and_item_update_reject_unpersistible_inputs(client, tenant, kind, field, value):
    # Schema rejection occurs before resolving the deliberately unknown product ID.
    line = _line(kind, **{field: value})
    created = client.post("/api/v1/sales", headers=_headers(tenant), json=_payload([line]))
    assert created.status_code == 422, created.text
    valid = client.post("/api/v1/sales", headers=_headers(tenant), json=_payload([_line()]))
    assert valid.status_code == 201, valid.text
    sale_id = valid.json()["data"]["id"]
    updated = client.patch(f"/api/v1/sales/{sale_id}", headers=_headers(tenant), json={"items": [line]})
    assert updated.status_code == 422, updated.text
    detail = client.get(f"/api/v1/sales/{sale_id}", headers=_headers(tenant)).json()["data"]
    assert detail["total_ars"] == "1.00"


@pytest.mark.parametrize("discount", ["0", "10", "10.5", "10.55", "100"])
@pytest.mark.parametrize("kind", ["service", "product"])
def test_discount_fraction_and_integer_quantity_limits(kind, discount):
    schema = SaleProductItemInput if kind == "product" else SaleServiceItemInput
    line = schema.model_validate(_line(kind, discount_percentage=discount, quantity=str(SALE_QUANTITY_MAX)))
    assert line.discount_percentage == Decimal(discount)
    assert line.quantity == SALE_QUANTITY_MAX


@pytest.mark.parametrize("amount", ["0.01", "12.34", str(SALE_TOTAL_MAX)])
def test_payment_amount_valid_boundaries(amount):
    payment = SalePaymentCreate(payment_method_id=uuid.uuid4(), amount_ars=amount, received_at=datetime.now(UTC))
    assert payment.amount_ars == Decimal(amount)


@pytest.mark.parametrize("amount", ["0", "-0.01", "0.001", "12.345", "100000000000000", "1e100", "NaN", "Infinity"])
def test_payment_amount_rejects_scale_and_overflow(amount):
    with pytest.raises(ValidationError):
        SalePaymentCreate(payment_method_id=uuid.uuid4(), amount_ars=amount, received_at=datetime.now(UTC))


@pytest.mark.parametrize("quantity,price,discount,subtotal,discount_total,total", [
    ("3", "0.05", "10", "0.15", "0.02", "0.13"),
    ("1", "0.01", "50", "0.01", "0.01", "0.00"),
    ("1", "0.05", "10", "0.05", "0.01", "0.04"),
    ("1", "1.00", "10.5", "1.00", "0.11", "0.89"),
    ("3", "0.07", "2.38", "0.21", "0.00", "0.21"),
    ("3", "0.07", "2.39", "0.21", "0.01", "0.20"),
])
def test_round_half_up_is_applied_per_line(client, tenant, quantity, price, discount, subtotal, discount_total, total):
    response = client.post("/api/v1/sales", headers=_headers(tenant), json=_payload([
        _line(quantity=quantity, unit_price_ars=price, discount_percentage=discount),
    ]))
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert (data["subtotal_ars"], data["discount_total_ars"], data["total_ars"]) == (subtotal, discount_total, total)
    line = data["items"][0]
    assert (line["line_subtotal_ars"], line["line_discount_ars"], line["line_total_ars"]) == (subtotal, discount_total, total)


@pytest.mark.parametrize("lines", [
    [_line(quantity="101", unit_price_ars=str(SALE_PRICE_MAX))],
    [_line(quantity="101", unit_price_ars=str(SALE_PRICE_MAX), discount_percentage="100")],
    [_line(quantity="60", unit_price_ars=str(SALE_PRICE_MAX))] * 2,
    [_line(quantity="60", unit_price_ars=str(SALE_PRICE_MAX), discount_percentage="100")] * 2,
])
def test_computed_line_and_sale_overflows_are_rejected_before_persistence(client, db_session, tenant, lines):
    response = client.post("/api/v1/sales", headers=_headers(tenant), json=_payload(lines))
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "sale_amount_out_of_range"
    assert db_session.scalar(select(func.count(Sale.id)).where(Sale.tenant_id == tenant.id)) == 0


def test_exact_sale_total_limit_is_calculated_without_float_conversion(db_session, tenant):
    payload = SaleCreate.model_validate(_payload([
        _line(quantity="100", unit_price_ars=str(SALE_PRICE_MAX)), _line(unit_price_ars="0.99"),
    ]))
    _, totals = SaleService(db_session)._build_items(tenant.id, payload.items)
    assert totals == {"subtotal_ars": SALE_TOTAL_MAX, "discount_total_ars": Decimal("0.00"), "total_ars": SALE_TOTAL_MAX}


@pytest.mark.parametrize("default_price", [False, True])
def test_product_at_inventory_money_limit_confirms_safely(client, db_session, tenant, default_price):
    item = _inventory(db_session, tenant, price=INVENTORY_MONEY_MAX)
    line = _line("product", inventory_item_id=str(item.id), unit_price_ars=None if default_price else str(INVENTORY_MONEY_MAX))
    response = client.post("/api/v1/sales", headers=_headers(tenant), json=_payload([line]))
    assert response.status_code == 201, response.text
    sale_id = response.json()["data"]["id"]
    confirmed = client.post(f"/api/v1/sales/{sale_id}/confirm", headers=_headers(tenant), json={"confirm": True})
    assert confirmed.status_code == 200, confirmed.text
    movement = db_session.scalar(select(InventoryMovement).where(InventoryMovement.tenant_id == tenant.id, InventoryMovement.source_id == sale_id))
    assert movement.unit_sale_price_ars == movement.total_sale_price_ars == INVENTORY_MONEY_MAX


@pytest.mark.parametrize("price,quantity,discount", [
    (str(INVENTORY_MONEY_MAX + Decimal("0.01")), "1", "0"),
    (str(INVENTORY_MONEY_MAX), "2", "0"),
])
def test_product_inventory_overflow_is_rejected_at_draft_creation(client, db_session, tenant, price, quantity, discount):
    item = _inventory(db_session, tenant)
    response = client.post("/api/v1/sales", headers=_headers(tenant), json=_payload([
        _line("product", inventory_item_id=str(item.id), unit_price_ars=price, quantity=quantity, discount_percentage=discount),
    ]))
    assert response.status_code == 422, response.text
    assert db_session.scalar(select(func.count(Sale.id)).where(Sale.tenant_id == tenant.id)) == 0
    assert db_session.scalar(select(func.count(InventoryMovement.id)).where(InventoryMovement.tenant_id == tenant.id)) == 0


def test_product_discounted_gross_can_exceed_inventory_limit_when_net_fits(client, db_session, tenant):
    item = _inventory(db_session, tenant)
    response = client.post("/api/v1/sales", headers=_headers(tenant), json=_payload([
        _line("product", inventory_item_id=str(item.id), unit_price_ars=str(INVENTORY_MONEY_MAX), quantity="2", discount_percentage="50"),
    ]))
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert Decimal(data["subtotal_ars"]) == INVENTORY_MONEY_MAX * 2
    assert Decimal(data["total_ars"]) == INVENTORY_MONEY_MAX
    assert client.post(f"/api/v1/sales/{data['id']}/confirm", headers=_headers(tenant), json={"confirm": True}).status_code == 200


def test_default_catalog_price_is_checked_without_repairing_catalog(client, db_session, tenant):
    # SQLite can retain an overflow that PostgreSQL would reject; simulate bad history.
    bad_price = INVENTORY_MONEY_MAX + Decimal("0.01")
    item = _inventory(db_session, tenant, price=bad_price)
    response = client.post("/api/v1/sales", headers=_headers(tenant), json=_payload([
        _line("product", inventory_item_id=str(item.id), unit_price_ars=None),
    ]))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "sale_amount_out_of_range"
    db_session.refresh(item)
    assert item.sale_price_ars == bad_price


def test_legacy_draft_is_readable_and_not_recalculated_but_cannot_overflow_inventory(client, db_session, tenant):
    item = _inventory(db_session, tenant)
    response = client.post("/api/v1/sales", headers=_headers(tenant), json=_payload([
        _line("product", inventory_item_id=str(item.id)),
    ]))
    assert response.status_code == 201
    sale_id = uuid.UUID(response.json()["data"]["id"])
    sale = db_session.scalar(select(Sale).where(Sale.tenant_id == tenant.id, Sale.id == sale_id))
    line = sale.items[0]
    line.unit_price_ars = line.line_subtotal_ars = line.line_total_ars = INVENTORY_MONEY_MAX + Decimal("0.01")
    sale.subtotal_ars = sale.total_ars = line.line_total_ars
    db_session.commit()
    before = client.get(f"/api/v1/sales/{sale_id}", headers=_headers(tenant)).json()["data"]
    updated = client.patch(f"/api/v1/sales/{sale_id}", headers=_headers(tenant), json={"notes": "Nota"})
    assert updated.status_code == 200
    assert updated.json()["data"]["items"] == before["items"]
    confirmed = client.post(f"/api/v1/sales/{sale_id}/confirm", headers=_headers(tenant), json={"confirm": True})
    assert confirmed.status_code == 422
    after = client.get(f"/api/v1/sales/{sale_id}", headers=_headers(tenant)).json()["data"]
    assert after["status"] == "draft" and after["items"] == before["items"]
    assert after["total_ars"] == before["total_ars"]
    assert db_session.scalar(select(func.count(InventoryMovement.id)).where(InventoryMovement.tenant_id == tenant.id)) == 0


def test_product_limits_keep_tenant_resolution_scoped(client, db_session, tenant, other_tenant):
    foreign = _inventory(db_session, other_tenant, price=INVENTORY_MONEY_MAX)
    response = client.post("/api/v1/sales", headers=_headers(tenant), json=_payload([
        _line("product", inventory_item_id=str(foreign.id), unit_price_ars=None),
    ]))
    assert response.status_code == 404


def test_postgresql_sale_numeric_limits_and_confirmation(postgres_test_session_factory):
    db = postgres_test_session_factory()
    tenant = Tenant(id=uuid.uuid4(), name="P.2 Numeric test")
    db.add(tenant)
    db.commit()
    try:
        # Real Numeric columns must preserve the maximum service price and totals.
        service = SaleService(db)
        sale = service.create(tenant.id, SaleCreate.model_validate(_payload([
            _line(quantity="100", unit_price_ars=str(SALE_PRICE_MAX)), _line(unit_price_ars="0.99"),
        ])), created_by_user_id=None)
        assert sale.items[0].unit_price_ars == SALE_PRICE_MAX
        assert sale.subtotal_ars == sale.total_ars == SALE_TOTAL_MAX
        service.confirm(tenant.id, sale.id, confirmed_by_user_id=None)
        method = PaymentMethod(tenant_id=tenant.id, label="Cash P.2", normalized_label="cash p.2", type="cash", is_active=True, sort_order=0)
        db.add(method)
        db.commit()
        payment_service = SalePaymentService(db)
        payment_service.create(tenant.id, sale.id, SalePaymentCreate(payment_method_id=method.id, amount_ars=SALE_TOTAL_MAX, received_at=datetime.now(UTC)), user_id=None)
        assert payment_service.repository.active_total(tenant.id, sale.id) == SALE_TOTAL_MAX
        assert service.get(tenant.id, sale.id).payment_status == "paid"
        with pytest.raises(AppError, match="supera el saldo"):
            payment_service.create(tenant.id, sale.id, SalePaymentCreate(payment_method_id=method.id, amount_ars=Decimal("0.01"), received_at=datetime.now(UTC)), user_id=None)

        # Product unit/net maximum and maximum whole quantity survive confirmation.
        for price, quantity in ((INVENTORY_MONEY_MAX, Decimal("1")), (Decimal("0.01"), SALE_QUANTITY_MAX)):
            item = _inventory(db, tenant, price=price, stock=quantity)
            product_sale = service.create(tenant.id, SaleCreate.model_validate(_payload([
                _line("product", inventory_item_id=str(item.id), quantity=str(quantity), unit_price_ars=None),
            ])), created_by_user_id=None)
            service.confirm(tenant.id, product_sale.id, confirmed_by_user_id=None)
            movement = db.scalar(select(InventoryMovement).where(InventoryMovement.tenant_id == tenant.id, InventoryMovement.source_id == str(product_sale.id)))
            assert movement.quantity == quantity
            assert movement.unit_sale_price_ars == price
            assert movement.total_sale_price_ars == (price * quantity).quantize(Decimal("0.01"))
            assert movement.stock_after == 0

        # PostgreSQL really overflows at each next cent; API limits avoid these writes.
        for precision, maximum in ((12, INVENTORY_MONEY_MAX), (14, SALE_PRICE_MAX), (16, SALE_TOTAL_MAX)):
            with pytest.raises(DataError):
                with db.begin_nested():
                    db.execute(text(f"SELECT CAST(:amount AS NUMERIC({precision}, 2))"), {"amount": maximum + Decimal("0.01")})
    finally:
        db.rollback()
        for model in (SalePayment, InventoryMovement, SaleItem, Sale, PaymentMethod, InventoryItem, TenantPreference, Tenant):
            column = model.id if model is Tenant else model.tenant_id
            db.execute(delete(model).where(column == tenant.id))
        db.commit()
        db.close()

"""Valid calculated catalog inputs for tests that need a specific sale price."""
from decimal import Decimal

from app.core.inventory_pricing import calculate_catalog_sale_price


def calculated_product_fields(sale_price: str) -> dict:
    price = Decimal(str(sale_price))
    calculated = calculate_catalog_sale_price(
        purchase_price_ars=price,
        purchase_tax_rate_percentage=Decimal("0"),
        profit_margin_percentage=Decimal("0"),
        round_sale_price=False,
        rounding_increment=Decimal("1"),
    )
    assert calculated == price
    return {
        "purchase_price_ars": str(price),
        "purchase_tax_rate_percentage": "0",
        "profit_margin_percentage": "0",
        "round_sale_price": False,
        "sale_price_ars": str(calculated),
    }

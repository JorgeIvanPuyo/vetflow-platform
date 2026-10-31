"""Catalog pricing: purchase tax first, markup, then optional clinic rounding."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal


def calculate_catalog_sale_price(
    *,
    purchase_price_ars: Decimal | None,
    purchase_tax_rate_percentage: Decimal | None,
    profit_margin_percentage: Decimal | None,
    round_sale_price: bool,
    rounding_increment: Decimal,
) -> Decimal | None:
    if purchase_price_ars is None or profit_margin_percentage is None:
        return None
    quantum = Decimal("0.01")
    cost = catalog_cost_with_purchase_tax(purchase_price_ars, purchase_tax_rate_percentage)
    price = (cost * (1 + profit_margin_percentage / 100)).quantize(quantum, rounding=ROUND_HALF_UP)
    if round_sale_price:
        price = (price / rounding_increment).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * rounding_increment
    return price


def catalog_cost_with_purchase_tax(cost: Decimal, tax_rate: Decimal | None) -> Decimal:
    quantum = Decimal("0.01")
    tax = (cost * (tax_rate or Decimal("0")) / 100).quantize(quantum, rounding=ROUND_HALF_UP)
    return (cost + tax).quantize(quantum, rounding=ROUND_HALF_UP)


MONEY_MAX = Decimal("9999999999.99")
MARGIN_QUANTUM = Decimal("0.01")
BULK_MARGIN_MAX = Decimal("1000")


class CatalogPriceTargetError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def resolve_catalog_price_target(
    *,
    target: Decimal,
    purchase_price_ars: Decimal | None,
    purchase_tax_rate_percentage: Decimal | None,
    profit_margin_percentage: Decimal | None,
    round_sale_price: bool,
    rounding_increment: Decimal,
    adjustment: Literal["increase", "decrease"] | None = None,
    current_price: Decimal | None = None,
) -> tuple[Decimal, Decimal]:
    """Resolve exact prices, or the closest rounded result for relative adjustments.

    The direct calculation is monotonic. A nearest theoretical margin, adjacent
    cents and boundary candidates suffice; no enumeration of the margin domain.
    Targets use catalog sale_price_ars (before the separate sale tax stage).
    """
    if purchase_price_ars is None or profit_margin_percentage is None:
        raise CatalogPriceTargetError("catalog_pricing_incomplete")
    if target < 0:
        raise CatalogPriceTargetError("sale_price_would_be_negative")
    if target > MONEY_MAX:
        raise CatalogPriceTargetError("catalog_price_limit")
    kwargs = dict(
        purchase_price_ars=purchase_price_ars,
        purchase_tax_rate_percentage=purchase_tax_rate_percentage,
        round_sale_price=round_sale_price,
        rounding_increment=rounding_increment,
    )
    base = catalog_cost_with_purchase_tax(purchase_price_ars, purchase_tax_rate_percentage)
    if base == 0 and target != 0:
        raise CatalogPriceTargetError("catalog_zero_cost_target")
    theoretical = (target / base - 1) * 100 if base else profit_margin_percentage
    nearest = theoretical.quantize(MARGIN_QUANTUM, rounding=ROUND_HALF_UP)
    # Prefer retaining the configured percentage when it already produces the goal.
    candidates = [profit_margin_percentage, nearest, nearest - MARGIN_QUANTUM,
                  nearest + MARGIN_QUANTUM, Decimal("0"), BULK_MARGIN_MAX]
    results = []
    for margin in dict.fromkeys(candidates):
        if not 0 <= margin <= BULK_MARGIN_MAX or margin != margin.quantize(MARGIN_QUANTUM):
            continue
        result = calculate_catalog_sale_price(**kwargs, profit_margin_percentage=margin)
        if adjustment is None and result == target:
            return margin.quantize(MARGIN_QUANTUM), result
        if result > MONEY_MAX:
            continue
        if adjustment == "increase" and (current_price is None or result < current_price):
            continue
        if adjustment == "decrease" and (current_price is None or result > current_price):
            continue
        results.append((margin, result))
    # Do not turn targets outside the markup domain into arbitrary clamped prices.
    exact_result = any(result == target for _, result in results)
    if theoretical < 0 and not exact_result:
        raise CatalogPriceTargetError("catalog_target_requires_negative_margin")
    if theoretical > BULK_MARGIN_MAX and not exact_result:
        raise CatalogPriceTargetError("catalog_target_margin_out_of_range")
    if adjustment is not None and results:
        margin, result = min(results, key=lambda pair: (
            abs(pair[1] - target), abs(pair[0] - theoretical),
            pair[0] != profit_margin_percentage,
        ))
        return margin.quantize(MARGIN_QUANTUM), result
    if adjustment is not None:
        raise CatalogPriceTargetError("catalog_adjustment_direction")
    raise CatalogPriceTargetError("catalog_target_not_representable")

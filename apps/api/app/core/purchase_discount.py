"""Purchase-only discount; line costs and taxes remain unchanged."""
from decimal import Decimal, ROUND_HALF_UP

from app.core.errors import AppError

MONEY_QUANTUM = Decimal("0.01")
PURCHASE_MONEY_MAX = Decimal("99999999999999.99")


def calculate_purchase_discount(total: Decimal, discount_type: str, value: Decimal) -> Decimal:
    if not total.is_finite() or not value.is_finite() or not 0 <= total <= PURCHASE_MONEY_MAX:
        raise AppError(422, "invalid_purchase_discount", "Los importes de compra deben ser finitos y respetar el límite monetario")
    if value < 0 or value > PURCHASE_MONEY_MAX or value != value.quantize(MONEY_QUANTUM):
        raise AppError(422, "invalid_purchase_discount", "El descuento debe ser mayor o igual a cero y tener hasta dos decimales")
    if discount_type == "none":
        if value != 0:
            raise AppError(422, "invalid_purchase_discount", "Sin descuento requiere un valor cero")
        amount = Decimal("0.00")
    elif discount_type == "percentage":
        if value > 100:
            raise AppError(422, "invalid_purchase_discount", "El porcentaje de descuento debe estar entre 0 y 100")
        amount = (total * value / 100).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    elif discount_type == "amount":
        amount = value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    else:
        raise AppError(422, "invalid_purchase_discount", "Selecciona una modalidad de descuento válida")
    if amount > total:
        raise AppError(422, "purchase_discount_exceeds_total", "El descuento no puede superar el total original de la compra")
    return amount


def purchase_amount_payable(total: Decimal, discount_amount: Decimal) -> Decimal:
    return (total - discount_amount).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)

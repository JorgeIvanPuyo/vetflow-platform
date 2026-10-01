"""Limits for new sale writes with the existing Numeric columns.

Sales: price Numeric(14, 2), totals Numeric(16, 2), quantity Numeric(12, 2).
Inventory movement prices and totals: Numeric(12, 2).
"""

from decimal import Decimal


MONEY_QUANTUM = Decimal("0.01")
SALE_PRICE_MAX = Decimal(10) ** (14 - 2) - MONEY_QUANTUM
SALE_TOTAL_MAX = Decimal(10) ** (16 - 2) - MONEY_QUANTUM
INVENTORY_MONEY_MAX = Decimal(10) ** (12 - 2) - MONEY_QUANTUM
# Sales currently require whole, positive quantities.
SALE_QUANTITY_MAX = Decimal(10) ** (12 - 2) - 1

from sqlalchemy import select

from app.core.errors import AppError
from app.models.fiscal_proposal import FiscalPaymentAllocation


def ensure_no_fiscal_reservations(db, tenant_id, sale_id, payment_id=None):
    """Called only after locking the sale; shares approval's serialization point."""
    query = select(FiscalPaymentAllocation.id).where(FiscalPaymentAllocation.tenant_id == tenant_id, FiscalPaymentAllocation.sale_id == sale_id, FiscalPaymentAllocation.is_active.is_(True))
    if payment_id is not None:
        query = query.where(FiscalPaymentAllocation.payment_id == payment_id)
    if db.scalar(query.limit(1)) is not None:
        code = "fiscal_payment_reserved" if payment_id is not None else "fiscal_sale_reserved"
        raise AppError(409, code, "Hay una imputación fiscal activa. Cancela la propuesta aprobada aún no enviada antes de anular el cobro o revertir la venta; si ya fue enviada requiere conciliación fiscal")

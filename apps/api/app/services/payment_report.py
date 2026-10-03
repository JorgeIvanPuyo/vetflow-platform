import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from math import ceil

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clinic_time import clinic_day_start_utc, clinic_timezone
from app.core.errors import AppError
from app.models.tenant import Tenant
from app.repositories.clinic import ClinicRepository
from app.repositories.payment_report import PaymentReportRepository
from app.schemas.payment_report import PaymentReport
from app.services.regional_settings import resolve_operational_money_settings


class PaymentReportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = PaymentReportRepository(db)

    def read(self, tenant_id: uuid.UUID, *, date_from: date | None, date_to: date | None,
             payment_method_id: uuid.UUID | None, page: int, page_size: int):
        tenant = self.db.scalar(select(Tenant).where(Tenant.id == tenant_id))
        if tenant is None:
            raise AppError(404, "clinic_not_found", "Clinic profile not found")
        zone = clinic_timezone(tenant.timezone)
        today = datetime.now(zone).date()
        date_from, date_to = date_from or today, date_to or today
        if date_from > date_to or date_to == date.max:
            raise AppError(422, "invalid_report_date_range", "El rango de fechas no es válido")
        start = clinic_day_start_utc(date_from, zone, error_code="invalid_report_date_range")
        end = clinic_day_start_utc(date_to + timedelta(days=1), zone, error_code="invalid_report_date_range")
        methods = self.repository.methods(tenant_id)
        method_by_id = {method["payment_method_id"]: method for method in methods}
        if payment_method_id is not None and payment_method_id not in method_by_id:
            raise AppError(404, "payment_method_not_found", "Forma de pago no encontrada")
        groups, rows = self.repository.read(tenant_id, start=start, end=end,
            method_id=payment_method_id, page=page, page_size=page_size)
        count = sum(group["payment_count"] for group in groups)
        money = resolve_operational_money_settings(ClinicRepository(self.db), tenant_id)
        report = PaymentReport.model_validate({
            "date_from": date_from, "date_to": date_to, "timezone": zone.key,
            "currency_code": money.currency_code, "locale": money.locale,
            "methods": methods, "payments": rows,
            "summary": {
                "total_amount_ars": sum((group["amount_ars"] for group in groups), Decimal("0.00")),
                "payment_count": count,
                "by_method": [{**group, "is_active": method_by_id[group["payment_method_id"]]["is_active"]} for group in groups],
            },
        })
        return report, {"page": page, "page_size": page_size, "total": count, "total_pages": ceil(count / page_size)}

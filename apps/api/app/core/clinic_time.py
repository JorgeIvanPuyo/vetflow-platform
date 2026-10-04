from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.errors import AppError


def clinic_timezone(value: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(value or "America/Panama")
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise AppError(422, "invalid_clinic_timezone", "La zona horaria de la clínica no es válida") from exc


def clinic_day_start_utc(day: date, zone: ZoneInfo, *, error_code: str) -> datetime:
    """P.12.2 convention: local midnight converted to an aware UTC instant."""
    try:
        normalized = datetime.combine(day, time.min, tzinfo=zone).astimezone(UTC)
    except (OverflowError, ValueError) as exc:
        raise AppError(422, error_code, "La fecha está fuera del rango admitido") from exc
    if normalized.astimezone(zone).date() != day:
        raise AppError(422, error_code, "Esta fecha no existe en la zona horaria de la clínica")
    return normalized

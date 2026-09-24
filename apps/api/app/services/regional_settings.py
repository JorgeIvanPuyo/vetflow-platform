from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from app.models.tenant_preference import TenantPreference
from app.repositories.clinic import ClinicRepository


@dataclass(frozen=True)
class OperationalMoneySettings:
    currency_code: str
    locale: str
    default_purchase_tax_rate: Decimal
    default_sale_tax_rate: Decimal
    default_profit_margin: Decimal
    money_rounding_increment: Decimal


NEW_TENANT_DEFAULTS = OperationalMoneySettings(
    currency_code="USD",
    locale="es-PA",
    default_purchase_tax_rate=Decimal("0"),
    default_sale_tax_rate=Decimal("0"),
    default_profit_margin=Decimal("35"),
    money_rounding_increment=Decimal("10"),
)

LEGACY_TENANT_DEFAULTS = OperationalMoneySettings(
    currency_code="ARS",
    locale="es-AR",
    default_purchase_tax_rate=Decimal("21"),
    default_sale_tax_rate=Decimal("0"),
    default_profit_margin=Decimal("35"),
    money_rounding_increment=Decimal("10"),
)


def _from_preferences(preferences: TenantPreference) -> OperationalMoneySettings:
    return OperationalMoneySettings(
        currency_code=preferences.currency_code,
        locale=preferences.locale,
        default_purchase_tax_rate=preferences.default_purchase_tax_rate,
        default_sale_tax_rate=preferences.default_sale_tax_rate,
        default_profit_margin=preferences.default_profit_margin,
        money_rounding_increment=preferences.money_rounding_increment,
    )


def resolve_operational_money_settings(
    repository: ClinicRepository,
    tenant_id: uuid.UUID,
) -> OperationalMoneySettings:
    preferences = repository.get_preferences(tenant_id)
    if preferences is not None:
        return _from_preferences(preferences)
    return (
        LEGACY_TENANT_DEFAULTS
        if repository.has_monetary_activity(tenant_id)
        else NEW_TENANT_DEFAULTS
    )


def ensure_operational_money_settings(
    repository: ClinicRepository,
    tenant_id: uuid.UUID,
) -> OperationalMoneySettings:
    preferences = repository.get_preferences(tenant_id)
    if preferences is not None:
        return _from_preferences(preferences)

    # Missing preferences can exist in tests, partial local environments, or a
    # legacy database that has not yet been through 0040. Once an operational
    # write starts, persist the inferred settings in the same transaction so
    # subsequent writes cannot reinterpret the same tenant in another currency.
    defaults = resolve_operational_money_settings(repository, tenant_id)
    preferences = repository.create_preferences(
        TenantPreference(
            tenant_id=tenant_id,
            currency_code=defaults.currency_code,
            locale=defaults.locale,
            default_purchase_tax_rate=defaults.default_purchase_tax_rate,
            default_sale_tax_rate=defaults.default_sale_tax_rate,
            default_profit_margin=defaults.default_profit_margin,
            money_rounding_increment=defaults.money_rounding_increment,
        )
    )
    return _from_preferences(preferences)

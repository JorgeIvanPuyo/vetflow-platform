export type MoneyPreferences = {
  currencyCode: string;
  locale: string;
};

export function formatCurrency(
  value: string | number | null | undefined,
  { currencyCode, locale }: MoneyPreferences,
): string {
  if (value === null || value === undefined || value === "") {
    return `${currencyCode} -`;
  }

  const numericValue = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(numericValue)) {
    return `${currencyCode} -`;
  }

  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: currencyCode,
    currencyDisplay: "code",
    maximumFractionDigits: 2,
  }).format(numericValue);
}

export function formatPercentage(
  value: string | number | null | undefined,
  locale: string,
): string {
  const numericValue = Number(value ?? 0);
  if (Number.isNaN(numericValue)) {
    return "0%";
  }

  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(numericValue)}%`;
}

export type TenantMoneySettings = {
  currency_code: string;
  locale: string;
};

export function resolveMoneyPreferences(
  preferences: TenantMoneySettings | null | undefined,
  currencyOverride?: string | null,
): MoneyPreferences {
  const currencyCode = currencyOverride ?? preferences?.currency_code ?? "ARS";
  const locale =
    preferences && preferences.currency_code === currencyCode
      ? preferences.locale
      : currencyCode === "USD"
        ? "es-PA"
        : "es-AR";
  return { currencyCode, locale };
}

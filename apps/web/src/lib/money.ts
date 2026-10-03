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

/** Format exact cents even near Numeric(16, 2)'s limit, without Number rounding. */
export function formatExactCurrency(value: string, { currencyCode, locale }: MoneyPreferences): string {
  const match = /^(-?)(\d+)(?:[.,](\d{1,2}))?$/.exec(value.trim());
  if (!match) return `${currencyCode} —`;
  const whole = BigInt(match[2]);
  const negative = match[1] === "-";
  const formatter = new Intl.NumberFormat(locale, { style: "currency", currency: currencyCode, currencyDisplay: "code", minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const fraction = new Intl.NumberFormat(locale, { minimumIntegerDigits: 2, useGrouping: false }).format(BigInt((match[3] ?? "").padEnd(2, "0")));
  return formatter.formatToParts(negative ? (whole === BigInt(0) ? -0 : -whole) : whole)
    .map((part) => part.type === "fraction" ? fraction : part.value).join("");
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

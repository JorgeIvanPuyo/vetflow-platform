/** Calendar dates use the clinic's existing IANA timezone, never browser time. */
export function clinicCalendarDate(value: Date | string, timezone: string): string {
  const date = typeof value === "string" ? new Date(value) : value;
  const parts = new Intl.DateTimeFormat("en", { timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(date);
  const part = (name: string) => parts.find((item) => item.type === name)!.value;
  return `${part("year").padStart(4, "0")}-${part("month")}-${part("day")}`;
}

export function startDateLabel(value: string): string {
  const [year, month, day] = value.split("-");
  return `${day}/${month}/${year}`;
}

export function startDateError(value: string, today: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith("0000")) return "Selecciona una fecha de inicio válida.";
  const parsed = new Date(`${value}T12:00:00Z`);
  if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) return "Selecciona una fecha de inicio válida.";
  return value > today ? "La fecha de inicio no puede estar en el futuro." : null;
}

export function cutoffChangeWarning(selected: string, active: string): string | null {
  if (!selected || selected === active) return null;
  return selected < active
    ? "Esta fecha puede incorporar ventas anteriores con saldo pendiente a las cuentas por cobrar."
    : "Esta fecha puede excluir ventas que actualmente aparecen en las cuentas por cobrar.";
}

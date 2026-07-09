/**
 * Convierte una fecha (Date o ISO string) al formato aceptado por un
 * `<input type="datetime-local">` (YYYY-MM-DDTHH:mm) en hora local.
 */
export function toDateTimeLocalValue(date: Date | string) {
  const value = typeof date === "string" ? new Date(date) : date;
  const offsetDate = new Date(value.getTime() - value.getTimezoneOffset() * 60000);
  return offsetDate.toISOString().slice(0, 16);
}

/** Formatea una fecha ISO a texto legible en español (fecha + hora corta). */
export function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("es", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

import type { PurchaseDocumentType, PurchaseStatus } from "@/types/api";


export function formatPurchaseCurrency(value: string | number | null | undefined) {
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 2,
  }).format(Number.isFinite(amount) ? amount : 0);
}

export function formatPurchaseDate(value: string) {
  return new Intl.DateTimeFormat("es-AR", { dateStyle: "medium" }).format(
    new Date(`${value.slice(0, 10)}T12:00:00`),
  );
}

export function formatPurchaseDateTime(value: string | null) {
  if (!value) return "Sin registrar";
  return new Intl.DateTimeFormat("es-AR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function labelPurchaseStatus(status: PurchaseStatus) {
  const labels: Record<PurchaseStatus, string> = {
    draft: "Borrador",
    cancelled: "Cancelada",
    received: "Recibida",
    partially_received: "Recepción parcial",
    returned: "Devuelta",
  };
  return labels[status];
}

export function labelPurchaseDocumentType(type: PurchaseDocumentType) {
  const labels: Record<PurchaseDocumentType, string> = {
    invoice: "Factura",
    receipt: "Recibo",
    ticket: "Ticket",
    delivery_note: "Remito",
    other: "Otro",
  };
  return labels[type];
}

export function formatPurchaseUser(name?: string | null, email?: string | null) {
  if (name && email) return `${name} · ${email}`;
  return name || email || "Sin usuario registrado";
}

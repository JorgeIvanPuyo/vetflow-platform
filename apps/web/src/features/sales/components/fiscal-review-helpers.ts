import type { SaleFiscalDocument } from "@/types/api";
import type { FiscalConfiguration, FiscalPaymentClassification, FiscalProposal, FiscalReview, FiscalReviewPayment } from "@/types/fiscal";

export function fiscalPaymentStatusLabel(status: FiscalPaymentClassification): string {
  return { available: "Elegible", proposed: "Propuesto (sin reserva)", committed: "Reservado", excluded: "Excluido por política", pending: "Pendiente de resolver" }[status] ?? "Pendiente de resolver";
}

export function fiscalProposalStatusLabel(status: FiscalProposal["status"]): string {
  return { draft: "Borrador · sin reserva", approved: "Aprobada · reserva activa", cancelled: "Cancelada", sent: "Enviada · pendiente de resultado", unknown: "Resultado desconocido · requiere conciliación", authorized: "Autorizada", rejected: "Rechazada", caea_pending: "Contingencia CAEA pendiente" }[status] ?? "Requiere revisión";
}

export function fiscalDocumentStatusLabel(status: SaleFiscalDocument["authorization_status"]): string {
  return { manual: "Adjunto manual", pending: "Pendiente de autorización", unknown: "Resultado desconocido", authorized: "Autorizado", rejected: "Rechazado", caea_pending: "Contingencia CAEA pendiente" }[status] ?? "Requiere revisión";
}

export function canReviewFiscalProposal(review: FiscalReview, proposal: FiscalProposal): boolean {
  return review.permissions.can_generate && (!review.permissions.own_issuer_id || review.permissions.own_issuer_id === proposal.fiscal_issuer_id);
}

export function canApproveFiscalProposal(review: FiscalReview, proposal: FiscalProposal): boolean {
  return review.permissions.can_approve && canReviewFiscalProposal(review, proposal) && proposal.status === "draft" && !proposal.is_stale && proposal.blockers.length === 0;
}

export function selectableFiscalPayments(payments: FiscalReviewPayment[], proposal?: FiscalProposal): FiscalReviewPayment[] {
  return payments.filter((payment) => (payment.status !== "committed" && payment.status !== "excluded") || proposal?.payment_ids.includes(payment.payment_id));
}

export function fiscalProposalIdentity(proposal: FiscalProposal, configuration: FiscalConfiguration) {
  const asRecord = (value: unknown): Record<string, unknown> => value !== null && typeof value === "object" ? value as Record<string, unknown> : {};
  const issuerSnapshot = asRecord(proposal.snapshot.issuer);
  const seriesSnapshot = asRecord(proposal.snapshot.series);
  const issuer = configuration.issuers.find((item) => item.id === proposal.fiscal_issuer_id);
  const series = configuration.series.find((item) => item.id === proposal.fiscal_series_id);
  return {
    name: String(issuerSnapshot.legal_name || issuer?.legal_name || issuer?.display_name || "Emisor histórico"),
    cuit: String(issuerSnapshot.cuit || seriesSnapshot.cuit_snapshot || series?.cuit_snapshot || "pendiente"),
    taxCondition: String(issuerSnapshot.tax_condition || issuer?.tax_condition || "pendiente"),
    environment: seriesSnapshot.environment ?? series?.environment,
    pointOfSale: seriesSnapshot.point_of_sale ?? series?.point_of_sale ?? "pendiente",
    documentType: seriesSnapshot.document_type ?? series?.document_type,
    concept: seriesSnapshot.concept ?? proposal.concept,
    authorizationMode: seriesSnapshot.authorization_mode ?? series?.authorization_mode,
  };
}

export function fiscalProposalPaymentAmount(proposal: FiscalProposal, paymentId: string, review: FiscalReview): string {
  const snapshots = proposal.snapshot.payments;
  if (Array.isArray(snapshots)) {
    const snapshot = snapshots.find((value) => value && typeof value === "object" && value.id === paymentId);
    if (snapshot && typeof snapshot.amount_ars === "string") return snapshot.amount_ars;
  }
  return proposal.allocations.find((allocation) => allocation.payment_id === paymentId)?.amount_ars ?? review.payments.find((payment) => payment.payment_id === paymentId)?.amount_ars ?? "pendiente";
}

// Sum monetary strings as whole cents; selecting a payment always selects its full amount.
export function selectedFiscalTotal(payments: FiscalReviewPayment[], selectedIds: string[]): string {
  let cents = BigInt(0);
  for (const payment of payments) {
    if (!selectedIds.includes(payment.payment_id)) continue;
    if (!/^\d+(?:\.\d{1,2})?$/.test(payment.amount_ars)) throw new Error("Importe de cobro inválido");
    const [whole, fraction = ""] = payment.amount_ars.split(".");
    cents += BigInt(whole) * BigInt(100) + BigInt(fraction.padEnd(2, "0"));
  }
  return `${cents / BigInt(100)}.${String(cents % BigInt(100)).padStart(2, "0")}`;
}

export function fiscalBlockerAction(code: string): string {
  if (/manual/.test(code)) return "Regulariza la imputación del comprobante manual con el contador antes de reservar nuevos cobros.";
  if (/currency|ars|usd/.test(code)) return "Usa una venta en ARS para el circuito argentino; no se convierten importes.";
  if (/stale|changed/.test(code)) return "Revisa y guarda nuevamente el borrador con los datos actuales antes de aprobar.";
  if (/attribution|mixed|split|composition/.test(code)) return "Revisa la atribución fiscal de líneas y cobros con el contador. Un cobro no puede dividirse automáticamente.";
  if (/production/.test(code)) return "Completa la revisión contable y prepara homologación. La validación externa sigue pendiente y producción permanece bloqueada.";
  if (/policy|issuer|series|configuration/.test(code)) return "Revisa política, identidad del emisor y serie en Ajustes fiscales.";
  if (/reserved|committed/.test(code)) return "Cancela explícitamente la propuesta aprobada aún no enviada antes de anular el cobro o revertir la venta.";
  return "Corrige la causa indicada y vuelve a revisar antes de aprobar.";
}

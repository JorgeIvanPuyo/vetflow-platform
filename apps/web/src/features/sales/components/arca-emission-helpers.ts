import type { FiscalBusinessPayload, FiscalEmission } from "@/types/arca-emission";
import type { FiscalProposal } from "@/types/fiscal";

export type EmissionLineForm = FiscalBusinessPayload["lines"][number];
export type EmissionForm = {
  fiscal_address: string; gross_income_registration: string; activity_start_date: string; fiscal_data_review_note: string;
  receiver_name: string; receiver_address: string; document_type: string; document_number: string; iva_condition_id: string;
  consumer_final: "" | "yes" | "no"; voucher_date: string; service_from: string; service_to: string; payment_due: string;
  lines: EmissionLineForm[];
};

export function emissionStatusLabel(status: FiscalEmission["status"]): string {
  return { prepared: "Intención preparada · sin enviar", processing: "Operación en curso", unknown: "Resultado incierto · requiere reconciliación", conflict: "Conflicto remoto · emisión bloqueada", rejected: "Rechazo definitivo", authorized: "Autorizado" }[status] ?? "Requiere revisión";
}

function cents(value: string): bigint {
  if (!/^\d+(?:\.\d{1,2})?$/.test(value)) throw new Error("Usa importes positivos con hasta dos decimales.");
  const [whole, fraction = ""] = value.split(".");
  return BigInt(whole) * BigInt(100) + BigInt(fraction.padEnd(2, "0"));
}
function amount(value: bigint): string { return `${value / BigInt(100)}.${String(value % BigInt(100)).padStart(2, "0")}`; }

export function emissionLineTotal(quantity: string, unitPrice: string): string {
  const product = cents(quantity) * cents(unitPrice);
  return amount((product + BigInt(50)) / BigInt(100));
}

export function emissionLinesTotal(lines: EmissionLineForm[]): string {
  return amount(lines.reduce((sum, line) => sum + cents(line.total), BigInt(0)));
}

export function initialEmissionForm(proposal: FiscalProposal): EmissionForm {
  return { fiscal_address: "", gross_income_registration: "", activity_start_date: "", fiscal_data_review_note: "", receiver_name: "", receiver_address: "", document_type: "", document_number: "", iva_condition_id: "", consumer_final: "", voucher_date: "", service_from: "", service_to: "", payment_due: "", lines: [{ description: proposal.fiscal_description, quantity: "1", unit_price: proposal.total_ars, total: proposal.total_ars }] };
}

export function buildEmissionPayload(proposal: FiscalProposal, form: EmissionForm): FiscalBusinessPayload {
  const issuer = proposal.snapshot.issuer as Record<string, unknown> | undefined;
  const series = proposal.snapshot.series as Record<string, unknown> | undefined;
  if (!issuer || !series || !issuer.cuit || !issuer.legal_name || !issuer.tax_condition) throw new Error("La aprobación necesita una identidad fiscal completa antes de preparar la intención.");
  if (series.environment !== "homologation") throw new Error("La emisión en producción permanece bloqueada.");
  if (proposal.currency !== "ARS" || !["receipt_c", "invoice_c"].includes(String(series.document_type)) || !Number.isInteger(Number(series.point_of_sale)) || Number(series.point_of_sale) < 1) throw new Error("Revisa moneda, punto de venta y tipo del comprobante aprobado.");
  if (!form.fiscal_address.trim() || (!form.gross_income_registration.trim() || !form.activity_start_date) && !form.fiscal_data_review_note.trim()) throw new Error("Completa domicilio, ingresos brutos e inicio de actividades, o documenta por qué estos últimos no corresponden.");
  if (form.consumer_final === "" || !form.document_type || form.document_number === "" || !form.iva_condition_id || !form.receiver_name.trim() || !form.receiver_address.trim()) throw new Error("Confirma explícitamente el receptor, su identificación y su condición de IVA.");
  if (!/^\d+$/.test(form.document_number) || !Number.isSafeInteger(Number(form.document_number)) || !/^\d+$/.test(form.document_type) || !/^\d+$/.test(form.iva_condition_id)) throw new Error("La identificación del receptor debe usar códigos y números válidos.");
  if ((form.consumer_final === "yes") !== (Number(form.iva_condition_id) === 5) || (Number(form.document_type) === 99 ? form.consumer_final !== "yes" || Number(form.document_number) !== 0 : Number(form.document_number) <= 0)) throw new Error("La selección de consumidor final debe coincidir con su condición IVA y su identificación explícita.");
  if (!form.voucher_date || proposal.concept !== 1 && (!form.service_from || !form.service_to || !form.payment_due)) throw new Error("Completa la fecha y el período de prestación y vencimiento que correspondan.");
  if (proposal.concept !== 1 && (form.service_to < form.service_from || form.payment_due < form.voucher_date) || form.activity_start_date && form.activity_start_date > form.voucher_date) throw new Error("Revisa el orden de las fechas de prestación, vencimiento e inicio de actividades.");
  if (!form.lines.length || form.lines.some((line) => !line.description.trim() || cents(line.quantity) === BigInt(0) || emissionLineTotal(line.quantity, line.unit_price) !== amount(cents(line.total)))) throw new Error("Revisa las cantidades, precios y descripciones del detalle documentado.");
  if (emissionLinesTotal(form.lines) !== amount(cents(proposal.total_ars))) throw new Error("El detalle debe coincidir exactamente con el total reservado de esta propuesta.");
  return {
    environment: "homologation",
    issuer: { cuit: String(issuer.cuit), legal_name: String(issuer.legal_name), tax_condition: String(issuer.tax_condition), fiscal_address: form.fiscal_address.trim(), gross_income_registration: form.gross_income_registration.trim() || null, activity_start_date: form.activity_start_date || null, fiscal_data_review_note: form.fiscal_data_review_note.trim() || null },
    receiver: { document_type: Number(form.document_type), document_number: Number(form.document_number), iva_condition_id: Number(form.iva_condition_id), name: form.receiver_name.trim(), address: form.receiver_address.trim(), consumer_final: form.consumer_final === "yes" },
    point_of_sale: Number(series.point_of_sale), document_type: series.document_type === "invoice_c" ? 11 : 15, concept: proposal.concept,
    voucher_date: form.voucher_date, service_from: proposal.concept === 1 ? null : form.service_from, service_to: proposal.concept === 1 ? null : form.service_to, payment_due: proposal.concept === 1 ? null : form.payment_due,
    currency: "PES", exchange_rate: "1", total: proposal.total_ars, net_amount: proposal.total_ars,
    lines: form.lines.map((line) => ({ ...line, description: line.description.trim() })),
  };
}

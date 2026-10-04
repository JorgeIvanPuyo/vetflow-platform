import { confirmSale, type SaleConfirmInput, type SaleInitialPaymentInput } from "@/services/sales";
import { createPaymentIntent, createRequestIntent } from "./sale-payment-intent";

export type SaleConfirmationMode = "full" | "partial" | "pending";

// P.2: sale payments and sale totals use Numeric(16, 2).
const MAX_PAYMENT_CENTS = BigInt("9999999999999999");

export function parseSaleMoney(value: string): bigint | null {
  const match = /^(\d{1,14})(?:[.,](\d{1,2}))?$/.exec(value.trim());
  if (!match) return null;
  const cents = BigInt(match[1]) * BigInt(100) + BigInt((match[2] ?? "").padEnd(2, "0"));
  return cents <= MAX_PAYMENT_CENTS ? cents : null;
}

export function saleMoneyFromCents(cents: bigint): string {
  if (cents < BigInt(0)) return `-${saleMoneyFromCents(-cents)}`;
  return `${cents / BigInt(100)}.${(cents % BigInt(100)).toString().padStart(2, "0")}`;
}

export { formatExactCurrency as formatSaleConfirmationMoney } from "@/lib/money";

export function saleConfirmationAmounts(total: string, mode: SaleConfirmationMode, amount: string) {
  const totalCents = parseSaleMoney(total);
  if (totalCents === null) return { payment: null, balance: null, error: "No pudimos validar el total de la venta." };
  if (totalCents === BigInt(0) || mode === "pending") return { payment: "0.00", balance: saleMoneyFromCents(totalCents), error: null };
  if (mode === "full") return { payment: saleMoneyFromCents(totalCents), balance: "0.00", error: null };
  const paid = parseSaleMoney(amount);
  if (paid === null) return { payment: null, balance: null, error: "Ingresa un importe válido con hasta 2 decimales." };
  if (paid <= BigInt(0)) return { payment: null, balance: null, error: "El importe pagado debe ser mayor que cero." };
  if (paid >= totalCents) return { payment: null, balance: null, error: "El pago parcial debe ser menor que el total. Para saldarlo, elige Pago completo." };
  return { payment: saleMoneyFromCents(paid), balance: saleMoneyFromCents(totalCents - paid), error: null };
}

export function createSaleConfirmationIntent(makeKey = () => crypto.randomUUID()) {
  return createPaymentIntent<SaleInitialPaymentInput>(
    (saleId, payment, key) => confirmSale(saleId, { confirm: true, initial_payment: payment }, key),
    makeKey,
  );
}

export const MAX_CONFIRMATION_PAYMENTS = 20;
export type SaleConfirmationRow = {
  id: string;
  payment_method_id: string;
  amount_ars: string;
  reference: string;
  notes: string;
};
export type SaleConfirmationRowErrors = Partial<Record<"payment_method_id" | "amount_ars" | "reference" | "notes", string>>;

export function confirmationRowsSignature(rows: readonly SaleConfirmationRow[]) {
  return JSON.stringify(rows.map((row) => {
    const cents = parseSaleMoney(row.amount_ars);
    return [row.payment_method_id, cents === null ? row.amount_ars.trim() : saleMoneyFromCents(cents),
      row.reference.trim() || null, row.notes.trim() || null];
  }));
}

export function saleConfirmationRows(total: string, mode: SaleConfirmationMode, rows: readonly SaleConfirmationRow[], methods: readonly { id: string }[]) {
  const totalCents = parseSaleMoney(total);
  const rowErrors: SaleConfirmationRowErrors[] = [];
  const payments: SaleInitialPaymentInput[] = [];
  if (totalCents === null) return { payment: null, balance: null, error: "No pudimos validar el total de la venta.", rowErrors, payments };
  if (totalCents === BigInt(0) || mode === "pending") return { payment: "0.00", balance: saleMoneyFromCents(totalCents), error: null, rowErrors, payments };
  let paid = BigInt(0);
  let amountsValid = true;
  for (const row of rows) {
    const errors: SaleConfirmationRowErrors = {};
    if (!methods.some((method) => method.id === row.payment_method_id)) errors.payment_method_id = "Selecciona una forma de pago disponible.";
    const cents = parseSaleMoney(row.amount_ars);
    if (cents === null) { errors.amount_ars = "Ingresa un importe válido con hasta 2 decimales."; amountsValid = false; }
    else {
      paid += cents;
      if (cents === BigInt(0)) errors.amount_ars = "El importe debe ser mayor que cero.";
    }
    if (row.reference.trim().length > 255) errors.reference = "La referencia admite hasta 255 caracteres.";
    if (row.notes.trim().length > 1000) errors.notes = "Las notas admiten hasta 1000 caracteres.";
    rowErrors.push(errors);
    payments.push({ payment_method_id: row.payment_method_id, amount_ars: cents === null ? row.amount_ars : saleMoneyFromCents(cents),
      reference: row.reference.trim() || null, notes: row.notes.trim() || null });
  }
  const payment = amountsValid ? saleMoneyFromCents(paid) : null;
  const balance = amountsValid ? saleMoneyFromCents(totalCents - paid) : null;
  let error: string | null = null;
  if (rows.length < 1 || rows.length > MAX_CONFIRMATION_PAYMENTS) error = "Agrega entre 1 y 20 formas de pago.";
  else if (rowErrors.some((errors) => Object.keys(errors).length)) error = "Revisa los datos de cada pago.";
  else if (paid > totalCents) error = "overpaid";
  else if (mode === "full" && paid < totalCents) error = "underpaid";
  else if (mode === "partial" && paid === totalCents) error = "El importe cubre el total. Usa “Pago completo”.";
  return { payment, balance, error, rowErrors, payments };
}

export function confirmationPayload(payments: readonly SaleInitialPaymentInput[]): SaleConfirmInput {
  if (payments.length === 0) return { confirm: true };
  if (payments.length === 1) return { confirm: true, initial_payment: payments[0] };
  return { confirm: true, initial_payments: [...payments] };
}

export function createSaleConfirmationRowsIntent(makeKey = () => crypto.randomUUID()) {
  return createRequestIntent<SaleInitialPaymentInput[]>(
    (saleId, payments, key) => confirmSale(saleId, confirmationPayload(payments), key), makeKey,
    (saleId, payments) => JSON.stringify([saleId, payments.length === 1 ? "individual" : "batch", payments.map((payment) => [
      payment.payment_method_id, parseSaleMoney(payment.amount_ars)?.toString() ?? payment.amount_ars,
      payment.received_at ?? null, payment.reference?.trim() || null, payment.notes?.trim() || null,
    ])]),
  );
}

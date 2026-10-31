import type { PurchaseDiscountType } from "@/types/api";

const ZERO = BigInt(0), HUNDRED = BigInt(100), BASIS = BigInt(10000);
const MAX_CENTS = BigInt("9999999999999999");
function cents(raw: string, round = false): bigint | null {
  const match = /^(\d+)(?:[.,](\d*))?$/.exec(raw.trim());
  if (!match || (!round && (match[2]?.length ?? 0) > 2)) return null;
  const fraction = match[2] ?? "";
  return BigInt(match[1]) * HUNDRED + BigInt(fraction.slice(0, 2).padEnd(2, "0")) + (round && Number(fraction[2] ?? 0) >= 5 ? BigInt(1) : ZERO);
}
function money(value: bigint) {
  return `${value / HUNDRED}.${String(value % HUNDRED).padStart(2, "0")}`;
}

export function purchaseDiscountPreview(
  lines: Array<{ quantity: string; unitPrice: string; taxRate: string }>,
  type: PurchaseDiscountType,
  raw: string,
) {
  let subtotal = ZERO, tax = ZERO;
  for (const line of lines) {
    const quantity = /^\d+$/.test(line.quantity.trim()) ? BigInt(line.quantity.trim()) : ZERO;
    const lineSubtotal = quantity * (cents(line.unitPrice, true) ?? ZERO);
    subtotal += lineSubtotal;
    tax += (lineSubtotal * (cents(line.taxRate, true) ?? ZERO) + BASIS / BigInt(2)) / BASIS;
  }
  const total = subtotal + tax;
  const value = type === "none" ? ZERO : cents(raw);
  let error: string | null = total > MAX_CENTS ? "El total original supera el límite monetario de la compra." : null;
  if (value === null || value > MAX_CENTS) error = "Ingresa un descuento mayor o igual a cero, con hasta dos decimales y dentro del límite monetario.";
  else if (type === "percentage" && value > BASIS) error = "El porcentaje de descuento debe estar entre 0 y 100.";
  const discount = value === null ? ZERO : type === "percentage" ? (total * value + BASIS / BigInt(2)) / BASIS : value;
  if (!error && discount > total) error = "El descuento no puede superar el total original de la compra.";
  return {
    subtotal: money(subtotal), tax: money(tax), total: money(total),
    discount_amount_ars: error ? null : money(discount),
    amount_payable_ars: error ? null : money(total - discount), error,
  };
}

"use client";

import { CheckCircle2, Plus, X } from "lucide-react";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { useClinic } from "@/features/clinic/clinic-context";
import { getApiErrorMessage, isTransientApiError } from "@/lib/api";
import { resolveMoneyPreferences } from "@/lib/money";
import { confirmSale, getPaymentMethods, getSale } from "@/services/sales";
import type { PaymentMethod, Sale } from "@/types/api";
import {
  confirmationPayload, confirmationRowsSignature, createSaleConfirmationRowsIntent, formatSaleConfirmationMoney,
  MAX_CONFIRMATION_PAYMENTS, parseSaleMoney, saleConfirmationRows,
  type SaleConfirmationMode, type SaleConfirmationRow,
} from "./sale-confirmation-helpers";

export function SaleConfirmationModal({ sale, onConfirmed, onClose }: {
  sale: Sale;
  onConfirmed: (sale: Sale) => void;
  onClose: () => void;
}) {
  const { preferences } = useClinic();
  const money = resolveMoneyPreferences(preferences, sale.currency);
  const [mode, setMode] = useState<SaleConfirmationMode>("pending");
  const [rows, setRows] = useState<SaleConfirmationRow[]>([
    { id: "payment-1", payment_method_id: "", amount_ars: "", reference: "", notes: "" },
  ]);
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [isLoadingMethods, setIsLoadingMethods] = useState(false);
  const [methodsError, setMethodsError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(false);
  const recoverLegacy = useRef(false);
  const nextRowId = useRef(2);
  const focusTarget = useRef<string | null>(null);
  const dialog = useRef<HTMLFormElement>(null);
  const intent = useRef<ReturnType<typeof createSaleConfirmationRowsIntent> | null>(null);
  if (intent.current === null) intent.current = createSaleConfirmationRowsIntent();
  const zeroTotal = parseSaleMoney(sale.total_ars) === BigInt(0);
  const needsPayment = !zeroTotal && mode !== "pending";
  const amounts = saleConfirmationRows(sale.total_ars, mode, rows, methods);
  const validationError = amounts.error === "underpaid"
    ? `Faltan ${formatSaleConfirmationMoney(amounts.balance!, money)} para completar la venta.`
    : amounts.error === "overpaid"
      ? `El total de los pagos supera la venta por ${formatSaleConfirmationMoney(amounts.balance!.slice(1), money)}.`
      : amounts.error;
  const fieldId = (rowId: string, field: string) => `sale-confirm-${sale.id}-${rowId}-${field}`;

  const loadMethods = useCallback(async () => {
    setIsLoadingMethods(true); setMethodsError(null);
    try {
      setMethods((await getPaymentMethods(true)).data.filter((method) => method.is_active)
        .sort((a, b) => a.sort_order - b.sort_order || a.label.localeCompare(b.label)));
    } catch (value) { setMethodsError(getApiErrorMessage(value)); }
    finally { setIsLoadingMethods(false); }
  }, []);

  useEffect(() => { if (!zeroTotal) void loadMethods(); }, [loadMethods, zeroTotal]);
  useEffect(() => {
    if (focusTarget.current) {
      document.getElementById(focusTarget.current)?.focus();
      focusTarget.current = null;
    }
  }, [rows]);
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const previousFocus = document.activeElement;
    document.body.style.overflow = "hidden";
    dialog.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !pending.current) onClose();
      if (event.key !== "Tab") return;
      const elements = dialog.current?.querySelectorAll<HTMLElement>("button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary:not([aria-disabled='true'])");
      if (!elements?.length) { event.preventDefault(); return; }
      const first = elements[0], last = elements[elements.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog.current)) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus();
    };
  }, [onClose]);

  function updateRow(id: string, field: keyof Omit<SaleConfirmationRow, "id">, value: string) {
    if (pending.current) return;
    const updated = rows.map((row) => row.id === id ? { ...row, [field]: value } : row);
    if (confirmationRowsSignature(updated) !== confirmationRowsSignature(rows)) intent.current?.invalidate();
    setRows(updated); setError(null);
  }

  function changeMode(value: SaleConfirmationMode) {
    if (pending.current || value === mode) return;
    intent.current?.invalidate();
    setMode(value); setError(null);
    if (value === "full" && rows.length === 1) setRows([{ ...rows[0], amount_ars: sale.total_ars }]);
  }

  function addRow() {
    if (pending.current || rows.length >= MAX_CONFIRMATION_PAYMENTS) return;
    const id = `payment-${nextRowId.current++}`;
    intent.current?.invalidate();
    focusTarget.current = fieldId(id, "method");
    setRows([...rows, { id, payment_method_id: "", amount_ars: "", reference: "", notes: "" }]);
    setError(null);
  }

  function removeRow(id: string) {
    if (pending.current || rows.length <= 1) return;
    const index = rows.findIndex((row) => row.id === id);
    const updated = rows.filter((row) => row.id !== id);
    intent.current?.invalidate();
    focusTarget.current = fieldId(updated[Math.max(0, index - 1)].id, "method");
    setRows(updated); setError(null);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending.current) return;
    if (validationError) {
      setError(validationError);
      const index = amounts.rowErrors.findIndex((errors) => Object.keys(errors).length);
      if (index >= 0) {
        const errors = amounts.rowErrors[index];
        const field = errors.payment_method_id ? "method" : errors.amount_ars ? "amount" : errors.reference ? "reference" : "notes";
        document.getElementById(fieldId(rows[index].id, field))?.focus();
      }
      return;
    }
    if (needsPayment && (isLoadingMethods || methodsError)) return;
    pending.current = true;
    setIsSubmitting(true); setError(null);
    try {
      if (!needsPayment) {
        // Legacy confirmation has no payment/key to replay. On an explicit
        // retry after a lost response, first recover the persisted Sale.
        if (recoverLegacy.current) {
          const latest = (await getSale(sale.id)).data;
          if (latest.status === "confirmed") { onConfirmed(latest); return; }
        }
        onConfirmed((await confirmSale(sale.id)).data);
        return;
      }
      const result: { sale?: Sale } = {};
      const submitted = await intent.current?.submit(sale.id, amounts.payments, async (id, payments, key) => {
        result.sale = (await confirmSale(id, confirmationPayload(payments), key)).data;
      });
      if (submitted && result.sale) onConfirmed(result.sale);
    } catch (value) {
      if (!needsPayment && isTransientApiError(value)) recoverLegacy.current = true;
      setError(isTransientApiError(value)
        ? "No pudimos confirmar la venta. Reintenta sin cambiar los datos para recuperar la misma operación."
        : getApiErrorMessage(value));
    } finally { pending.current = false; setIsSubmitting(false); }
  }

  return createPortal(
    <div className="purchase-modal-backdrop" role="presentation">
      <form ref={dialog} tabIndex={-1} className="panel purchase-modal sale-confirmation-modal" role="dialog" aria-modal="true" aria-labelledby="sale-confirm-title" aria-describedby="sale-confirm-description" onSubmit={submit} noValidate>
        <button className="icon-button purchase-modal__close" type="button" aria-label="Cerrar confirmación" disabled={isSubmitting} onClick={onClose}><X size={18} /></button>
        <div className="section-heading"><h2 id="sale-confirm-title">Confirmar venta</h2><p id="sale-confirm-description">La venta quedará cerrada y se descontará el stock de sus productos.</p></div>
        <div className="sale-confirmation-total"><span>Total de la venta</span><strong>{formatSaleConfirmationMoney(sale.total_ars, money)}</strong></div>
        {zeroTotal ? <p>Venta sin importe a cobrar</p> : <fieldset className="sale-confirmation-options" disabled={isSubmitting}>
          <legend>¿Cómo se pagó?</legend>
          {([ ["full", "Pago completo"], ["partial", "Pago parcial"], ["pending", "Dejar pendiente"] ] as const).map(([value, label]) =>
            <label key={value}><input type="radio" name="sale-payment-mode" value={value} checked={mode === value} onChange={() => changeMode(value)} /><span>{label}</span></label>
          )}
        </fieldset>}
        {needsPayment ? <fieldset className="sale-confirmation-fields" disabled={isSubmitting}>
          <legend className="sr-only">Formas de pago</legend>
          {methodsError ? <div className="error-state" role="alert">{methodsError}<button className="secondary-button" type="button" disabled={isSubmitting || isLoadingMethods} onClick={() => void loadMethods()}>Reintentar</button></div> : !isLoadingMethods && methods.length === 0 ? <p>No hay formas de pago activas disponibles. Puedes dejar la venta pendiente.</p> : null}
          {rows.map((row, index) => {
            const errors = amounts.rowErrors[index] ?? {};
            const amountLabel = rows.length === 1 ? (mode === "full" ? "Importe" : "Importe pagado") : `Importe ${index + 1}`;
            const methodError = !isLoadingMethods && !methodsError ? errors.payment_method_id : undefined;
            return <fieldset key={row.id} className="sale-confirmation-row" disabled={isSubmitting}>
              <legend>Pago {index + 1}</legend>
              <div className="sale-confirmation-row__fields">
                <label className="field" htmlFor={fieldId(row.id, "method")}><span>Forma de pago *</span><select id={fieldId(row.id, "method")} required aria-label={rows.length === 1 ? "Forma de pago" : `Forma de pago ${index + 1}`} value={row.payment_method_id} disabled={isSubmitting || isLoadingMethods || Boolean(methodsError)} onChange={(event) => updateRow(row.id, "payment_method_id", event.target.value)} aria-invalid={Boolean(methodError)} aria-describedby={methodError ? fieldId(row.id, "method-error") : undefined}>
                  <option value="">{isLoadingMethods ? "Cargando formas de pago..." : "Seleccionar..."}</option>
                  {methods.map((method) => <option key={method.id} value={method.id}>{method.label}</option>)}
                </select>{methodError ? <small className="sale-confirmation-row__error" id={fieldId(row.id, "method-error")}>{methodError}</small> : null}</label>
                <label className="field" htmlFor={fieldId(row.id, "amount")}><span>Importe *</span><input id={fieldId(row.id, "amount")} required aria-label={amountLabel} type="text" inputMode="decimal" placeholder="0,00" value={row.amount_ars} onChange={(event) => updateRow(row.id, "amount_ars", event.target.value)} aria-invalid={Boolean(errors.amount_ars)} aria-describedby={errors.amount_ars ? fieldId(row.id, "amount-error") : undefined} />{errors.amount_ars ? <small className="sale-confirmation-row__error" id={fieldId(row.id, "amount-error")}>{errors.amount_ars}</small> : null}</label>
              </div>
              <details className="sale-confirmation-extras"><summary aria-disabled={isSubmitting} tabIndex={isSubmitting ? -1 : 0} onClick={(event) => { if (pending.current) event.preventDefault(); }}>Referencia y notas (opcional)</summary>
                <label className="field" htmlFor={fieldId(row.id, "reference")}><span>Referencia</span><input id={fieldId(row.id, "reference")} aria-label={rows.length === 1 ? "Referencia" : `Referencia ${index + 1}`} maxLength={255} value={row.reference} onChange={(event) => updateRow(row.id, "reference", event.target.value)} aria-invalid={Boolean(errors.reference)} aria-describedby={errors.reference ? fieldId(row.id, "reference-error") : undefined} />{errors.reference ? <small className="sale-confirmation-row__error" id={fieldId(row.id, "reference-error")}>{errors.reference}</small> : null}</label>
                <label className="field" htmlFor={fieldId(row.id, "notes")}><span>Notas</span><textarea id={fieldId(row.id, "notes")} aria-label={rows.length === 1 ? "Notas" : `Notas ${index + 1}`} rows={2} maxLength={1000} value={row.notes} onChange={(event) => updateRow(row.id, "notes", event.target.value)} aria-invalid={Boolean(errors.notes)} aria-describedby={errors.notes ? fieldId(row.id, "notes-error") : undefined} />{errors.notes ? <small className="sale-confirmation-row__error" id={fieldId(row.id, "notes-error")}>{errors.notes}</small> : null}</label>
              </details>
              {rows.length > 1 ? <button className="secondary-button sale-confirmation-row__remove" type="button" aria-label={`Quitar pago ${index + 1}`} disabled={isSubmitting} onClick={() => removeRow(row.id)}>Quitar</button> : null}
            </fieldset>;
          })}
          <button className="secondary-button sale-confirmation-add" type="button" aria-label="Agregar forma de pago" disabled={isSubmitting || rows.length >= MAX_CONFIRMATION_PAYMENTS} onClick={addRow}><Plus size={16} /> Agregar forma de pago</button>
          {rows.length >= MAX_CONFIRMATION_PAYMENTS ? <small>Máximo de 20 formas de pago.</small> : null}
        </fieldset> : !zeroTotal ? <p>La venta se confirmará sin registrar un cobro. El saldo quedará pendiente.</p> : null}
        <dl className="sale-confirmation-summary" aria-live="polite">
          <div><dt>Total venta</dt><dd>{formatSaleConfirmationMoney(sale.total_ars, money)}</dd></div>
          <div><dt>Total ingresado</dt><dd>{amounts.payment === null ? "—" : formatSaleConfirmationMoney(amounts.payment, money)}</dd></div>
          <div><dt>Saldo pendiente</dt><dd>{amounts.balance === null ? "—" : formatSaleConfirmationMoney(amounts.balance, money)}</dd></div>
        </dl>
        {needsPayment && validationError && !isLoadingMethods && !methodsError ? <div className="error-state" role="alert">{validationError}</div> : null}
        {error && error !== validationError ? <div className="error-state" role="alert">{error}</div> : null}
        <div className="purchase-modal__actions"><button className="secondary-button" type="button" disabled={isSubmitting} onClick={onClose}>Volver</button><button className="primary-button" type="submit" disabled={isSubmitting || Boolean(validationError) || (needsPayment && (isLoadingMethods || Boolean(methodsError)))}><CheckCircle2 size={17} /> {isSubmitting ? "Confirmando..." : "Confirmar venta"}</button></div>
      </form>
    </div>, document.body,
  );
}

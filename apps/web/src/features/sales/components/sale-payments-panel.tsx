"use client";

import { AlertTriangle, Banknote, Plus, Settings2, X } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

import { useClinic } from "@/features/clinic/clinic-context";
import { formatPurchaseCurrency, formatPurchaseDateTime, formatPurchaseUser } from "@/features/purchases/components/purchase-helpers";
import { labelPaymentType } from "@/features/sales/components/payment-methods-screen";
import { getApiErrorMessage } from "@/lib/api";
import { resolveMoneyPreferences } from "@/lib/money";
import { createSalePayment, getPaymentMethods, voidSalePayment } from "@/services/sales";
import type { PaymentMethod, Sale, SalePayment } from "@/types/api";

export function SalePaymentsPanel({ sale, onUpdated }: { sale: Sale; onUpdated: () => Promise<void> }) {
  const { preferences } = useClinic();
  const moneyPreferences = resolveMoneyPreferences(preferences);
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [methodId, setMethodId] = useState("");
  const [amount, setAmount] = useState("");
  const [receivedAt, setReceivedAt] = useState("");
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");
  const [voiding, setVoiding] = useState<SalePayment | null>(null);
  const [voidReason, setVoidReason] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadMethods = useCallback(async () => { try { setMethods((await getPaymentMethods(true)).data); } catch (value) { setError(getApiErrorMessage(value)); } }, []);
  useEffect(() => { void loadMethods(); }, [loadMethods]);
  const ordered = useMemo(() => [...methods].sort((a, b) => a.sort_order - b.sort_order || a.label.localeCompare(b.label)), [methods]);

  function openForm() { setMethodId(ordered[0]?.id ?? ""); setAmount(sale.balance_due_ars); const local = new Date(Date.now() - new Date().getTimezoneOffset() * 60_000).toISOString().slice(0, 16); setReceivedAt(local); setReference(""); setNotes(""); setError(null); setShowForm(true); }
  async function submit(event: FormEvent) { event.preventDefault(); if (!methodId) { setError("Selecciona una forma de pago."); return; } setIsSaving(true); setError(null); try { await createSalePayment(sale.id, { payment_method_id: methodId, amount_ars: amount, received_at: new Date(receivedAt).toISOString(), reference: reference.trim() || null, notes: notes.trim() || null }); setShowForm(false); await onUpdated(); } catch (value) { setError(getApiErrorMessage(value)); } finally { setIsSaving(false); } }
  async function confirmVoid(event: FormEvent) { event.preventDefault(); if (!voiding || !voidReason.trim()) { setError("Ingresa el motivo de anulación."); return; } setIsSaving(true); setError(null); try { await voidSalePayment(voiding.id, voidReason.trim()); setVoiding(null); setVoidReason(""); await onUpdated(); } catch (value) { setError(getApiErrorMessage(value)); } finally { setIsSaving(false); } }

  return <section className="panel sale-fiscal-panel" aria-label="Cobros de la venta">
    <div className="section-heading"><div><h2>Cobros</h2><p>{labelPaymentStatus(sale.payment_status)}</p></div>{sale.payment_status ? <span className={`badge payment-status--${sale.payment_status}`}>{labelPaymentStatus(sale.payment_status)}</span> : null}</div>
    {sale.payment_requires_attention ? <div className="purchase-reversal-warning" role="alert"><AlertTriangle size={18} /><span>La venta fue revertida y conserva cobros activos. Requiere revisión manual; Vetflow no registra devoluciones ni reembolsos automáticamente.</span></div> : null}
    <div className="panel purchase-summary"><div><span>Total</span><strong>{formatPurchaseCurrency(sale.total_ars, moneyPreferences)}</strong></div><div><span>Cobrado</span><strong>{formatPurchaseCurrency(sale.paid_total_ars, moneyPreferences)}</strong></div><div><span>Saldo</span><strong>{formatPurchaseCurrency(sale.balance_due_ars, moneyPreferences)}</strong></div></div>
    {error ? <div className="error-state" role="alert">{error}</div> : null}
    {sale.status === "confirmed" && Number(sale.balance_due_ars) > 0 ? ordered.length ? <button className="primary-button" type="button" onClick={openForm}><Plus size={17} /> Registrar cobro</button> : <div className="purchase-empty-state"><Banknote size={28} /><h3>No hay formas de pago activas</h3><p>Configura el catálogo antes de registrar el primer cobro.</p><Link className="secondary-button" href="/settings/sales/payment-methods"><Settings2 size={17} /> Ir a Ajustes</Link></div> : null}
    {sale.payments.length ? <div className="inventory-table-scroll"><table className="inventory-table"><thead><tr><th>Forma</th><th>Importe</th><th>Fecha</th><th>Referencia</th><th>Usuario</th><th>Estado</th><th>Acción</th></tr></thead><tbody>{sale.payments.map((payment) => <tr key={payment.id} className="inventory-table__row--static"><td><strong>{payment.payment_method_label_snapshot}</strong><small className="table-cell-subtitle">{labelPaymentType(payment.payment_method_type_snapshot)}</small></td><td>{formatPurchaseCurrency(payment.amount_ars, moneyPreferences)}</td><td>{formatPurchaseDateTime(payment.received_at)}</td><td>{payment.reference || "—"}</td><td>{formatPurchaseUser(payment.created_by_user_name, payment.created_by_user_email)}</td><td>{payment.is_active ? <span className="badge sale-status--confirmed">Activo</span> : <><span className="badge sale-status--cancelled">Anulado</span><small className="table-cell-subtitle">{payment.void_reason} · {formatPurchaseUser(payment.voided_by_user_name, payment.voided_by_user_email)} · {formatPurchaseDateTime(payment.voided_at)}</small></>}</td><td>{payment.is_active ? <button className="secondary-button" type="button" onClick={() => { setVoiding(payment); setVoidReason(""); setError(null); }}>Anular</button> : "—"}</td></tr>)}</tbody></table></div> : <div className="purchase-empty-state"><Banknote size={28} /><h3>Sin cobros registrados</h3><p>{sale.status === "confirmed" ? "El cobro es independiente de la confirmación y del comprobante fiscal." : "Los cobros podrán registrarse cuando la venta esté confirmada."}</p></div>}
    {showForm ? createPortal(<div className="purchase-modal-backdrop" role="presentation"><form className="panel purchase-modal" role="dialog" aria-modal="true" aria-labelledby="sale-payment-title" onSubmit={submit}><button className="icon-button purchase-modal__close" type="button" aria-label="Cerrar cobro" onClick={() => setShowForm(false)}><X size={18} /></button><div className="section-heading"><h2 id="sale-payment-title">Registrar cobro</h2><p>Saldo pendiente: {formatPurchaseCurrency(sale.balance_due_ars, moneyPreferences)}</p></div><label className="field"><span>Forma de pago *</span><select required value={methodId} onChange={(event) => setMethodId(event.target.value)}>{ordered.map((method) => <option key={method.id} value={method.id}>{method.label}</option>)}</select></label><label className="field"><span>Importe *</span><input required inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} /></label><label className="field"><span>Fecha y hora *</span><input required type="datetime-local" value={receivedAt} onChange={(event) => setReceivedAt(event.target.value)} /></label><label className="field"><span>Referencia</span><input maxLength={255} value={reference} onChange={(event) => setReference(event.target.value)} /></label><label className="field"><span>Notas</span><textarea rows={3} maxLength={1000} value={notes} onChange={(event) => setNotes(event.target.value)} /></label><small>No ingreses números de tarjeta, CVV, PIN ni otros datos sensibles.</small>{error ? <div className="error-state" role="alert">{error}</div> : null}<div className="purchase-modal__actions"><button className="secondary-button" type="button" onClick={() => setShowForm(false)}>Cancelar</button><button className="primary-button" type="submit" disabled={isSaving}>{isSaving ? "Registrando..." : "Registrar cobro"}</button></div></form></div>, document.body) : null}
    {voiding ? createPortal(<div className="purchase-modal-backdrop" role="presentation"><form className="panel purchase-modal" role="dialog" aria-modal="true" aria-labelledby="void-payment-title" onSubmit={confirmVoid}><button className="icon-button purchase-modal__close" type="button" aria-label="Cerrar anulación" onClick={() => setVoiding(null)}><X size={18} /></button><div className="section-heading"><h2 id="void-payment-title">Anular cobro</h2><p>{formatPurchaseCurrency(voiding.amount_ars, moneyPreferences)} · {voiding.payment_method_label_snapshot}</p></div><label className="field"><span>Motivo *</span><textarea required rows={3} maxLength={1000} value={voidReason} onChange={(event) => setVoidReason(event.target.value)} /></label>{error ? <div className="error-state" role="alert">{error}</div> : null}<div className="purchase-modal__actions"><button className="secondary-button" type="button" onClick={() => setVoiding(null)}>Volver</button><button className="danger-button" type="submit" disabled={isSaving}>{isSaving ? "Anulando..." : "Anular cobro"}</button></div></form></div>, document.body) : null}
  </section>;
}

export function labelPaymentStatus(status: Sale["payment_status"]) { if (status === "unpaid") return "Sin cobrar"; if (status === "partial") return "Cobro parcial"; if (status === "paid") return "Pagada"; if (status === "requires_attention") return "Requiere atención"; return "No aplica"; }

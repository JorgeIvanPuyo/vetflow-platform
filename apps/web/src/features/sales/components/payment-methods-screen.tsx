"use client";

import { ArrowLeft, Pencil, Plus, Power, Save, X } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { useCurrentUser } from "@/features/auth/current-user-context";
import { getApiErrorMessage } from "@/lib/api";
import { createPaymentMethod, getPaymentMethods, updatePaymentMethod } from "@/services/sales";
import type { PaymentMethod, PaymentMethodType, PaymentMethodWritePayload } from "@/types/api";

type MethodForm = Omit<PaymentMethodWritePayload, "type"> & { type: PaymentMethodType | "" };
const initialForm: MethodForm = { label: "", type: "", is_active: true, sort_order: 0 };

export function PaymentMethodsScreen() {
  const { isLoading } = useCurrentUser();
  if (isLoading) return <div className="loading-state" role="status">Cargando permisos...</div>;
  return <PaymentMethodsScreenContent />;
}

function PaymentMethodsScreenContent() {
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [form, setForm] = useState<MethodForm>(initialForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const writeInFlight = useRef(false);
  const load = useCallback(async () => {
    setIsLoading(true); setError(null);
    try {
      const catalog: PaymentMethod[] = [];
      let page = 1;
      while (true) {
        const response = await getPaymentMethods(undefined, page);
        catalog.push(...response.data);
        if (!response.data.length || catalog.length >= response.meta.total) break;
        page += 1;
      }
      setMethods(catalog);
    } catch (value) { setError(getApiErrorMessage(value)); }
    finally { setIsLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  function startCreate() { setEditingId(null); setForm(initialForm); setError(null); setShowForm(true); }
  function startEdit(method: PaymentMethod) {
    setEditingId(method.id);
    setForm({ label: method.label, type: method.type ?? "", is_active: method.is_active, sort_order: method.sort_order });
    setError(null); setShowForm(true);
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (writeInFlight.current) return;
    if (!form.label.trim()) { setError("Ingresa un nombre para la forma de pago."); return; }
    if (!form.type) { setError("Selecciona un tipo para la forma de pago."); return; }
    writeInFlight.current = true; setIsSaving(true); setError(null);
    try {
      const payload: PaymentMethodWritePayload = { ...form, type: form.type, label: form.label.trim() };
      if (editingId) await updatePaymentMethod(editingId, payload); else await createPaymentMethod(payload);
      setShowForm(false); setEditingId(null); setForm(initialForm); await load();
    } catch (value) { setError(getApiErrorMessage(value)); }
    finally { writeInFlight.current = false; setIsSaving(false); }
  }
  async function toggle(method: PaymentMethod) {
    if (writeInFlight.current) return;
    writeInFlight.current = true; setIsSaving(true); setError(null);
    try { await updatePaymentMethod(method.id, { is_active: !method.is_active }); await load(); }
    catch (value) { setError(getApiErrorMessage(value)); }
    finally { writeInFlight.current = false; setIsSaving(false); }
  }
  const editing = methods.find((method) => method.id === editingId);
  const actions = (method: PaymentMethod) => <div className="purchase-attachment-actions">
    <button className="secondary-button" type="button" disabled={isSaving} aria-label={`Editar ${method.label}`} onClick={() => startEdit(method)}><Pencil size={16} /> Editar</button>
    <button className="secondary-button" type="button" disabled={isSaving} aria-label={`${method.is_active ? "Inactivar" : "Activar"} ${method.label}`} onClick={() => void toggle(method)}><Power size={16} /> {method.is_active ? "Inactivar" : "Activar"}</button>
  </div>;
  const state = (method: PaymentMethod) => <span className={`badge ${method.is_active ? "sale-status--confirmed" : "sale-status--cancelled"}`}>{method.is_active ? "Activa" : "Inactiva"}</span>;

  return <div className="page-stack sales-page payment-methods-page">
    <section className="screen-heading list-page__header"><div>
      <nav className="settings-breadcrumb" aria-label="Breadcrumb"><Link className="back-link" href="/settings"><ArrowLeft size={18} /> Ajustes</Link><span aria-hidden="true">/</span><span>Ventas y cobros</span><span aria-hidden="true">/</span><span aria-current="page">Formas de pago</span></nav>
      <h1>Formas de pago</h1><p>Elige el tipo de cada forma de pago, independientemente de su nombre.</p>
    </div><button className="primary-button" type="button" disabled={isSaving || isLoading} onClick={startCreate}><Plus size={17} /> Nueva forma de pago</button></section>
    {error ? <section className="error-state" role="alert"><p>{error}</p>{!showForm ? <button className="secondary-button" type="button" onClick={() => void load()}>Reintentar</button> : null}</section> : null}
    {showForm ? <form className="panel fiscal-issuer-form" aria-label={editingId ? "Editar forma de pago" : "Nueva forma de pago"} onSubmit={submit}>
      <div className="section-heading fiscal-issuer-form__heading"><div><h2>{editingId ? "Editar forma de pago" : "Nueva forma de pago"}</h2><p>El tipo describe cómo se recibe el cobro. Cambiar el nombre no cambia el tipo.</p></div><button className="icon-button" type="button" disabled={isSaving} aria-label="Cerrar formulario" onClick={() => setShowForm(false)}><X size={18} /></button></div>
      <fieldset className="payment-methods-fields" disabled={isSaving}><div className="fiscal-issuer-form__grid">
        <label className="field" htmlFor="payment-method-name"><span>Nombre *</span><input id="payment-method-name" required maxLength={120} value={form.label} onChange={(event) => setForm((current) => ({ ...current, label: event.target.value }))} /></label>
        <label className="field" htmlFor="payment-method-type"><span>Tipo *</span><select id="payment-method-type" required value={form.type} disabled={Boolean(editing?.has_payments)} aria-describedby="payment-method-type-help" onChange={(event) => setForm((current) => ({ ...current, type: event.target.value as PaymentMethodType | "" }))}><option value="" disabled>Selecciona un tipo</option>{PAYMENT_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><small id="payment-method-type-help">{editing?.has_payments ? "El tipo está bloqueado porque ya existen cobros históricos." : "Selecciona el tipo; el nombre visible puede ser el que usa tu clínica."}</small></label>
        <label className="field" htmlFor="payment-method-order"><span>Orden</span><input id="payment-method-order" type="number" min={0} max={999999} required value={form.sort_order} onChange={(event) => setForm((current) => ({ ...current, sort_order: Number(event.target.value) }))} /></label>
      </div><label className="checkbox-field"><input type="checkbox" checked={form.is_active} onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))} /><span>Disponible para nuevos cobros</span></label></fieldset>
      <div className="purchase-form-actions"><button className="secondary-button" type="button" disabled={isSaving} onClick={() => setShowForm(false)}>Cancelar</button><button className="primary-button" type="submit" disabled={isSaving} aria-live="polite"><Save size={17} /> {isSaving ? "Guardando..." : "Guardar"}</button></div>
    </form> : null}
    {isLoading ? <div className="loading-card" role="status">Cargando formas de pago...</div> : null}
    {!isLoading && !error && !methods.length && !showForm ? <section className="empty-state"><h2>No hay formas de pago configuradas</h2><p>Crea la primera opción para poder registrar cobros en ventas confirmadas.</p></section> : null}
    {!isLoading && methods.length > 0 ? <>
      <section className="inventory-table-card payment-methods-desktop" aria-label="Formas de pago"><table className="inventory-table payment-methods-table"><thead><tr><th>Nombre</th><th>Tipo</th><th>Orden</th><th>Uso histórico</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>{methods.map((method) => <tr key={method.id} className="inventory-table__row--static"><td><strong>{method.label}</strong></td><td>{labelPaymentType(method.type)}</td><td>{method.sort_order}</td><td>{method.has_payments ? "Con cobros" : "Sin cobros"}</td><td>{state(method)}</td><td>{actions(method)}</td></tr>)}</tbody></table></section>
      <section className="payment-methods-mobile" aria-label="Formas de pago móvil">{methods.map((method) => <article className="panel" key={method.id}><strong>{method.label}</strong><span>{labelPaymentType(method.type)}</span>{state(method)}<span>{method.has_payments ? "Con cobros" : "Sin cobros"} · Orden {method.sort_order}</span>{actions(method)}</article>)}</section>
    </> : null}
  </div>;
}

export const PAYMENT_TYPES: [PaymentMethodType, string][] = [["cash", "Efectivo"], ["bank_transfer", "Transferencia bancaria"], ["debit_card", "Tarjeta de débito"], ["credit_card", "Tarjeta de crédito"], ["digital_wallet", "Otro medio electrónico (QR / billetera digital)"], ["other", "Otro"]];
export function labelPaymentType(value: PaymentMethodType | null | undefined) { return PAYMENT_TYPES.find(([type]) => type === value)?.[1] ?? "Sin clasificar"; }

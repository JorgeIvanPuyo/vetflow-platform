"use client";

import { ArrowLeft, Pencil, Plus, Power, Save, X } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { getApiErrorMessage } from "@/lib/api";
import { createPaymentMethod, getPaymentMethods, updatePaymentMethod } from "@/services/sales";
import type { PaymentMethod, PaymentMethodType, PaymentMethodWritePayload } from "@/types/api";

const initialForm: PaymentMethodWritePayload = { label: "", type: "cash", is_active: true, sort_order: 0 };

export function PaymentMethodsScreen() {
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [form, setForm] = useState(initialForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { setError(null); try { setMethods((await getPaymentMethods()).data); } catch (value) { setError(getApiErrorMessage(value)); } }, []);
  useEffect(() => { void load(); }, [load]);
  function startCreate() { setEditingId(null); setForm(initialForm); setError(null); setShowForm(true); }
  function startEdit(method: PaymentMethod) { setEditingId(method.id); setForm({ label: method.label, type: method.type, is_active: method.is_active, sort_order: method.sort_order }); setError(null); setShowForm(true); }
  async function submit(event: FormEvent) { event.preventDefault(); if (!form.label.trim()) { setError("Ingresa un nombre para la forma de pago."); return; } setIsSaving(true); setError(null); try { const payload = { ...form, label: form.label.trim() }; if (editingId) await updatePaymentMethod(editingId, payload); else await createPaymentMethod(payload); setShowForm(false); setEditingId(null); setForm(initialForm); await load(); } catch (value) { setError(getApiErrorMessage(value)); } finally { setIsSaving(false); } }
  async function toggle(method: PaymentMethod) { setError(null); try { await updatePaymentMethod(method.id, { is_active: !method.is_active }); await load(); } catch (value) { setError(getApiErrorMessage(value)); } }
  const editing = methods.find((method) => method.id === editingId);
  return <div className="page-stack sales-page">
    <section className="screen-heading list-page__header"><div><nav className="settings-breadcrumb" aria-label="Breadcrumb"><Link className="back-link" href="/settings"><ArrowLeft size={18} /> Ajustes</Link><span aria-hidden="true">/</span><span>Ventas y facturación</span><span aria-hidden="true">/</span><span aria-current="page">Formas de pago</span></nav><h1>Formas de pago</h1><p>Configura las opciones disponibles al registrar cobros de ventas.</p></div><button className="primary-button" type="button" onClick={startCreate}><Plus size={17} /> Nueva forma de pago</button></section>
    {error ? <section className="error-state" role="alert">{error}</section> : null}
    {showForm ? <form className="panel fiscal-issuer-form" onSubmit={submit}><div className="section-heading fiscal-issuer-form__heading"><div><h2>{editingId ? "Editar forma de pago" : "Nueva forma de pago"}</h2><p>El tipo interno permite reportes consistentes aunque cambie el nombre visible.</p></div><button className="icon-button" type="button" aria-label="Cerrar formulario" onClick={() => setShowForm(false)}><X size={18} /></button></div><div className="fiscal-issuer-form__grid"><label className="field"><span>Nombre *</span><input required maxLength={120} value={form.label} onChange={(event) => setForm((current) => ({ ...current, label: event.target.value }))} /></label><label className="field"><span>Tipo *</span><select value={form.type} disabled={Boolean(editing?.has_payments)} onChange={(event) => setForm((current) => ({ ...current, type: event.target.value as PaymentMethodType }))}>{PAYMENT_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>{editing?.has_payments ? <small>El tipo está bloqueado porque ya existen cobros históricos.</small> : null}</label><label className="field"><span>Orden</span><input type="number" min={0} value={form.sort_order} onChange={(event) => setForm((current) => ({ ...current, sort_order: Number(event.target.value) }))} /></label></div><label className="checkbox-field"><input type="checkbox" checked={form.is_active} onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))} /><span>Disponible para nuevos cobros</span></label><div className="purchase-form-actions"><button className="secondary-button" type="button" onClick={() => setShowForm(false)}>Cancelar</button><button className="primary-button" type="submit" disabled={isSaving}><Save size={17} /> {isSaving ? "Guardando..." : "Guardar"}</button></div></form> : null}
    {!methods.length && !showForm ? <section className="empty-state"><h2>No hay formas de pago configuradas</h2><p>Crea la primera opción para poder registrar cobros en ventas confirmadas.</p></section> : null}
    {methods.length ? <section className="inventory-table-card" aria-label="Formas de pago"><div className="inventory-table-scroll"><table className="inventory-table"><thead><tr><th>Nombre</th><th>Tipo</th><th>Orden</th><th>Uso histórico</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>{methods.map((method) => <tr key={method.id} className="inventory-table__row--static"><td><strong>{method.label}</strong></td><td>{labelPaymentType(method.type)}</td><td>{method.sort_order}</td><td>{method.has_payments ? "Con cobros" : "Sin cobros"}</td><td><span className={`badge ${method.is_active ? "sale-status--confirmed" : "sale-status--cancelled"}`}>{method.is_active ? "Activa" : "Inactiva"}</span></td><td><div className="purchase-attachment-actions"><button className="secondary-button" type="button" onClick={() => startEdit(method)}><Pencil size={16} /> Editar</button><button className="secondary-button" type="button" onClick={() => void toggle(method)}><Power size={16} /> {method.is_active ? "Inactivar" : "Activar"}</button></div></td></tr>)}</tbody></table></div></section> : null}
  </div>;
}

export const PAYMENT_TYPES: [PaymentMethodType, string][] = [["cash", "Efectivo"], ["bank_transfer", "Transferencia bancaria"], ["debit_card", "Tarjeta de débito"], ["credit_card", "Tarjeta de crédito"], ["digital_wallet", "Billetera digital"], ["other", "Otro"]];
export function labelPaymentType(value: PaymentMethodType) { return PAYMENT_TYPES.find(([type]) => type === value)?.[1] ?? value; }

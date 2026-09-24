"use client";

import { ArrowLeft, Pencil, Plus, Power, Save, X } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { getApiErrorMessage } from "@/lib/api";
import { createFiscalIssuer, getFiscalIssuers, getSaleFilterOptions, updateFiscalIssuer } from "@/services/sales";
import type { FiscalDocumentType, FiscalIssuer, FiscalIssuerWritePayload, PurchaseCreatorOption } from "@/types/api";

type IssuerForm = Omit<FiscalIssuerWritePayload, "service_document_type" | "product_document_type"> & {
  service_document_type: FiscalDocumentType;
  product_document_type: FiscalDocumentType;
};

const initialForm: IssuerForm = {
  user_id: "",
  display_name: "",
  tax_id: "",
  is_active: true,
  can_issue_service_receipt_c: true,
  can_issue_product_invoice_c: false,
  service_document_type: "receipt_c",
  service_document_code: "015",
  product_document_type: "invoice_c",
  product_document_code: "011",
};

export function FiscalIssuersScreen() {
  const [issuers, setIssuers] = useState<FiscalIssuer[]>([]);
  const [users, setUsers] = useState<PurchaseCreatorOption[]>([]);
  const [form, setForm] = useState<IssuerForm>(initialForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [issuerResponse, userResponse] = await Promise.all([getFiscalIssuers(), getSaleFilterOptions()]);
      setIssuers(issuerResponse.data);
      setUsers(userResponse.data.creators);
    } catch (value) {
      setError(getApiErrorMessage(value));
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const configuredUsers = useMemo(() => new Set(issuers.filter((item) => item.id !== editingId).map((item) => item.user_id)), [editingId, issuers]);

  function startCreate() {
    setEditingId(null);
    setForm(initialForm);
    setError(null);
    setShowForm(true);
  }

  function startEdit(issuer: FiscalIssuer) {
    setEditingId(issuer.id);
    setForm({
      user_id: issuer.user_id,
      display_name: issuer.display_name,
      tax_id: issuer.tax_id,
      is_active: issuer.is_active,
      can_issue_service_receipt_c: issuer.can_issue_service_receipt_c,
      can_issue_product_invoice_c: issuer.can_issue_product_invoice_c,
      service_document_type: issuer.service_document_type ?? "receipt_c",
      service_document_code: issuer.service_document_code ?? "015",
      product_document_type: issuer.product_document_type ?? "invoice_c",
      product_document_code: issuer.product_document_code ?? "011",
    });
    setError(null);
    setShowForm(true);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form.user_id || !form.display_name.trim() || !form.tax_id.trim()) {
      setError("Completa el usuario, el nombre fiscal y la identificación tributaria.");
      return;
    }
    if (!form.can_issue_service_receipt_c && !form.can_issue_product_invoice_c) {
      setError("Selecciona al menos una capacidad fiscal.");
      return;
    }
    const payload: FiscalIssuerWritePayload = {
      ...form,
      display_name: form.display_name.trim(),
      tax_id: form.tax_id.trim(),
      service_document_type: form.can_issue_service_receipt_c ? form.service_document_type : null,
      service_document_code: form.can_issue_service_receipt_c ? form.service_document_code?.trim() || null : null,
      product_document_type: form.can_issue_product_invoice_c ? form.product_document_type : null,
      product_document_code: form.can_issue_product_invoice_c ? form.product_document_code?.trim() || null : null,
    };
    setIsSaving(true); setError(null);
    try {
      if (editingId) await updateFiscalIssuer(editingId, payload);
      else await createFiscalIssuer(payload);
      setShowForm(false); setEditingId(null); setForm(initialForm);
      await load();
    } catch (value) {
      setError(getApiErrorMessage(value));
    } finally {
      setIsSaving(false);
    }
  }

  async function toggle(issuer: FiscalIssuer) {
    setError(null);
    try {
      await updateFiscalIssuer(issuer.id, { is_active: !issuer.is_active });
      await load();
    } catch (value) { setError(getApiErrorMessage(value)); }
  }

  return <div className="page-stack sales-page">
    <section className="screen-heading list-page__header"><div><nav className="settings-breadcrumb" aria-label="Breadcrumb"><Link className="back-link" href="/settings"><ArrowLeft size={18} /> Ajustes</Link><span aria-hidden="true">/</span><span>Ventas y facturación</span><span aria-hidden="true">/</span><span aria-current="page">Emisores fiscales</span></nav><h1>Emisores fiscales</h1><p>Configura quién puede emitir comprobantes manuales y qué tipos tiene habilitados.</p></div><button className="primary-button" type="button" onClick={startCreate}><Plus size={17} /> Nuevo emisor</button></section>
    {error ? <section className="error-state" role="alert">{error}</section> : null}
    {showForm ? <form className="panel fiscal-issuer-form" onSubmit={submit}>
      <div className="section-heading fiscal-issuer-form__heading"><div><h2>{editingId ? "Editar emisor" : "Nuevo emisor"}</h2><p>El emisor fiscal y el usuario que carga el comprobante se registran por separado.</p></div><button className="icon-button" type="button" aria-label="Cerrar formulario" onClick={() => setShowForm(false)}><X size={18} /></button></div>
      <div className="fiscal-issuer-form__grid">
        <label className="field"><span>Usuario *</span><select required value={form.user_id} onChange={(event) => setForm((current) => ({ ...current, user_id: event.target.value }))}><option value="">Seleccionar</option>{users.map((user) => <option key={user.id} value={user.id} disabled={configuredUsers.has(user.id)}>{user.full_name} · {user.email}</option>)}</select></label>
        <label className="field"><span>Nombre fiscal *</span><input required maxLength={255} value={form.display_name} onChange={(event) => setForm((current) => ({ ...current, display_name: event.target.value }))} /></label>
        <label className="field"><span>Identificación tributaria *</span><input required maxLength={80} value={form.tax_id} onChange={(event) => setForm((current) => ({ ...current, tax_id: event.target.value }))} /></label>
      </div>
      <div className="fiscal-capability-grid">
        <fieldset><label className="checkbox-field"><input type="checkbox" checked={form.can_issue_service_receipt_c} onChange={(event) => setForm((current) => ({ ...current, can_issue_service_receipt_c: event.target.checked }))} /><span>Puede emitir por servicios</span></label>{form.can_issue_service_receipt_c ? <div className="fiscal-capability-fields"><label className="field"><span>Tipo</span><select value={form.service_document_type} onChange={(event) => setForm((current) => ({ ...current, service_document_type: event.target.value as FiscalDocumentType }))}><option value="receipt_c">Recibo C</option><option value="invoice_c">Factura C</option></select></label><label className="field"><span>Código</span><input required maxLength={20} value={form.service_document_code ?? ""} onChange={(event) => setForm((current) => ({ ...current, service_document_code: event.target.value }))} /></label></div> : null}</fieldset>
        <fieldset><label className="checkbox-field"><input type="checkbox" checked={form.can_issue_product_invoice_c} onChange={(event) => setForm((current) => ({ ...current, can_issue_product_invoice_c: event.target.checked }))} /><span>Puede emitir por productos</span></label>{form.can_issue_product_invoice_c ? <div className="fiscal-capability-fields"><label className="field"><span>Tipo</span><select value={form.product_document_type} onChange={(event) => setForm((current) => ({ ...current, product_document_type: event.target.value as FiscalDocumentType }))}><option value="invoice_c">Factura C</option><option value="receipt_c">Recibo C</option></select></label><label className="field"><span>Código</span><input required maxLength={20} value={form.product_document_code ?? ""} onChange={(event) => setForm((current) => ({ ...current, product_document_code: event.target.value }))} /></label></div> : null}</fieldset>
      </div>
      <label className="checkbox-field"><input type="checkbox" checked={form.is_active} onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))} /><span>Emisor activo</span></label>
      <div className="purchase-form-actions"><button className="secondary-button" type="button" onClick={() => setShowForm(false)}>Cancelar</button><button className="primary-button" type="submit" disabled={isSaving}><Save size={17} /> {isSaving ? "Guardando..." : "Guardar emisor"}</button></div>
    </form> : null}
    {!issuers.length && !showForm ? <section className="empty-state"><h2>No hay emisores configurados</h2><p>Agrega el primer emisor para registrar comprobantes de ventas confirmadas.</p></section> : null}
    {issuers.length ? <section className="inventory-table-card" aria-label="Emisores fiscales"><div className="inventory-table-scroll"><table className="inventory-table"><thead><tr><th>Emisor</th><th>Usuario</th><th>Servicios</th><th>Productos</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>{issuers.map((issuer) => <tr key={issuer.id} className="inventory-table__row--static"><td><strong>{issuer.display_name}</strong><small className="table-cell-subtitle">{issuer.tax_id}</small></td><td>{issuer.user_name || issuer.user_email}</td><td>{issuer.can_issue_service_receipt_c ? `${labelType(issuer.service_document_type)} · ${issuer.service_document_code}` : "No habilitado"}</td><td>{issuer.can_issue_product_invoice_c ? `${labelType(issuer.product_document_type)} · ${issuer.product_document_code}` : "No habilitado"}</td><td><span className={`badge ${issuer.is_active ? "sale-status--confirmed" : "sale-status--cancelled"}`}>{issuer.is_active ? "Activo" : "Inactivo"}</span></td><td><div className="purchase-attachment-actions"><button className="secondary-button" type="button" onClick={() => startEdit(issuer)}><Pencil size={16} /> Editar</button><button className="secondary-button" type="button" onClick={() => void toggle(issuer)}><Power size={16} /> {issuer.is_active ? "Inactivar" : "Activar"}</button></div></td></tr>)}</tbody></table></div></section> : null}
  </div>;
}

function labelType(value: FiscalDocumentType | null) {
  if (value === "receipt_c") return "Recibo C";
  if (value === "invoice_c") return "Factura C";
  return "—";
}

"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, Pencil, Plus, Save } from "lucide-react";

import { getApiErrorMessage } from "@/lib/api";
import { createFiscalSeries, getFiscalConfiguration, updateFiscalPolicy, updateFiscalSeries } from "@/services/fiscal";
import { updatePaymentMethod } from "@/services/sales";
import type { PaymentMethod } from "@/types/api";
import type { FiscalConfiguration, FiscalPolicyInput, FiscalSeries, FiscalSeriesInput } from "@/types/fiscal";
import { FiscalEmissionReadinessPanel } from "./fiscal-emission-readiness-panel";

const emptySeries: FiscalSeriesInput = {
  fiscal_issuer_id: "", environment: "homologation", point_of_sale: 0,
  document_type: "receipt_c", concept: 2, authorization_mode: "CAE", is_active: true,
  credential_reference: null, caea_reference: null,
};

export function FiscalConfigurationScreen() {
  const [configuration, setConfiguration] = useState<FiscalConfiguration | null>(null);
  const [policy, setPolicy] = useState<FiscalPolicyInput>({ enabled: false, payment_scope: "electronic_only" });
  const [reviewNote, setReviewNote] = useState("");
  const [series, setSeries] = useState<FiscalSeriesInput>(emptySeries);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showSeries, setShowSeries] = useState(false);
  const [mapping, setMapping] = useState<{ id: string; operational_reference: string; suggested_fiscal_issuer_id: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const inFlight = useRef(false);

  const load = useCallback(async () => {
    const response = await getFiscalConfiguration();
    setConfiguration(response.data);
    setPolicy({ enabled: response.data.policy.enabled, payment_scope: response.data.policy.payment_scope });
  }, []);
  useEffect(() => { void load().catch((value) => setError(getApiErrorMessage(value))); }, [load]);

  async function save(action: () => Promise<unknown>, message: string) {
    if (inFlight.current || !configuration?.permissions.can_manage_configuration) return;
    inFlight.current = true; setBusy(true); setError(null); setNotice(null);
    try { await action(); await load(); setNotice(message); }
    catch (value) { setError(getApiErrorMessage(value)); }
    finally { inFlight.current = false; setBusy(false); }
  }
  function editSeries(item?: FiscalSeries) {
    setEditingId(item?.id ?? null);
    setSeries(item ? {
      fiscal_issuer_id: item.fiscal_issuer_id, environment: item.environment, point_of_sale: item.point_of_sale,
      document_type: item.document_type, concept: item.concept, authorization_mode: item.authorization_mode,
      is_active: item.is_active, credential_reference: item.credential_reference, caea_reference: item.caea_reference,
    } : emptySeries);
    setShowSeries(true); setError(null);
  }
  function editMapping(method: PaymentMethod) {
    setMapping({ id: method.id, operational_reference: method.operational_reference ?? "", suggested_fiscal_issuer_id: method.suggested_fiscal_issuer_id ?? "" });
  }
  function submitPolicy(event: FormEvent) {
    event.preventDefault();
    void save(async () => {
      await updateFiscalPolicy({ ...policy, ...(reviewNote.trim() ? { accounting_review_note: reviewNote.trim() } : {}) });
      setReviewNote("");
    }, "Política guardada. Revisa las propuestas con esta configuración.");
  }

  if (!configuration) return <div className="page-stack"><h1>Configuración fiscal argentina</h1>{error ? <section className="error-state" role="alert">{error}<button className="secondary-button" onClick={() => { setError(null); void load().catch((value) => setError(getApiErrorMessage(value))); }}>Reintentar</button></section> : <div className="loading-state" role="status">Cargando configuración fiscal...</div>}</div>;
  const canManage = configuration.permissions.can_manage_configuration;
  const issuerName = (id: string | null) => configuration.issuers.find((item) => item.id === id)?.legal_name || configuration.issuers.find((item) => item.id === id)?.display_name || "Sin emisor sugerido";

  return <div className="page-stack sales-page fiscal-workspace">
    <section className="screen-heading"><div><Link className="back-link" href="/settings"><ArrowLeft size={18} /> Ajustes</Link><h1>Configuración fiscal argentina</h1><p>ARCA.2: prepara homologación, con validación externa pendiente de accesos.</p></div><Link className="secondary-button" href="/settings/sales/fiscal-issuers">Identidad de emisores</Link></section>
    {error ? <section className="error-state" role="alert">{error}</section> : null}
    {notice ? <p role="status">{notice}</p> : null}
    {!canManage ? <p className="purchase-reversal-warning">Consulta de configuración. Los cambios requieren un administrador de clínica o contador.</p> : null}
    <FiscalEmissionReadinessPanel configuration={configuration} />

    <form className="panel fiscal-card" onSubmit={submitPolicy}>
      <div className="section-heading"><h2>Política de selección</h2><span className="badge">{configuration.policy.enabled ? "Módulo activado" : "Módulo desactivado"}</span></div>
      <fieldset className="fiscal-fields" disabled={!canManage || busy}>
        <label className="checkbox-field"><input type="checkbox" checked={policy.enabled} onChange={(event) => setPolicy((value) => ({ ...value, enabled: event.target.checked }))} /><span>Activar revisión fiscal argentina</span></label>
        <label className="field" htmlFor="fiscal-payment-scope"><span>Cobros a contemplar</span><select id="fiscal-payment-scope" value={policy.payment_scope} onChange={(event) => setPolicy((value) => ({ ...value, payment_scope: event.target.value as FiscalPolicyInput["payment_scope"] }))}><option value="electronic_only">Sólo electrónicos clasificados</option><option value="all_payments">Todos los tipos de cobro</option></select></label>
        <p>Los electrónicos incluyen transferencias, tarjetas y billeteras. “Otro” requiere clasificación y revisión. El efectivo excluido se muestra por separado: excluirlo no lo declara exento ni resuelve la obligación de facturar.</p>
        <label className="field" htmlFor="fiscal-accounting-note"><span>Nota de revisión contable</span><textarea id="fiscal-accounting-note" maxLength={1000} rows={3} value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} placeholder="Registra el criterio contable antes de preparar producción" /></label>
        <p>{configuration.policy.accounting_reviewed_at ? `Última revisión: ${configuration.policy.accounting_reviewed_at}. ${configuration.policy.accounting_review_note ?? ""}` : "Revisión contable pendiente: producción permanece bloqueada."}</p>
        <p>Modificar la selección o activar el módulo requiere renovar la revisión contable.</p>
        {canManage ? <button className="primary-button" type="submit"><Save size={17} /> Guardar política</button> : null}
      </fieldset>
    </form>

    <section className="panel fiscal-card"><div className="section-heading"><h2>Ambientes y series fiscales</h2>{canManage ? <button className="secondary-button" type="button" disabled={busy} onClick={() => editSeries()}><Plus size={17} /> Nueva serie</button> : null}</div>
      <p>“Lista para revisión” describe la configuración. Preparar una serie no acredita autorización remota y producción permanece bloqueada.</p>
      {!configuration.series.length ? <p>No hay series. Crea una en homologación y completa la identidad fiscal del emisor.</p> : null}
      <div className="fiscal-cards">{configuration.series.map((item) => <article className="fiscal-summary-card" key={item.id}>
        <strong>{issuerName(item.fiscal_issuer_id)}</strong><span>CUIT {item.cuit_snapshot || "pendiente"}</span>
        <span>{item.environment === "homologation" ? "Homologación" : "Producción"} · Punto de venta {item.point_of_sale} · {item.document_type === "receipt_c" ? "Recibo C" : "Factura C"}</span>
        <span>Concepto {item.concept} · {item.authorization_mode} · {item.is_active ? "Activa" : "Inactiva"}</span>
        <span className="badge">{item.readiness === "ready" ? "Lista para revisión" : "Pendiente de completar"}</span>
        {item.pending_reasons.map((reason) => <small key={reason}>{reason}</small>)}
        {canManage ? <button className="secondary-button" type="button" disabled={busy} onClick={() => editSeries(item)}><Pencil size={16} /> Revisar serie</button> : null}
      </article>)}</div>
      {showSeries && canManage ? <form className="fiscal-card" onSubmit={(event) => { event.preventDefault(); void save(async () => { if (editingId) await updateFiscalSeries(editingId, series); else await createFiscalSeries(series); setShowSeries(false); }, "Serie guardada; verifica su estado pendiente o lista para revisión."); }}>
        <h3>{editingId ? "Editar serie" : "Nueva serie"}</h3><fieldset className="fiscal-fields" disabled={busy}><div className="fiscal-grid">
          <label className="field"><span>Emisor confirmado *</span><select required value={series.fiscal_issuer_id} onChange={(event) => setSeries((value) => ({ ...value, fiscal_issuer_id: event.target.value }))}><option value="">Seleccionar emisor</option>{configuration.issuers.map((issuer) => <option key={issuer.id} value={issuer.id}>{issuer.legal_name || issuer.display_name} · {issuer.cuit || "CUIT pendiente"}</option>)}</select></label>
          <label className="field"><span>Ambiente *</span><select value={series.environment} onChange={(event) => setSeries((value) => ({ ...value, environment: event.target.value as FiscalSeriesInput["environment"] }))}><option value="homologation">Homologación</option><option value="production">Producción (preparación, sin emisión)</option></select></label>
          <label className="field"><span>Punto de venta *</span><input required type="number" min={1} max={99999} value={series.point_of_sale || ""} onChange={(event) => setSeries((value) => ({ ...value, point_of_sale: Number(event.target.value) }))} /></label>
          <label className="field"><span>Tipo de comprobante</span><select value={series.document_type} onChange={(event) => setSeries((value) => ({ ...value, document_type: event.target.value as FiscalSeriesInput["document_type"] }))}><option value="receipt_c">Recibo C</option><option value="invoice_c">Factura C</option></select></label>
          <label className="field"><span>Concepto</span><select value={series.concept} onChange={(event) => setSeries((value) => ({ ...value, concept: Number(event.target.value) as 1 | 2 | 3 }))}><option value={1}>Productos</option><option value={2}>Servicios (incluye medicamentos)</option><option value={3}>Productos y servicios</option></select></label>
          <label className="field"><span>Modalidad prevista</span><select value={series.authorization_mode} onChange={(event) => setSeries((value) => ({ ...value, authorization_mode: event.target.value as "CAE" | "CAEA" }))}><option value="CAE">CAE</option><option value="CAEA">CAEA (contingencia futura)</option></select></label>
          <label className="field"><span>Referencia opaca de credencial</span><input maxLength={220} placeholder="opaque://identificador" pattern="opaque://[A-Za-z0-9][A-Za-z0-9._/-]{0,199}" value={series.credential_reference ?? ""} onChange={(event) => setSeries((value) => ({ ...value, credential_reference: event.target.value || null }))} /></label>
          <label className="field"><span>Referencia opaca CAEA</span><input maxLength={220} placeholder="opaque://identificador" pattern="opaque://[A-Za-z0-9][A-Za-z0-9._/-]{0,199}" value={series.caea_reference ?? ""} onChange={(event) => setSeries((value) => ({ ...value, caea_reference: event.target.value || null }))} /></label>
        </div><p>Guarda únicamente identificadores opacos. No ingreses certificados, claves, contraseñas ni tokens.</p><label className="checkbox-field"><input type="checkbox" checked={series.is_active} onChange={(event) => setSeries((value) => ({ ...value, is_active: event.target.checked }))} /><span>Serie activa para revisión</span></label><div className="purchase-attachment-actions"><button className="secondary-button" type="button" onClick={() => setShowSeries(false)}>Cerrar</button><button className="primary-button" type="submit">Guardar serie</button></div></fieldset>
      </form> : null}
    </section>

    <section className="panel fiscal-card"><h2>Atribución sugerida de formas de pago</h2><p>La cuenta operativa y el emisor sugerido ayudan a revisar cobros futuros. Cada propuesta requiere confirmar el emisor; no modifican los cobros históricos ni reservas aprobadas.</p>
      <div className="fiscal-cards">{configuration.payment_methods.map((method) => <article className="fiscal-summary-card" key={method.id}><strong>{method.label}</strong><span>{method.operational_reference || "Sin referencia operativa"}</span><span>{issuerName(method.suggested_fiscal_issuer_id ?? null)}</span>{canManage ? <button className="secondary-button" type="button" disabled={busy} onClick={() => editMapping(method)}>Revisar atribución</button> : null}</article>)}</div>
      {mapping && canManage ? <form className="fiscal-card" onSubmit={(event) => { event.preventDefault(); void save(async () => { await updatePaymentMethod(mapping.id, { operational_reference: mapping.operational_reference.trim() || null, suggested_fiscal_issuer_id: mapping.suggested_fiscal_issuer_id || null }); setMapping(null); }, "Sugerencia guardada para propuestas futuras."); }}><fieldset className="fiscal-fields" disabled={busy}>
        <label className="field"><span>Cuenta o referencia operativa no secreta</span><input maxLength={255} value={mapping.operational_reference} onChange={(event) => setMapping({ ...mapping, operational_reference: event.target.value })} /></label>
        <label className="field"><span>Emisor sugerido</span><select value={mapping.suggested_fiscal_issuer_id} onChange={(event) => setMapping({ ...mapping, suggested_fiscal_issuer_id: event.target.value })}><option value="">Sin sugerencia</option>{configuration.issuers.filter((issuer) => issuer.is_active).map((issuer) => <option key={issuer.id} value={issuer.id}>{issuer.legal_name || issuer.display_name}</option>)}</select></label>
        <div className="purchase-attachment-actions"><button className="secondary-button" type="button" onClick={() => setMapping(null)}>Cerrar</button><button className="primary-button" type="submit">Guardar sugerencia</button></div>
      </fieldset></form> : null}
    </section>
  </div>;
}

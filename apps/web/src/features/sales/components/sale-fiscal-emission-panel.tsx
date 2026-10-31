"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { getApiErrorMessage } from "@/lib/api";
import { getSaleFiscalReview } from "@/services/fiscal";
import { getFiscalEmissionFile, getFiscalEmissions, issueFiscalEmission, prepareFiscalEmission, reconcileFiscalEmission, regenerateFiscalEmission } from "@/services/arca-emission";
import type { Sale } from "@/types/api";
import type { FiscalEmission, FiscalEmissions } from "@/types/arca-emission";
import type { FiscalProposal } from "@/types/fiscal";
import { buildEmissionPayload, emissionLinesTotal, emissionLineTotal, emissionStatusLabel, initialEmissionForm, type EmissionForm } from "./arca-emission-helpers";

export function SaleFiscalEmissionPanel({ sale, onUpdated }: { sale: Sale; onUpdated: () => Promise<void> }) {
  const [emissions, setEmissions] = useState<FiscalEmissions | null>(null);
  const [proposals, setProposals] = useState<FiscalProposal[]>([]);
  const [preparing, setPreparing] = useState<FiscalProposal | null>(null);
  const [form, setFormState] = useState<EmissionForm | null>(null);
  const [prepareConfirmed, setPrepareConfirmed] = useState(false);
  const [supersedesId, setSupersedesId] = useState<string | null>(null);
  const [issueConfirmed, setIssueConfirmed] = useState<string[]>([]);
  const [retryConfirmed, setRetryConfirmed] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const writeInFlight = useRef(false);
  const intentKeys = useRef(new Map<string, string>());

  function setForm(value: EmissionForm | null) {
    setFormState(value); setPrepareConfirmed(false);
  }

  const load = useCallback(async () => {
    const [operations, review] = await Promise.all([getFiscalEmissions(sale.id), getSaleFiscalReview(sale.id)]);
    setEmissions(operations.data); setProposals(review.data.proposals);
  }, [sale.id]);
  useEffect(() => { void load().catch((value) => setError(getApiErrorMessage(value))); }, [load, sale]);

  async function mutate(action: () => Promise<unknown>, message: string) {
    if (writeInFlight.current) return;
    writeInFlight.current = true; setBusy(true); setError(null); setNotice(null);
    try { await action(); await load(); await onUpdated(); setIssueConfirmed([]); setRetryConfirmed([]); setNotice(message); }
    catch (value) {
      setError(getApiErrorMessage(value));
      // A failed HTTP response is not evidence that ARCA did not authorize.
      // Recover the durable operation instead of creating another intention.
      await load().then(onUpdated).catch(() => {});
    } finally { writeInFlight.current = false; setBusy(false); }
  }

  function openPrepare(proposal: FiscalProposal, supersedes?: string) {
    if (!emissions?.permissions.can_prepare) return;
    setPreparing(proposal); setForm(initialEmissionForm(proposal)); setPrepareConfirmed(false); setSupersedesId(supersedes ?? null); setError(null);
  }
  async function submitPrepare(event: FormEvent) {
    event.preventDefault();
    if (!form || !preparing || !prepareConfirmed || !emissions?.permissions.can_prepare) return;
    try {
      const fiscalData = buildEmissionPayload(preparing, form);
      const fingerprint = `${preparing.id}:${supersedesId ?? ""}:${JSON.stringify(fiscalData)}`;
      let key = intentKeys.current.get(fingerprint);
      if (!key) { key = crypto.randomUUID(); intentKeys.current.set(fingerprint, key); }
      await mutate(async () => { await prepareFiscalEmission(sale.id, preparing.id, fiscalData, key, supersedesId); setPreparing(null); setForm(null); }, "Intención fiscal guardada sin enviar. Su identidad y sus importes quedaron congelados.");
    } catch (value) { setError(value instanceof Error ? value.message : "Revisa los datos fiscales."); }
  }
  async function issue(operation: FiscalEmission) {
    if (!emissions?.permissions.can_issue || !operation.allowed_actions.issue || operation.status !== "prepared" || !issueConfirmed.includes(operation.id)) return;
    await mutate(() => issueFiscalEmission(sale.id, operation.id), "Operación procesada. Revisa su estado durable y el archivo; no repitas la emisión para resolver un resultado incierto.");
  }
  async function download(operation: FiscalEmission, versionId?: string) {
    setError(null);
    try {
      const response = await getFiscalEmissionFile(sale.id, operation.id, versionId);
      const url = URL.createObjectURL(response.blob);
      const anchor = document.createElement("a"); anchor.href = url; anchor.download = response.filename ?? `comprobante-${operation.number ?? operation.id}.pdf`; anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (value) { setError(getApiErrorMessage(value)); }
  }
  function updateLine(index: number, key: "description" | "quantity" | "unit_price", value: string) {
    if (!form) return;
    setForm({ ...form, lines: form.lines.map((line, at) => {
      if (at !== index) return line;
      const updated = { ...line, [key]: value };
      if (key !== "description") { try { updated.total = emissionLineTotal(updated.quantity, updated.unit_price); } catch { updated.total = ""; } }
      return updated;
    }) });
  }

  if (!emissions) return <section className="panel fiscal-card"><h2>Emisión electrónica</h2>{error ? <div className="error-state" role="alert">{error}<button className="secondary-button" type="button" onClick={() => void load().catch((value) => setError(getApiErrorMessage(value)))}>Reintentar operaciones</button></div> : <p role="status">Cargando intenciones fiscales...</p>}</section>;
  const ownIssuer = emissions.permissions.own_issuer_id;
  const canPrepare = (proposal: FiscalProposal) => emissions.permissions.can_prepare && (!ownIssuer || proposal.fiscal_issuer_id === ownIssuer) && (proposal.status === "approved" || proposal.status === "rejected") && !emissions.operations.some((operation) => operation.proposal_id === proposal.id && operation.status !== "rejected");
  let formTotal = "Pendiente de completar";
  if (form) { try { formTotal = emissionLinesTotal(form.lines); } catch { /* Incomplete inputs remain editable. */ } }

  return <section className="panel fiscal-card fiscal-workspace" aria-label="Emisión electrónica ARCA">
    <div className="section-heading"><div><h2>Emisión electrónica</h2><p>Homologación externa pendiente de accesos y validación. Producción permanece bloqueada.</p></div><button className="secondary-button" type="button" disabled={busy} onClick={() => void load().catch((value) => setError(getApiErrorMessage(value)))}>Actualizar operaciones</button></div>
    <p>Aprobar una propuesta reserva cobros. Preparar una intención congela los datos. Sólo la acción explícita de envío puede solicitar un CAE.</p>
    {error ? <div className="error-state" role="alert">{error}</div> : null}{notice ? <p role="status">{notice}</p> : null}
    {!emissions.permissions.can_prepare ? <p>Consulta de operaciones. Tu rol no permite preparar ni enviar comprobantes.</p> : null}
    {!emissions.operations.length ? <p>No hay intenciones de emisión registradas. Completa los datos de una propuesta aprobada.</p> : null}
    <div className="fiscal-cards">{proposals.filter((proposal) => canPrepare(proposal) && !emissions.operations.some((operation) => operation.proposal_id === proposal.id)).map((proposal) => <article className="fiscal-summary-card" key={proposal.id}><strong>Propuesta aprobada · ARS {proposal.total_ars}</strong><p>{proposal.fiscal_description}</p><small>{proposal.id}</small><button className="secondary-button" type="button" disabled={busy} onClick={() => openPrepare(proposal)}>Completar intención fiscal</button></article>)}</div>

    {preparing && form ? <form className="fiscal-card" aria-label="Completar intención fiscal" onSubmit={submitPrepare}><h3>Intención de homologación · ARS {preparing.total_ars}</h3>{supersedesId ? <p>Corrección explícita de la intención rechazada {supersedesId}. Se creará otra intención auditada; la solicitud anterior se conserva.</p> : null}<p>Los cobros, la aprobación histórica y el total reservado permanecen vinculados a esta intención. El detalle debe representar exactamente esta porción.</p><fieldset className="fiscal-fields" disabled={busy}>
      <div className="fiscal-summary-card"><strong>Emisor confirmado en la aprobación</strong><span>{String((preparing.snapshot.issuer as Record<string, unknown> | undefined)?.legal_name ?? "Identidad pendiente")}</span><span>CUIT {String((preparing.snapshot.issuer as Record<string, unknown> | undefined)?.cuit ?? "pendiente")}</span></div>
      <p>{String((preparing.snapshot.issuer as Record<string, unknown> | undefined)?.tax_condition ?? "Condición fiscal pendiente")} · Homologación · PV {String((preparing.snapshot.series as Record<string, unknown> | undefined)?.point_of_sale ?? "pendiente")} · {(preparing.snapshot.series as Record<string, unknown> | undefined)?.document_type === "invoice_c" ? "Factura C" : "Recibo C"} · Concepto {preparing.concept}</p>
      <div className="fiscal-grid"><label className="field" htmlFor="emission-fiscal-address"><span>Domicilio fiscal del emisor *</span><input id="emission-fiscal-address" required maxLength={500} value={form.fiscal_address} onChange={(event) => setForm({ ...form, fiscal_address: event.target.value })} /></label><label className="field" htmlFor="emission-gross-income"><span>Inscripción en ingresos brutos</span><input id="emission-gross-income" maxLength={120} value={form.gross_income_registration} onChange={(event) => setForm({ ...form, gross_income_registration: event.target.value })} /></label><label className="field" htmlFor="emission-activity-start"><span>Inicio de actividades</span><input id="emission-activity-start" type="date" value={form.activity_start_date} onChange={(event) => setForm({ ...form, activity_start_date: event.target.value })} /></label></div>
      <label className="field" htmlFor="emission-issuer-note"><span>Revisión de datos fiscales no aplicables</span><textarea id="emission-issuer-note" maxLength={1000} rows={2} value={form.fiscal_data_review_note} onChange={(event) => setForm({ ...form, fiscal_data_review_note: event.target.value })} /><small>Obligatoria si ingresos brutos o inicio de actividades no corresponden. No se asignan valores ficticios.</small></label>
      <h4>Receptor confirmado</h4><p>El documento libre del cliente no determina su tipo fiscal. Confirma los códigos conforme a los parámetros y la revisión contable.</p>
      <div className="fiscal-grid"><label className="field" htmlFor="emission-receiver-name"><span>Nombre o razón social *</span><input id="emission-receiver-name" required maxLength={255} value={form.receiver_name} onChange={(event) => setForm({ ...form, receiver_name: event.target.value })} /></label><label className="field" htmlFor="emission-receiver-address"><span>Domicilio del receptor *</span><input id="emission-receiver-address" required maxLength={500} value={form.receiver_address} onChange={(event) => setForm({ ...form, receiver_address: event.target.value })} /></label>
      <label className="field" htmlFor="emission-consumer-final"><span>Condición de consumidor final *</span><select id="emission-consumer-final" required value={form.consumer_final} onChange={(event) => { const value = event.target.value as EmissionForm["consumer_final"]; setForm({ ...form, consumer_final: value, iva_condition_id: value === "yes" ? "5" : "", ...(value !== "yes" && form.document_type === "99" ? { document_type: "", document_number: "" } : {}) }); }}><option value="">Confirmar explícitamente</option><option value="yes">Es consumidor final</option><option value="no">Otra condición de IVA</option></select></label>
      <label className="field" htmlFor="emission-doc-type"><span>Código de tipo de documento *</span><input id="emission-doc-type" inputMode="numeric" pattern="[0-9]+" required value={form.document_type} onChange={(event) => setForm({ ...form, document_type: event.target.value })} /></label><label className="field" htmlFor="emission-doc-number"><span>Número de documento *</span><input id="emission-doc-number" inputMode="numeric" pattern="[0-9]+" maxLength={11} required value={form.document_number} onChange={(event) => setForm({ ...form, document_number: event.target.value })} /></label><label className="field" htmlFor="emission-vat-condition"><span>Código de condición IVA del receptor *</span><input id="emission-vat-condition" inputMode="numeric" pattern="[0-9]+" required value={form.iva_condition_id} onChange={(event) => setForm({ ...form, iva_condition_id: event.target.value })} /></label></div>
      <label className="checkbox-field"><input type="checkbox" disabled={form.consumer_final !== "yes"} checked={form.document_type === "99" && form.document_number === "0"} onChange={(event) => setForm({ ...form, document_type: event.target.checked ? "99" : "", document_number: event.target.checked ? "0" : "" })} /><span>Confirmo que corresponde receptor sin identificar (99/0), como consumidor final revisado.</span></label>
      <div className="fiscal-grid"><label className="field" htmlFor="emission-voucher-date"><span>Fecha de emisión *</span><input id="emission-voucher-date" type="date" required value={form.voucher_date} onChange={(event) => setForm({ ...form, voucher_date: event.target.value })} /></label>{preparing.concept !== 1 ? <><label className="field" htmlFor="emission-service-from"><span>Prestación desde *</span><input id="emission-service-from" type="date" required value={form.service_from} onChange={(event) => setForm({ ...form, service_from: event.target.value })} /></label><label className="field" htmlFor="emission-service-to"><span>Prestación hasta *</span><input id="emission-service-to" type="date" required value={form.service_to} onChange={(event) => setForm({ ...form, service_to: event.target.value })} /></label><label className="field" htmlFor="emission-payment-due"><span>Vencimiento de pago *</span><input id="emission-payment-due" type="date" required value={form.payment_due} onChange={(event) => setForm({ ...form, payment_due: event.target.value })} /></label></> : null}</div>
      <h4>Detalle representado en el comprobante</h4>{form.lines.map((line, index) => <div className="fiscal-summary-card" key={index}><label className="field" htmlFor={`emission-line-description-${index}`}><span>Descripción fiscal {index + 1} *</span><textarea id={`emission-line-description-${index}`} required maxLength={2000} rows={3} value={line.description} onChange={(event) => updateLine(index, "description", event.target.value)} /></label><div className="fiscal-grid"><label className="field" htmlFor={`emission-line-quantity-${index}`}><span>Cantidad *</span><input id={`emission-line-quantity-${index}`} required inputMode="decimal" value={line.quantity} onChange={(event) => updateLine(index, "quantity", event.target.value)} /></label><label className="field" htmlFor={`emission-line-price-${index}`}><span>Precio unitario ARS *</span><input id={`emission-line-price-${index}`} required inputMode="decimal" value={line.unit_price} onChange={(event) => updateLine(index, "unit_price", event.target.value)} /></label><strong>Importe ARS {line.total || "pendiente"}</strong></div>{form.lines.length > 1 ? <button className="secondary-button" type="button" onClick={() => setForm({ ...form, lines: form.lines.filter((_, at) => at !== index) })}>Quitar detalle {index + 1}</button> : null}</div>)}
      <button className="secondary-button" type="button" disabled={form.lines.length >= 200} onClick={() => setForm({ ...form, lines: [...form.lines, { description: "", quantity: "1", unit_price: "", total: "" }] })}>Añadir detalle de esta porción</button><strong>Total representado: ARS {formTotal} · Total reservado: ARS {preparing.total_ars}</strong>
      <label className="checkbox-field"><input type="checkbox" checked={prepareConfirmed} onChange={(event) => setPrepareConfirmed(event.target.checked)} /><span>Confirmo identidad, receptor, fechas y detalle por el total reservado. Guardar esta intención todavía no solicita un CAE.</span></label><div className="purchase-attachment-actions"><button className="secondary-button" type="button" onClick={() => { setPreparing(null); setForm(null); }}>Cerrar sin preparar</button><button className="primary-button" type="submit" disabled={!prepareConfirmed}>Guardar intención sin enviar</button></div>
    </fieldset></form> : null}

    <div className="fiscal-card">{emissions.operations.map((operation) => <article className="fiscal-summary-card" key={operation.id} aria-label={`Emisión ${operation.id}`}><div className="section-heading"><strong>{emissionStatusLabel(operation.status)}</strong><span className="badge">{operation.environment === "homologation" ? "HOMOLOGACIÓN — SIN VALIDEZ FISCAL" : "Producción bloqueada"}</span></div><span>{operation.business_snapshot.issuer.legal_name} · CUIT {operation.business_snapshot.issuer.cuit}</span><span>PV {operation.business_snapshot.point_of_sale} · {operation.business_snapshot.document_type === 11 ? "Factura C" : "Recibo C"} · Número {operation.number ?? "aún no asignado"} · ARS {operation.business_snapshot.total}</span><span>Receptor: {operation.business_snapshot.receiver.name} · Documento {operation.business_snapshot.receiver.document_type}/{operation.business_snapshot.receiver.document_number}</span><small>Operación {operation.id} · Propuesta {operation.proposal_id}</small>
      <details className="fiscal-card"><summary>Revisar datos fiscales congelados</summary><div className="fiscal-summary-card"><span>Emisor: {operation.business_snapshot.issuer.legal_name} · {operation.business_snapshot.issuer.tax_condition}</span><span>Domicilio fiscal: {operation.business_snapshot.issuer.fiscal_address}</span><span>Ingresos brutos: {operation.business_snapshot.issuer.gross_income_registration || "No informado"} · Inicio de actividades: {operation.business_snapshot.issuer.activity_start_date || "No informado"}</span>{operation.business_snapshot.issuer.fiscal_data_review_note ? <span>Revisión: {operation.business_snapshot.issuer.fiscal_data_review_note}</span> : null}<span>Receptor: {operation.business_snapshot.receiver.name} · Domicilio: {operation.business_snapshot.receiver.address}</span><span>Condición IVA: {operation.business_snapshot.receiver.iva_condition_id} · {operation.business_snapshot.receiver.consumer_final ? "Consumidor final confirmado" : "Otra condición confirmada"}</span><span>Fecha: {operation.business_snapshot.voucher_date} · Concepto: {operation.business_snapshot.concept}</span>{operation.business_snapshot.concept !== 1 ? <span>Prestación: {operation.business_snapshot.service_from} al {operation.business_snapshot.service_to} · Vencimiento de pago: {operation.business_snapshot.payment_due}</span> : null}{operation.business_snapshot.lines.map((line, index) => <p key={index}>{line.description} · Cantidad {line.quantity} · Precio ARS {line.unit_price} · Total ARS {line.total}</p>)}<strong>Total documentado ARS {operation.business_snapshot.total} · PES · Cotización {operation.business_snapshot.exchange_rate}</strong></div></details>
      {operation.status === "authorized" ? <><strong>CAE {operation.cae} · Vencimiento {operation.cae_expiry}</strong><span>{operation.file_status === "ready" ? "Archivo disponible" : "Autorizado, archivo pendiente"}</span><p>Regenerar el archivo conserva el CAE y el número; no solicita otra autorización.</p></> : operation.status === "unknown" || operation.status === "processing" || operation.status === "conflict" ? <p className="purchase-reversal-warning">Conserva el número, la solicitud y las reservas. Reconcilia la operación existente antes de avanzar la serie. No canceles ni prepares otra emisión para estos cobros.</p> : operation.status === "rejected" ? <p>El rechazo definitivo se conserva. Corregirlo requiere una intención nueva y auditada; no se modifica esta solicitud.</p> : null}
      {operation.status === "rejected" && proposals.some((proposal) => proposal.id === operation.proposal_id && canPrepare(proposal)) ? <button className="secondary-button" type="button" disabled={busy} onClick={() => { const proposal = proposals.find((item) => item.id === operation.proposal_id); if (proposal) openPrepare(proposal, operation.id); }}>Preparar corrección de esta intención rechazada</button> : null}
      {operation.diagnostics.map((diagnostic, index) => <p role="status" key={`${diagnostic.code}:${index}`}>{diagnostic.message}</p>)}{operation.next_action_at ? <small>Próxima acción permitida: {operation.next_action_at}</small> : null}
      {operation.allowed_actions.issue && emissions.permissions.can_issue && operation.status === "prepared" ? <div className="fiscal-card"><label className="checkbox-field"><input type="checkbox" checked={issueConfirmed.includes(operation.id)} disabled={busy} onChange={(event) => setIssueConfirmed((ids) => event.target.checked ? [...ids, operation.id] : ids.filter((id) => id !== operation.id))} /><span>Confirmo enviar esta intención de homologación una sola vez. No implica habilitación productiva.</span></label><button className="primary-button" type="button" disabled={busy || !issueConfirmed.includes(operation.id)} onClick={() => void issue(operation)}>Solicitar CAE de esta intención</button></div> : null}
      {operation.allowed_actions.retry_same_request && emissions.permissions.can_reconcile ? <div className="fiscal-card"><label className="checkbox-field"><input type="checkbox" checked={retryConfirmed.includes(operation.id)} disabled={busy} onChange={(event) => setRetryConfirmed((ids) => event.target.checked ? [...ids, operation.id] : ids.filter((id) => id !== operation.id))} /><span>Confirmo conservar exactamente el número y la solicitud persistidos. El servidor consultará su autorización antes de permitir el reenvío.</span></label><button className="secondary-button" type="button" disabled={busy || !retryConfirmed.includes(operation.id)} onClick={() => { if (!retryConfirmed.includes(operation.id)) return; void mutate(() => reconcileFiscalEmission(sale.id, operation.id, true), "Recuperación solicitada con la misma identidad y el mismo número. Revisa el resultado persistido."); }}>Reenviar exactamente la solicitud y número persistidos</button></div> : null}
      <div className="purchase-attachment-actions">{operation.allowed_actions.reconcile && emissions.permissions.can_reconcile ? <button className="secondary-button" type="button" disabled={busy} onClick={() => void mutate(() => reconcileFiscalEmission(sale.id, operation.id), "Reconciliación consultada para la misma serie y número. Revisa su resultado.")}>Reconciliar resultado existente</button> : null}{operation.allowed_actions.regenerate && emissions.permissions.can_regenerate && operation.status === "authorized" ? <button className="secondary-button" type="button" disabled={busy} onClick={() => void mutate(() => regenerateFiscalEmission(sale.id, operation.id), "Regeneración de archivo procesada sin volver a emitir.")}>Regenerar PDF y QR</button> : null}{operation.allowed_actions.download && operation.status === "authorized" && operation.file_status === "ready" ? <button className="secondary-button" type="button" onClick={() => void download(operation)}>Descargar comprobante</button> : null}</div>
      <details><summary>Historial de intentos ({operation.attempts.length}) y archivos ({operation.file_versions.length})</summary>{operation.attempts.map((attempt, index) => <p key={index}>{attempt.created_at} · {attempt.action} · {attempt.outcome}</p>)}{operation.file_versions.map((version) => <div className="fiscal-card" key={version.id}><small>{version.created_at} · SHA256 {version.sha256}</small>{operation.allowed_actions.download ? <button className="secondary-button" type="button" onClick={() => void download(operation, version.id)}>Descargar versión {version.id}</button> : null}</div>)}</details>
    </article>)}</div>
  </section>;
}

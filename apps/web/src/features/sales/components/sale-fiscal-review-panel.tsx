"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { getApiErrorMessage } from "@/lib/api";
import { allocateManualFiscalDocument, approveFiscalProposal, cancelFiscalProposal, generateFiscalProposals, getFiscalConfiguration, getSaleFiscalReview, updateFiscalProposal } from "@/services/fiscal";
import type { Sale, SaleFiscalDocument } from "@/types/api";
import type { FiscalBlocker, FiscalConfiguration, FiscalProposal, FiscalReview } from "@/types/fiscal";
import { canApproveFiscalProposal, canReviewFiscalProposal, fiscalBlockerAction, fiscalDocumentStatusLabel, fiscalPaymentStatusLabel, fiscalProposalIdentity, fiscalProposalPaymentAmount, fiscalProposalStatusLabel, selectableFiscalPayments, selectedFiscalTotal } from "./fiscal-review-helpers";

export function SaleFiscalReviewPanel({ sale, onUpdated }: { sale: Sale; onUpdated?: () => Promise<void> }) {
  const [review, setReview] = useState<FiscalReview | null>(null);
  const [configuration, setConfiguration] = useState<FiscalConfiguration | null>(null);
  const [editing, setEditing] = useState<FiscalProposal | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [seriesId, setSeriesId] = useState("");
  const [description, setDescription] = useState("");
  const [paymentIds, setPaymentIds] = useState<string[]>([]);
  const [confirmed, setConfirmed] = useState<string[]>([]);
  const [cancelling, setCancelling] = useState<FiscalProposal | null>(null);
  const [reason, setReason] = useState("");
  const [allocatingDocument, setAllocatingDocument] = useState<SaleFiscalDocument | null>(null);
  const [manualPaymentIds, setManualPaymentIds] = useState<string[]>([]);
  const [manualConfirmed, setManualConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const writeInFlight = useRef(false);
  const approvalKeys = useRef(new Map<string, string>());
  const allocationKeys = useRef(new Map<string, string>());

  const load = useCallback(async () => {
    const [reviewResponse, configurationResponse] = await Promise.all([getSaleFiscalReview(sale.id), getFiscalConfiguration()]);
    setReview(reviewResponse.data); setConfiguration(configurationResponse.data);
  }, [sale.id]);
  useEffect(() => { void load().catch((value) => setError(getApiErrorMessage(value))); }, [load, sale]);

  async function mutate(action: () => Promise<unknown>, message: string) {
    if (writeInFlight.current) return;
    writeInFlight.current = true; setBusy(true); setError(null); setNotice(null);
    try { await action(); setConfirmed([]); await load(); await onUpdated?.(); setNotice(message); }
    catch (value) { setError(getApiErrorMessage(value)); }
    finally { writeInFlight.current = false; setBusy(false); }
  }
  function openForm(proposal?: FiscalProposal) {
    if (!review?.permissions.can_generate || proposal && !canReviewFiscalProposal(review, proposal)) return;
    setEditing(proposal ?? null); setSeriesId(proposal?.fiscal_series_id ?? "");
    setDescription(proposal?.fiscal_description ?? ""); setPaymentIds(proposal?.payment_ids ?? []);
    setShowForm(true); setError(null);
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!review?.permissions.can_generate) return;
    if (!seriesId || !description.trim() || !paymentIds.length) { setError("Confirma emisor y serie, descripción fiscal y al menos un cobro íntegro."); return; }
    const payload = { fiscal_series_id: seriesId, fiscal_description: description.trim(), payment_ids: paymentIds };
    await mutate(async () => { if (editing) await updateFiscalProposal(sale.id, editing.id, payload); else await generateFiscalProposals(sale.id, payload); setShowForm(false); }, "Borrador guardado. Revisa el contenido antes de aprobar la reserva.");
  }
  async function approve(proposal: FiscalProposal) {
    if (!review || !canApproveFiscalProposal(review, proposal) || !confirmed.includes(proposal.id)) return;
    const identity = `${proposal.id}:${proposal.content_hash}`;
    let key = approvalKeys.current.get(identity);
    if (!key) { key = crypto.randomUUID(); approvalKeys.current.set(identity, key); }
    await mutate(() => approveFiscalProposal(sale.id, proposal, key), "Propuesta aprobada y cobros reservados. No se emitió un comprobante ARCA.");
  }

  if (!review || !configuration) return <section className="panel fiscal-card"><h2>Revisión fiscal argentina</h2>{error ? <div className="error-state" role="alert">{error}<button className="secondary-button" type="button" onClick={() => { setError(null); void load().catch((value) => setError(getApiErrorMessage(value))); }}>Reintentar revisión</button></div> : <p role="status">Cargando elegibilidad fiscal...</p>}</section>;
  const ownIssuerId = review.permissions.own_issuer_id;
  const availableSeries = configuration.series.filter((item) => item.is_active && (!ownIssuerId || item.fiscal_issuer_id === ownIssuerId));
  const selectedSeries = configuration.series.find((item) => item.id === seriesId);
  const selectedIssuer = configuration.issuers.find((item) => item.id === selectedSeries?.fiscal_issuer_id);
  const eligiblePayments = selectableFiscalPayments(review.payments, editing ?? undefined);
  const manualTotal = selectedFiscalTotal(review.payments, manualPaymentIds);
  const hasSentReservations = review.proposals.some((proposal) => ["sent", "unknown", "authorized", "caea_pending"].includes(proposal.status));
  const hasUnsentReservations = review.proposals.some((proposal) => proposal.status === "approved");
  const issuerName = (id: string) => configuration.issuers.find((issuer) => issuer.id === id)?.legal_name || configuration.issuers.find((issuer) => issuer.id === id)?.display_name || "Emisor histórico";

  return <section className="panel fiscal-card fiscal-workspace" aria-label="Revisión fiscal argentina">
    <div className="section-heading"><div><h2>Revisión fiscal argentina</h2><p>Los borradores no consumen cobros. Aprobar reserva importes; ARCA.2 requiere preparar y confirmar una intención de emisión aparte.</p></div>{review.permissions.can_manage_configuration ? <Link className="secondary-button" href="/settings/sales/fiscal">Ajustes fiscales</Link> : null}</div>
    {error ? <div className="error-state" role="alert">{error}</div> : null}
    {notice ? <p role="status">{notice}</p> : null}
    {!review.permissions.can_generate ? <p>Consulta fiscal. Tu rol no permite modificar propuestas.</p> : ownIssuerId ? <p>Puedes revisar y aprobar únicamente propuestas de tu emisor vinculado.</p> : null}
    <FiscalBlockers blockers={review.eligibility.blockers} />
    <div className="fiscal-totals" aria-label="Totales de revisión"><div><span>Elegibles</span><strong>ARS {review.totals.available_ars}</strong></div><div><span>Propuestos</span><strong>ARS {review.totals.proposed_ars}</strong></div><div><span>Reservados</span><strong>ARS {review.totals.committed_ars}</strong></div><div><span>Excluidos</span><strong>ARS {review.totals.excluded_ars}</strong></div><div><span>Pendientes</span><strong>ARS {review.totals.pending_ars}</strong></div></div>
    <p>El efectivo excluido no se declara exento. Los importes se revisan en ARS, sin conversión de moneda.</p>
    <div className="fiscal-cards" aria-label="Clasificación fiscal de cobros">{review.payments.map((payment) => <article className="fiscal-summary-card" key={payment.payment_id}><strong>{payment.label} · ARS {payment.amount_ars}</strong><span className="badge">{fiscalPaymentStatusLabel(payment.status)}</span>{payment.status === "committed" ? <span>Consulta la propuesta o el comprobante antes de modificar este cobro.</span> : payment.reason ? <span>{payment.reason}</span> : null}<small>{payment.suggested_fiscal_issuer_id ? `Sugerencia: ${issuerName(payment.suggested_fiscal_issuer_id)}. Requiere confirmación.` : "Sin emisor sugerido; requiere atribución fiscal."}</small></article>)}</div>
    {review.totals.committed_ars !== "0.00" && review.totals.committed_ars !== "0" ? <p className="purchase-reversal-warning">Hay imputaciones fiscales activas. {hasSentReservations ? "Las operaciones enviadas, inciertas o autorizadas conservan sus reservas; consulta o reconcilia la operación existente y revisa con el contador cualquier corrección fiscal. " : hasUnsentReservations ? "Antes de anular un cobro reservado o revertir esta venta, cancela explícitamente su propuesta aprobada aún no enviada. " : "Consulta el comprobante y sus imputaciones antes de modificar cobros o revertir esta venta. "}Las imputaciones de comprobantes manuales requieren revisión contable y no se liberan desde una propuesta.</p> : null}
    {review.permissions.can_generate ? <button className="secondary-button" type="button" disabled={busy || !review.eligibility.eligible} onClick={() => openForm()}>Preparar propuesta revisable</button> : null}

    {showForm && review.permissions.can_generate ? <form className="fiscal-card" aria-label="Revisar propuesta fiscal" onSubmit={submit}><h3>{editing ? "Corregir borrador" : "Confirmar atribución de cobros"}</h3><fieldset className="fiscal-fields" disabled={busy}>
      <label className="field" htmlFor="proposal-series"><span>Emisor y serie fiscal confirmados *</span><select id="proposal-series" required value={seriesId} onChange={(event) => setSeriesId(event.target.value)}><option value="">Seleccionar explícitamente</option>{availableSeries.map((item) => <option key={item.id} value={item.id}>{issuerName(item.fiscal_issuer_id)} · {item.cuit_snapshot || "CUIT pendiente"} · {item.environment === "homologation" ? "Homologación" : "Producción"} · PV {item.point_of_sale} · {item.document_type === "receipt_c" ? "Recibo C" : "Factura C"} · Concepto {item.concept}</option>)}</select></label>
      {selectedSeries ? <div className="fiscal-summary-card"><strong>{selectedIssuer?.legal_name || selectedIssuer?.display_name}</strong><span>CUIT {selectedSeries.cuit_snapshot || "pendiente"} · {selectedIssuer?.tax_condition || "Condición fiscal pendiente"}</span><span>{selectedSeries.authorization_mode} · {selectedSeries.readiness === "ready" ? "Lista para revisión" : "Configuración pendiente"}</span>{selectedSeries.pending_reasons.map((item) => <small key={item}>{item}</small>)}</div> : null}
      <label className="field" htmlFor="proposal-description"><span>Descripción fiscal confirmada *</span><textarea id="proposal-description" rows={3} maxLength={1000} required value={description} onChange={(event) => setDescription(event.target.value)} /></label>
      <fieldset className="fiscal-fields"><legend>Cobros íntegros a imputar *</legend>{eligiblePayments.map((payment) => <label className="checkbox-field" key={payment.payment_id}><input type="checkbox" checked={paymentIds.includes(payment.payment_id)} onChange={(event) => setPaymentIds((ids) => event.target.checked ? [...ids, payment.payment_id] : ids.filter((id) => id !== payment.payment_id))} /><span>{payment.label} · ARS {payment.amount_ars} · {fiscalPaymentStatusLabel(payment.status)}</span></label>)}</fieldset>
      <strong>Total de cobros seleccionados: ARS {selectedFiscalTotal(review.payments, paymentIds)}</strong><p>No se dividen cobros ni se atribuyen líneas automáticamente por la cuenta receptora.</p>
      <div className="purchase-attachment-actions"><button className="secondary-button" type="button" onClick={() => setShowForm(false)}>Cerrar revisión</button><button className="primary-button" type="submit">Guardar borrador sin reservar</button></div>
    </fieldset></form> : null}

    <div className="fiscal-card"><h3>Propuestas persistentes ({review.proposals.length})</h3>{!review.proposals.length ? <p>Aún no hay propuestas.</p> : null}{review.proposals.map((proposal) => {
      const manageable = canReviewFiscalProposal(review, proposal);
      const identity = fiscalProposalIdentity(proposal, configuration);
      return <article className="fiscal-summary-card" key={proposal.id} aria-label={`Propuesta ${proposal.id}`}><div className="section-heading"><strong>{identity.name} · ARS {proposal.total_ars}</strong><span className="badge">{fiscalProposalStatusLabel(proposal.status)}</span></div>
        <span>CUIT {identity.cuit} · {identity.taxCondition} · {identity.environment === "production" ? "Producción" : identity.environment === "homologation" ? "Homologación" : "Ambiente pendiente"} · PV {String(identity.pointOfSale)} · {identity.documentType === "invoice_c" ? "Factura C" : identity.documentType === "receipt_c" ? "Recibo C" : "Tipo pendiente"} · Concepto {String(identity.concept)}</span>
        <p>{proposal.fiscal_description}</p><small>{proposal.payment_ids.length} cobro(s) íntegro(s) · Identificador {proposal.id}</small>
        <ul className="fiscal-payment-list" aria-label="Cobros de la propuesta">{proposal.payment_ids.map((id) => { const payment = review.payments.find((item) => item.payment_id === id); return <li key={id}>{payment?.label ?? "Cobro histórico"} · ARS {fiscalProposalPaymentAmount(proposal, id, review)}</li>; })}</ul>
        {proposal.is_stale ? <p className="error-state" role="alert">Propuesta obsoleta. Revisa pagos, venta y configuración, y guarda el borrador antes de aprobar.</p> : null}<FiscalBlockers blockers={proposal.blockers} />
        {proposal.cancellation_reason ? <p>Cancelación: {proposal.cancellation_reason}</p> : null}
        {manageable && proposal.status === "draft" ? <div className="fiscal-card"><button className="secondary-button" type="button" disabled={busy} onClick={() => openForm(proposal)}>Revisar o corregir</button>
          <label className="checkbox-field"><input type="checkbox" disabled={busy || !canApproveFiscalProposal(review, proposal)} checked={confirmed.includes(proposal.id)} onChange={(event) => setConfirmed((ids) => event.target.checked ? [...ids, proposal.id] : ids.filter((id) => id !== proposal.id))} /><span>Confirmo emisor, CUIT, serie, descripción y cobros íntegros mostrados. Aprobar sólo reserva; no emite.</span></label>
          <button className="primary-button" type="button" disabled={busy || !confirmed.includes(proposal.id) || !canApproveFiscalProposal(review, proposal)} onClick={() => void approve(proposal)}>Aprobar y reservar cobros</button>
        </div> : null}
        {manageable && (proposal.status === "draft" || proposal.status === "approved") ? <button className="secondary-button" type="button" disabled={busy} onClick={() => { setCancelling(proposal); setReason(""); }}>Cancelar propuesta{proposal.status === "approved" ? " y liberar reserva" : ""}</button> : null}
      </article>;
    })}</div>
    {cancelling ? <form className="fiscal-card" aria-label="Cancelar propuesta fiscal" onSubmit={(event) => { event.preventDefault(); if (!reason.trim() || !canReviewFiscalProposal(review, cancelling)) return; void mutate(async () => { await cancelFiscalProposal(sale.id, cancelling.id, reason.trim()); setCancelling(null); }, "Propuesta cancelada. Sus reservas se liberaron; una nueva aprobación requiere una propuesta nueva."); }}><h3>Cancelar propuesta {cancelling.id}</h3><label className="field"><span>Motivo auditado *</span><textarea required maxLength={1000} rows={3} value={reason} onChange={(event) => setReason(event.target.value)} disabled={busy} /></label><p>Esta acción cancela una propuesta aún no enviada. No es una anulación fiscal ante ARCA.</p><div className="purchase-attachment-actions"><button className="secondary-button" type="button" disabled={busy} onClick={() => setCancelling(null)}>Volver</button><button className="danger-button" type="submit" disabled={busy || !reason.trim()}>Confirmar cancelación</button></div></form> : null}
    <details className="fiscal-card"><summary>Comprobantes registrados ({review.documents.length})</summary><p>Los adjuntos manuales conservan su panel e historial. Una propuesta aprobada no es un comprobante emitido.</p>
      <div className="fiscal-totals" aria-label="Totales de comprobantes activos">{sale.fiscal_document_totals?.map((total) => <div key={`${total.source}:${total.authorization_status}:${total.environment ?? "none"}`}><span>{documentEnvironmentLabel(total.source, total.environment)} · {fiscalDocumentStatusLabel(total.authorization_status)} · {total.count} comprobante(s) activo(s)</span><strong>ARS {total.total_ars}</strong></div>)}</div>
      {review.documents.map((document) => <article className="fiscal-summary-card" key={document.id}><strong>{document.issuer_name_snapshot}</strong><span>{document.document_type === "receipt_c" ? "Recibo C" : "Factura C"} · {document.document_number} · ARS {document.total_ars_snapshot}</span><span>{documentEnvironmentLabel(document.source, document.environment)} · {fiscalDocumentStatusLabel(document.authorization_status)} · {document.is_active ? "Activo" : "Histórico"}</span>
      {document.is_active && document.source === "manual" && review.permissions.can_approve && (!ownIssuerId || document.fiscal_issuer_id === ownIssuerId) && review.eligibility.blockers.some((blocker) => /manual/.test(blocker.code)) ? <button className="secondary-button" type="button" disabled={busy} onClick={() => { setAllocatingDocument(document); setManualPaymentIds([]); setManualConfirmed(false); }}>Regularizar imputación manual</button> : null}
    </article>)}</details>
    {allocatingDocument ? <form className="fiscal-card" aria-label="Regularizar comprobante manual" onSubmit={(event) => {
      event.preventDefault();
      if (!manualConfirmed || !manualPaymentIds.length || manualTotal !== allocatingDocument.total_ars_snapshot || !review.permissions.can_approve) return;
      const identity = `${allocatingDocument.id}:${[...manualPaymentIds].sort().join(":")}`;
      let key = allocationKeys.current.get(identity);
      if (!key) { key = crypto.randomUUID(); allocationKeys.current.set(identity, key); }
      void mutate(async () => { await allocateManualFiscalDocument(sale.id, allocatingDocument.id, manualPaymentIds, key); setAllocatingDocument(null); setManualPaymentIds([]); }, "Imputación del comprobante manual regularizada y auditada.");
    }}><h3>Regularizar comprobante {allocatingDocument.document_number}</h3><p>{allocatingDocument.issuer_name_snapshot} · CUIT/identificación {allocatingDocument.issuer_tax_id_snapshot} · Total ARS {allocatingDocument.total_ars_snapshot}</p><fieldset className="fiscal-fields" disabled={busy}><legend>Selecciona los cobros íntegros cubiertos por este comprobante</legend>{review.payments.filter((payment) => payment.status !== "committed").map((payment) => <label className="checkbox-field" key={payment.payment_id}><input type="checkbox" checked={manualPaymentIds.includes(payment.payment_id)} onChange={(event) => setManualPaymentIds((ids) => event.target.checked ? [...ids, payment.payment_id] : ids.filter((id) => id !== payment.payment_id))} /><span>{payment.label} · ARS {payment.amount_ars}</span></label>)}
      <strong>Total seleccionado: ARS {manualTotal}</strong><p>Debe coincidir exactamente con el total del comprobante. Incluye efectivo si el comprobante histórico lo cubre; no se divide ningún cobro.</p><label className="checkbox-field"><input type="checkbox" checked={manualConfirmed} onChange={(event) => setManualConfirmed(event.target.checked)} /><span>Confirmo la identidad fiscal y que este comprobante manual cubre los cobros seleccionados.</span></label><div className="purchase-attachment-actions"><button className="secondary-button" type="button" onClick={() => setAllocatingDocument(null)}>Volver sin regularizar</button><button className="primary-button" type="submit" disabled={!manualConfirmed || !manualPaymentIds.length || manualTotal !== allocatingDocument.total_ars_snapshot}>Confirmar imputación manual</button></div>
    </fieldset></form> : null}
  </section>;
}

function FiscalBlockers({ blockers }: { blockers: FiscalBlocker[] }) {
  return blockers.length ? <div className="fiscal-blockers" role="alert">{blockers.map((blocker) => <div key={`${blocker.code}:${blocker.message}`}><strong>{blocker.message}</strong><p>{fiscalBlockerAction(blocker.code)}</p></div>)}</div> : null;
}

function documentEnvironmentLabel(source: SaleFiscalDocument["source"], environment: SaleFiscalDocument["environment"]) {
  if (source === "manual") return "Registro manual";
  if (environment === "homologation") return "ARCA · Homologación · sin validez fiscal";
  if (environment === "production") return "ARCA · Producción";
  return "ARCA · Ambiente pendiente de verificar";
}

"use client";

import { AlertTriangle, Download, Eye, FileCheck2, FileUp, Settings2, X } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { useClinic } from "@/features/clinic/clinic-context";
import { formatPurchaseCurrency, formatPurchaseDate, formatPurchaseDateTime, formatPurchaseUser } from "@/features/purchases/components/purchase-helpers";
import { getApiErrorMessage } from "@/lib/api";
import { resolveMoneyPreferences } from "@/lib/money";
import { createSaleFiscalDocument, getFiscalIssuers, getSaleFiscalDocumentFile, updateSaleFiscalDocument } from "@/services/sales";
import type { FiscalDocumentType, FiscalIssuer, Sale } from "@/types/api";

export function SaleFiscalDocumentPanel({ sale, onUpdated }: { sale: Sale; onUpdated: () => Promise<void> }) {
  const { preferences } = useClinic();
  const moneyPreferences = resolveMoneyPreferences(preferences);
  const document = sale.fiscal_document;
  const [issuers, setIssuers] = useState<FiscalIssuer[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [issuerId, setIssuerId] = useState("");
  const [number, setNumber] = useState("");
  const [issueDate, setIssueDate] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getFiscalIssuers().then((response) => setIssuers(response.data)).catch(() => setIssuers([]));
  }, []);

  const eligible = useMemo(() => issuers.filter((issuer) => {
    if (issuer.id === document?.fiscal_issuer_id) return true;
    if (!issuer.is_active) return false;
    return Boolean(getIssuerDocumentPair(sale, issuer));
  }), [document?.fiscal_issuer_id, issuers, sale]);
  const selectedIssuer = eligible.find((issuer) => issuer.id === issuerId) ?? null;
  const hasActiveIssuers = issuers.some((issuer) => issuer.is_active);
  const selectedPair = document && selectedIssuer?.id === document.fiscal_issuer_id
    ? [document.document_type, document.document_code] as [FiscalDocumentType, string]
    : selectedIssuer ? getIssuerDocumentPair(sale, selectedIssuer) : null;

  function openForm() {
    const defaultIssuer = document
      ? eligible.find((item) => item.id === document.fiscal_issuer_id)
      : eligible[0];
    setIssuerId(defaultIssuer?.id ?? "");
    setNumber(document?.document_number ?? "");
    setIssueDate(document?.issue_date ?? localDate());
    setFile(null);
    setError(null);
    setShowForm(true);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!selectedIssuer || !selectedPair) { setError("Selecciona un emisor habilitado para esta venta."); return; }
    if (!number.trim() || !issueDate) { setError("Completa el número y la fecha del comprobante."); return; }
    if (!document && !file) { setError("Selecciona el archivo del comprobante."); return; }
    if (file) {
      const validation = await validateFiscalFile(file);
      if (validation) { setError(validation); return; }
    }
    setIsSaving(true); setError(null);
    const payload = {
      fiscal_issuer_id: selectedIssuer.id,
      document_type: selectedPair[0],
      document_code: selectedPair[1],
      document_number: number.trim(),
      issue_date: issueDate,
      file,
    };
    try {
      if (document) await updateSaleFiscalDocument(sale.id, payload);
      else await createSaleFiscalDocument(sale.id, payload);
      setShowForm(false); setFile(null);
      await onUpdated();
    } catch (value) { setError(getApiErrorMessage(value)); }
    finally { setIsSaving(false); }
  }

  async function openFile(download: boolean) {
    setError(null);
    try {
      const response = await getSaleFiscalDocumentFile(sale.id, download);
      const objectUrl = URL.createObjectURL(response.blob);
      if (download) {
        const anchor = window.document.createElement("a");
        anchor.href = objectUrl;
        anchor.download = response.filename ?? document?.original_filename ?? "comprobante";
        anchor.click();
      } else window.open(objectUrl, "_blank", "noopener,noreferrer");
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    } catch (value) { setError(getApiErrorMessage(value)); }
  }

  return <section className="panel purchase-attachment-panel sale-fiscal-panel">
    <div className="section-heading"><div><h2>Comprobante fiscal</h2><p>{labelFiscalStatus(sale.fiscal_status)}</p></div>{sale.fiscal_status ? <span className={`badge fiscal-status fiscal-status--${sale.fiscal_status}`}>{labelFiscalStatus(sale.fiscal_status)}</span> : null}</div>
    {sale.fiscal_status === "requires_attention" ? <div className="purchase-reversal-warning" role="alert"><AlertTriangle size={18} /><span>La venta fue revertida después de documentarse. El comprobante se conserva y requiere revisión manual; Vetflow no genera una nota de crédito.</span></div> : null}
    {document ? <>
      <div className="purchase-attachment-metadata fiscal-document-metadata">
        <div><span>Emisor</span><strong>{document.issuer_name_snapshot}</strong><small>{document.issuer_tax_id_snapshot}</small></div>
        <div><span>Comprobante</span><strong>{labelDocumentType(document.document_type)} {document.document_code}</strong><small>N.º {document.document_number}</small></div>
        <div><span>Fecha y total</span><strong>{formatPurchaseDate(document.issue_date)}</strong><small>{formatPurchaseCurrency(document.total_ars_snapshot, moneyPreferences)}</small></div>
        <div><span>Archivo</span><strong>{document.original_filename}</strong><small>{formatFileSize(document.size_bytes)} · {labelFileType(document.content_type)}</small></div>
        <div><span>Cargado por</span><strong>{formatPurchaseUser(document.uploaded_by_user_name, document.uploaded_by_user_email)}</strong><small>{formatPurchaseDateTime(document.uploaded_at)}</small></div>
      </div>
      <div className="purchase-attachment-actions"><button className="secondary-button" type="button" onClick={() => void openFile(false)}><Eye size={17} /> Ver</button><button className="secondary-button" type="button" onClick={() => void openFile(true)}><Download size={17} /> Descargar</button><button className="primary-button" type="button" onClick={openForm}><FileUp size={17} /> Corregir o reemplazar</button></div>
      {document.file_history.length ? <details className="purchase-attachment-history"><summary>Historial de archivos ({document.file_history.length})</summary>{document.file_history.map((item) => <div key={item.id}><strong>{item.original_filename}</strong><small>{formatPurchaseDateTime(item.uploaded_at)} · reemplazado {formatPurchaseDateTime(item.replaced_at)} por {formatPurchaseUser(item.replaced_by_user_name, item.replaced_by_user_email)}</small></div>)}</details> : null}
    </> : sale.status === "confirmed" ? <div className="purchase-empty-state"><FileCheck2 size={28} /><h3>Comprobante pendiente</h3><p>Registra el comprobante emitido manualmente fuera de Vetflow.</p>{eligible.length ? <button className="primary-button" type="button" onClick={openForm}><FileUp size={17} /> Registrar comprobante</button> : <><small>{hasActiveIssuers ? "No hay un emisor activo compatible con la composición de esta venta." : "No hay emisores fiscales activos configurados."}</small><Link className="secondary-button" href="/settings/sales/fiscal-issuers"><Settings2 size={17} /> Ir a Ajustes</Link></>}</div> : <p>El comprobante podrá registrarse cuando la venta esté confirmada.</p>}
    {error && !showForm ? <div className="error-state" role="alert">{error}</div> : null}
    {showForm ? <form className="sale-fiscal-form" onSubmit={submit}>
      <div className="section-heading"><div><h3>{document ? "Corregir comprobante" : "Registrar comprobante"}</h3><p>El total se toma de la venta y no puede editarse.</p></div><button className="icon-button" type="button" aria-label="Cerrar formulario fiscal" onClick={() => setShowForm(false)}><X size={17} /></button></div>
      <div className="fiscal-document-form-grid"><label className="field"><span>Emisor *</span><select required value={issuerId} onChange={(event) => setIssuerId(event.target.value)}><option value="">Seleccionar</option>{eligible.map((issuer) => <option key={issuer.id} value={issuer.id}>{issuer.display_name} · {issuer.tax_id}{issuer.is_active ? "" : " (inactivo, documento actual)"}</option>)}</select></label><label className="field"><span>Tipo permitido</span><input readOnly value={selectedPair ? `${labelDocumentType(selectedPair[0])} · ${selectedPair[1]}` : "Sin tipo compatible"} /></label><label className="field"><span>Número *</span><input required maxLength={120} value={number} onChange={(event) => setNumber(event.target.value)} /></label><label className="field"><span>Fecha de emisión *</span><input required type="date" value={issueDate} onChange={(event) => setIssueDate(event.target.value)} /></label><label className="field"><span>Total</span><input readOnly value={formatPurchaseCurrency(sale.total_ars, moneyPreferences)} /></label></div>
      <label className="purchase-attachment-picker"><FileUp size={20} /><span>{file?.name ?? (document ? "Conservar archivo actual o seleccionar reemplazo" : "Seleccionar PDF, JPEG o PNG *")}</span><input type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
      {file ? <small>{formatFileSize(file.size)}</small> : null}{error ? <div className="error-state" role="alert">{error}</div> : null}
      <div className="purchase-modal__actions"><button className="secondary-button" type="button" disabled={isSaving} onClick={() => setShowForm(false)}>Cancelar</button><button className="primary-button" type="submit" disabled={isSaving || (!document && !file)}><FileUp size={17} /> {isSaving ? "Guardando..." : document ? "Guardar corrección" : "Registrar comprobante"}</button></div>
    </form> : null}
  </section>;
}

function getIssuerDocumentPair(sale: Sale, issuer: FiscalIssuer): [FiscalDocumentType, string] | null {
  const products = sale.items.some((item) => item.line_type === "product");
  const services = sale.items.some((item) => item.line_type === "service");
  if (products && services) {
    if (!issuer.can_issue_product_invoice_c || !issuer.can_issue_service_receipt_c) return null;
    if (issuer.product_document_type !== issuer.service_document_type || issuer.product_document_code !== issuer.service_document_code) return null;
    return issuer.product_document_type && issuer.product_document_code ? [issuer.product_document_type, issuer.product_document_code] : null;
  }
  if (products) return issuer.can_issue_product_invoice_c && issuer.product_document_type && issuer.product_document_code ? [issuer.product_document_type, issuer.product_document_code] : null;
  return services && issuer.can_issue_service_receipt_c && issuer.service_document_type && issuer.service_document_code ? [issuer.service_document_type, issuer.service_document_code] : null;
}

function labelFiscalStatus(status: Sale["fiscal_status"]) {
  if (status === "documented") return "Documentada";
  if (status === "requires_attention") return "Requiere atención";
  if (status === "pending") return "Comprobante pendiente";
  return "Sin estado fiscal hasta confirmar";
}
function labelDocumentType(type: FiscalDocumentType) { return type === "receipt_c" ? "Recibo C" : "Factura C"; }
function labelFileType(type: string) { return type === "application/pdf" ? "PDF" : type === "image/jpeg" ? "JPEG" : "PNG"; }
function formatFileSize(size: number) { return size >= 1024 * 1024 ? `${(size / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(size / 1024))} KB`; }
function localDate() { const date = new Date(); return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`; }

const MAX_FILE_BYTES = 10 * 1024 * 1024;
const MIME_BY_EXTENSION: Record<string, string> = { pdf: "application/pdf", jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png" };
async function validateFiscalFile(file: File) {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  const expected = MIME_BY_EXTENSION[extension];
  if (!expected) return "El comprobante debe ser PDF, JPEG o PNG.";
  if (file.type.toLowerCase() !== expected) return "La extensión y el tipo del archivo no coinciden.";
  if (!file.size) return "El comprobante no puede estar vacío.";
  if (file.size > MAX_FILE_BYTES) return "El comprobante supera el máximo de 10 MB.";
  const bytes = new Uint8Array(await file.slice(0, 8).arrayBuffer());
  const valid = expected === "application/pdf" ? bytes[0] === 0x25 && bytes[1] === 0x50 && bytes[2] === 0x44 && bytes[3] === 0x46 && bytes[4] === 0x2d : expected === "image/jpeg" ? bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff : bytes.length >= 8 && [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a].every((value, index) => bytes[index] === value);
  return valid ? null : "El contenido del archivo no corresponde al formato seleccionado.";
}

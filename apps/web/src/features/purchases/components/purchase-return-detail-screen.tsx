"use client";

import { ArrowLeft, Ban, CheckCircle2, Download, ExternalLink, Eye, FileUp, Pencil, X } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { formatPurchaseCurrency, formatPurchaseDate, formatPurchaseDateTime, formatPurchaseUser } from "@/features/purchases/components/purchase-helpers";
import { getApiErrorMessage } from "@/lib/api";
import { cancelPurchaseReturn, confirmPurchaseReturn, getPurchaseReturn, getPurchaseReturnAttachment, uploadPurchaseReturnAttachment } from "@/services/purchase-returns";
import type { PurchaseReturn, PurchaseReturnDocumentType, PurchaseReturnStatus } from "@/types/api";

export function PurchaseReturnDetailScreen({ returnId }: { returnId: string }) {
  const searchParams = useSearchParams();
  const [purchaseReturn, setPurchaseReturn] = useState<PurchaseReturn | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [showAttachment, setShowAttachment] = useState(false);
  const [attachmentFile, setAttachmentFile] = useState<File | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [isConfirming, setIsConfirming] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const dialogRef = useRef<HTMLElement>(null);

  const load = useCallback(async () => {
    try { setPurchaseReturn((await getPurchaseReturn(returnId)).data); }
    catch (error) { setErrorMessage(getApiErrorMessage(error)); }
  }, [returnId]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (!showConfirmation && !showAttachment) return;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.requestAnimationFrame(() => dialogRef.current?.focus());
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !isConfirming && !isUploading) { setShowConfirmation(false); setShowAttachment(false); }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => { document.body.style.overflow = overflow; document.removeEventListener("keydown", onKeyDown); };
  }, [isConfirming, isUploading, showAttachment, showConfirmation]);

  async function handleConfirm() {
    setIsConfirming(true); setErrorMessage(null);
    try { setPurchaseReturn((await confirmPurchaseReturn(returnId)).data); setShowConfirmation(false); }
    catch (error) { setErrorMessage(getApiErrorMessage(error)); setShowConfirmation(false); }
    finally { setIsConfirming(false); }
  }

  async function handleCancel() {
    if (!cancelReason.trim()) { setErrorMessage("Ingresa un motivo de cancelación."); return; }
    setIsCancelling(true); setErrorMessage(null);
    try { setPurchaseReturn((await cancelPurchaseReturn(returnId, cancelReason.trim())).data); setCancelReason(""); }
    catch (error) { setErrorMessage(getApiErrorMessage(error)); }
    finally { setIsCancelling(false); }
  }

  async function handleUpload() {
    if (!attachmentFile) return;
    const validation = validateAttachment(attachmentFile);
    if (validation) { setErrorMessage(validation); setShowAttachment(false); return; }
    setIsUploading(true); setErrorMessage(null);
    try { await uploadPurchaseReturnAttachment(returnId, attachmentFile); await load(); setShowAttachment(false); setAttachmentFile(null); }
    catch (error) { setErrorMessage(getApiErrorMessage(error)); setShowAttachment(false); }
    finally { setIsUploading(false); }
  }

  async function handleOpenAttachment(download: boolean) {
    try {
      const response = await getPurchaseReturnAttachment(returnId, download);
      const objectUrl = URL.createObjectURL(response.blob);
      if (download) { const anchor = document.createElement("a"); anchor.href = objectUrl; anchor.download = response.filename ?? purchaseReturn?.attachment?.original_filename ?? "comprobante"; anchor.click(); }
      else window.open(objectUrl, "_blank", "noopener,noreferrer");
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    } catch (error) { setErrorMessage(getApiErrorMessage(error)); }
  }

  if (!purchaseReturn && !errorMessage) return <div className="loading-card" aria-label="Cargando devolución" />;
  if (!purchaseReturn) return <div className="page-stack purchases-page"><section className="error-state">{errorMessage}</section><Link className="secondary-button" href="/purchases">Volver a compras</Link></div>;

  return (
    <div className="page-stack purchases-page">
      <section className="screen-heading list-page__header"><div><Link className="back-link" href={`/purchases/${purchaseReturn.purchase_id}`}><ArrowLeft size={18} /> Compra original</Link><h1>Devolución a proveedor</h1><p>{purchaseReturn.supplier_name} · {formatPurchaseDate(purchaseReturn.return_date)}</p></div><div className="screen-heading__actions">{purchaseReturn.status === "draft" ? <><Link className="secondary-button" href={`/purchase-returns/${returnId}/edit`}><Pencil size={17} /> Editar</Link><button className="primary-button" type="button" onClick={() => setShowConfirmation(true)}><CheckCircle2 size={17} /> Confirmar devolución</button></> : null}{purchaseReturn.inventory_operation_id ? <Link className="secondary-button" href={`/inventory/movements?operation_id=${purchaseReturn.inventory_operation_id}`}><ExternalLink size={17} /> Ver movimientos</Link> : null}</div></section>
      {errorMessage ? <section className="error-state" role="alert">{errorMessage}</section> : null}
      {searchParams.get("attachment_upload") === "failed" ? <section className="error-state" role="alert">La devolución quedó guardada, pero no se pudo subir el comprobante. Puedes adjuntarlo aquí sin crear otro borrador.</section> : null}

      <section className="panel purchase-detail-grid">
        <div><span>Proveedor</span><strong>{purchaseReturn.supplier_name}</strong><small>{purchaseReturn.supplier_tax_id || "Sin identificación fiscal"}</small></div>
        <div><span>Estado</span><strong><span className={`badge purchase-return-status purchase-return-status--${purchaseReturn.status}`}>{labelReturnStatus(purchaseReturn.status)}</span></strong><small>Actualizada {formatPurchaseDateTime(purchaseReturn.updated_at)}</small></div>
        <div><span>Documento</span><strong>{labelReturnDocument(purchaseReturn.document_type)}</strong><small>{purchaseReturn.document_number || "Sin número"}</small></div>
        <div><span>Compra original</span><Link className="back-link" href={`/purchases/${purchaseReturn.purchase_id}`}>{formatPurchaseDate(purchaseReturn.purchase.purchase_date)}</Link><small>{purchaseReturn.purchase.document_number || "Sin número"}</small></div>
        <div className="purchase-detail-notes"><span>Motivo</span><p>{purchaseReturn.reason}</p></div>
      </section>

      <section className="inventory-table-card" aria-label="Productos devueltos"><div className="inventory-table-scroll"><table className="inventory-table purchase-table"><thead><tr><th>Producto</th><th>Cantidad</th><th>Unidad</th><th>Precio histórico</th><th>IVA</th><th>Subtotal</th><th>Total</th></tr></thead><tbody>{purchaseReturn.items.map((item) => <tr key={item.id} className="inventory-table__row--static"><td className="purchase-wrap"><strong>{item.description_snapshot}</strong><small>{item.internal_code_snapshot}</small></td><td>{item.quantity}</td><td>{item.unit}</td><td>{formatPurchaseCurrency(item.unit_price_without_tax_ars)}</td><td>{item.tax_rate_percentage}%</td><td>{formatPurchaseCurrency(item.line_subtotal_ars)}</td><td><strong>{formatPurchaseCurrency(item.line_total_ars)}</strong></td></tr>)}</tbody></table></div></section>
      <section className="panel purchase-summary"><div><span>Subtotal</span><strong>{formatPurchaseCurrency(purchaseReturn.subtotal_ars)}</strong></div><div><span>IVA</span><strong>{formatPurchaseCurrency(purchaseReturn.tax_total_ars)}</strong></div><div><span>Total devuelto</span><strong>{formatPurchaseCurrency(purchaseReturn.total_ars)}</strong></div></section>

      <section className="panel purchase-attachment-panel"><div className="section-heading"><h2>Comprobante de devolución</h2><p>{purchaseReturn.attachment ? "Comprobante cargado" : "Comprobante pendiente"}</p></div>{purchaseReturn.attachment ? <div className="purchase-attachment-metadata"><div><strong>{purchaseReturn.attachment.original_filename}</strong><small>{formatSize(purchaseReturn.attachment.size_bytes)}</small></div><div><span>Cargado por</span><strong>{formatPurchaseUser(purchaseReturn.attachment.uploaded_by_user_name, purchaseReturn.attachment.uploaded_by_user_email)}</strong><small>{formatPurchaseDateTime(purchaseReturn.attachment.uploaded_at)}</small></div></div> : <p>No hay archivo activo.</p>}<div className="purchase-attachment-actions">{purchaseReturn.attachment ? <><button className="secondary-button" type="button" onClick={() => void handleOpenAttachment(false)}><Eye size={17} /> Ver</button><button className="secondary-button" type="button" onClick={() => void handleOpenAttachment(true)}><Download size={17} /> Descargar</button></> : null}<button className="primary-button" type="button" onClick={() => setShowAttachment(true)}><FileUp size={17} /> {purchaseReturn.attachment ? "Reemplazar" : "Adjuntar"}</button></div>{purchaseReturn.attachment_history.length ? <details className="purchase-attachment-history"><summary>Historial ({purchaseReturn.attachment_history.length})</summary>{purchaseReturn.attachment_history.map((item) => <div key={item.id}><strong>{item.original_filename}</strong><small>{formatPurchaseDateTime(item.uploaded_at)}</small></div>)}</details> : null}</section>

      <section className="panel purchase-traceability"><h2>Trazabilidad</h2><dl><div><dt>Creada por</dt><dd>{formatPurchaseUser(purchaseReturn.created_by_user_name, purchaseReturn.created_by_user_email)}</dd></div><div><dt>Creada el</dt><dd>{formatPurchaseDateTime(purchaseReturn.created_at)}</dd></div><div><dt>ID</dt><dd>{purchaseReturn.id}</dd></div>{purchaseReturn.confirmed_at ? <><div><dt>Confirmada por</dt><dd>{formatPurchaseUser(purchaseReturn.confirmed_by_user_name, purchaseReturn.confirmed_by_user_email)}</dd></div><div><dt>Confirmada el</dt><dd>{formatPurchaseDateTime(purchaseReturn.confirmed_at)}</dd></div><div><dt>Operación</dt><dd>{purchaseReturn.inventory_operation_id}</dd></div></> : null}</dl></section>

      {purchaseReturn.status === "cancelled" ? <section className="panel purchase-cancellation"><h2>Cancelación</h2><p>{purchaseReturn.cancellation_reason}</p><small>{formatPurchaseUser(purchaseReturn.cancelled_by_user_name, purchaseReturn.cancelled_by_user_email)} · {formatPurchaseDateTime(purchaseReturn.cancelled_at)}</small></section> : null}
      {purchaseReturn.status === "draft" ? <section className="panel purchase-cancel-form"><div><h2>Cancelar borrador</h2><p>La devolución permanecerá histórica y no cambiará stock.</p></div><label className="field"><span>Motivo *</span><textarea rows={3} maxLength={1000} value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} /></label><button className="danger-button" type="button" disabled={isCancelling} onClick={() => void handleCancel()}><Ban size={17} /> {isCancelling ? "Cancelando..." : "Cancelar devolución"}</button></section> : null}

      {showConfirmation ? createPortal(<div className="purchase-modal-backdrop" role="presentation"><section ref={dialogRef} tabIndex={-1} className="panel purchase-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-return-title"><button className="icon-button purchase-modal__close" type="button" aria-label="Cerrar confirmación" disabled={isConfirming} onClick={() => setShowConfirmation(false)}><X size={18} /></button><div className="section-heading"><h2 id="confirm-return-title">Confirmar devolución</h2><p>Se aplicarán exactamente las líneas guardadas.</p></div><ul className="purchase-receive-effects"><li>Disminuirá el stock disponible.</li><li>La devolución quedará inmutable.</li><li>No cambiará costos, precios de venta ni margen.</li><li>No podrá editarse ni deshacerse automáticamente.</li></ul><div className="purchase-receive-summary"><div><span>Proveedor</span><strong>{purchaseReturn.supplier_name}</strong></div><div><span>Líneas</span><strong>{purchaseReturn.items.length}</strong></div><div><span>Total</span><strong>{formatPurchaseCurrency(purchaseReturn.total_ars)}</strong></div></div><div className="purchase-modal__actions"><button className="secondary-button" type="button" disabled={isConfirming} onClick={() => setShowConfirmation(false)}>Volver</button><button className="primary-button" type="button" disabled={isConfirming} onClick={() => void handleConfirm()}><CheckCircle2 size={17} /> {isConfirming ? "Confirmando..." : "Confirmar devolución"}</button></div></section></div>, document.body) : null}
      {showAttachment ? createPortal(<div className="purchase-modal-backdrop" role="presentation"><section ref={dialogRef} tabIndex={-1} className="panel purchase-modal" role="dialog" aria-modal="true" aria-labelledby="return-attachment-title"><button className="icon-button purchase-modal__close" type="button" aria-label="Cerrar" disabled={isUploading} onClick={() => setShowAttachment(false)}><X size={18} /></button><div className="section-heading"><h2 id="return-attachment-title">{purchaseReturn.attachment ? "Reemplazar comprobante" : "Agregar comprobante"}</h2><p>PDF, JPEG o PNG de hasta 10 MB. No afecta el stock.</p></div><label className="purchase-attachment-picker"><FileUp size={22} /><span>{attachmentFile?.name ?? "Seleccionar archivo"}</span><input type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" onChange={(event) => setAttachmentFile(event.target.files?.[0] ?? null)} /></label><div className="purchase-modal__actions"><button className="secondary-button" type="button" disabled={isUploading} onClick={() => setShowAttachment(false)}>Cancelar</button><button className="primary-button" type="button" disabled={isUploading || !attachmentFile} onClick={() => void handleUpload()}><FileUp size={17} /> {isUploading ? "Cargando..." : "Subir comprobante"}</button></div></section></div>, document.body) : null}
    </div>
  );
}

function labelReturnStatus(status: PurchaseReturnStatus) { return status === "draft" ? "Borrador" : status === "confirmed" ? "Confirmada" : "Cancelada"; }
function labelReturnDocument(type: PurchaseReturnDocumentType | null) { if (type === "credit_note") return "Nota de crédito"; if (type === "return_delivery_note") return "Remito de devolución"; if (type === "other") return "Otro"; return "Sin especificar"; }
function formatSize(size: number) { return size >= 1024 * 1024 ? `${(size / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(size / 1024))} KB`; }
function validateAttachment(file: File) { if (!["application/pdf", "image/jpeg", "image/png"].includes(file.type)) return "El comprobante debe ser PDF, JPEG o PNG."; if (!file.size) return "El comprobante no puede estar vacío."; if (file.size > 10 * 1024 * 1024) return "El comprobante supera el máximo de 10 MB."; return null; }

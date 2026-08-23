"use client";

import { ArrowLeft, Ban, CheckCircle2, ExternalLink, Pencil, RotateCcw, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { formatPurchaseCurrency, formatPurchaseDate, formatPurchaseDateTime, formatPurchaseUser } from "@/features/purchases/components/purchase-helpers";
import { labelSaleStatus } from "@/features/sales/components/sale-helpers";
import { SaleFiscalDocumentPanel } from "@/features/sales/components/sale-fiscal-document-panel";
import { SalePaymentsPanel } from "@/features/sales/components/sale-payments-panel";
import { getApiErrorMessage } from "@/lib/api";
import { cancelSale, confirmSale, getSale, reverseSale } from "@/services/sales";
import type { Sale } from "@/types/api";

export function SaleDetailScreen({ saleId }: { saleId: string }) {
  const [sale, setSale] = useState<Sale | null>(null);
  const [reason, setReason] = useState("");
  const [reversalReason, setReversalReason] = useState("");
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [showReversal, setShowReversal] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [isReversing, setIsReversing] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLElement>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setSale((await getSale(saleId)).data);
    } catch (value) {
      setError(getApiErrorMessage(value));
    }
  }, [saleId]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!showConfirmation && !showReversal) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.requestAnimationFrame(() => dialogRef.current?.focus());
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || isConfirming || isReversing) return;
      setShowConfirmation(false);
      setShowReversal(false);
      setModalError(null);
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isConfirming, isReversing, showConfirmation, showReversal]);

  async function handleCancel() {
    if (!reason.trim()) { setError("Ingresa un motivo de cancelación."); return; }
    setIsCancelling(true); setError(null);
    try { setSale((await cancelSale(saleId, reason.trim())).data); setReason(""); }
    catch (value) { setError(getApiErrorMessage(value)); }
    finally { setIsCancelling(false); }
  }

  async function handleConfirm() {
    if (isConfirming) return;
    setIsConfirming(true); setModalError(null);
    try {
      setSale((await confirmSale(saleId)).data);
      setShowConfirmation(false);
    } catch (value) {
      const message = getApiErrorMessage(value);
      try {
        const latest = (await getSale(saleId)).data;
        setSale(latest);
        if (latest.status === "confirmed") { setShowConfirmation(false); return; }
        if (latest.status !== "draft") { setShowConfirmation(false); setError(message); return; }
      } catch {
        // Keep the original confirmation error because it is the actionable one.
      }
      setModalError(message);
    } finally { setIsConfirming(false); }
  }

  async function handleReverse() {
    if (!reversalReason.trim()) { setModalError("Ingresa el motivo de reversión."); return; }
    if (isReversing) return;
    setIsReversing(true); setModalError(null);
    try {
      setSale((await reverseSale(saleId, reversalReason.trim())).data);
      setReversalReason("");
      setShowReversal(false);
    } catch (value) {
      setModalError(getApiErrorMessage(value));
    } finally { setIsReversing(false); }
  }

  if (!sale && !error) return <div className="loading-card" aria-label="Cargando venta" />;
  if (!sale) return <div className="page-stack sales-page"><section className="error-state">{error}</section><Link className="secondary-button" href="/sales">Volver</Link></div>;

  const productCount = sale.items.filter((item) => item.line_type === "product").length;
  const serviceCount = sale.items.length - productCount;

  return <div className="page-stack sales-page">
    <section className="screen-heading list-page__header"><div><Link className="back-link" href="/sales"><ArrowLeft size={18} /> Ventas</Link><h1>{sale.owner_name_snapshot || "Venta de mostrador"}</h1><p>{formatPurchaseDate(sale.sale_date)} · {labelSaleStatus(sale.status)}</p></div><div className="screen-heading__actions">
      {sale.status === "draft" ? <><Link className="secondary-button" href={`/sales/${sale.id}/edit`}><Pencil size={17} /> Editar</Link><button className="primary-button" type="button" onClick={() => { setModalError(null); setShowConfirmation(true); }}><CheckCircle2 size={17} /> Confirmar venta</button></> : null}
      {sale.inventory_operation_id ? <Link className="secondary-button" href={`/inventory/movements?operation_id=${sale.inventory_operation_id}`}><ExternalLink size={17} /> Ver movimientos</Link> : null}
      {sale.status === "confirmed" ? <button className="danger-button" type="button" onClick={() => { setModalError(null); setShowReversal(true); }}><RotateCcw size={17} /> Revertir venta</button> : null}
    </div></section>
    {error ? <section className="error-state" role="alert">{error}</section> : null}
    <section className="panel purchase-detail-grid"><div><span>Cliente</span><strong>{sale.owner_name_snapshot || "Venta de mostrador"}</strong><small>{sale.owner_document_snapshot || "Sin identificación"}</small></div><div><span>Paciente</span><strong>{sale.patient_name_snapshot || "Sin paciente"}</strong><small>{sale.patient_species_snapshot || "—"}</small></div><div><span>Fecha</span><strong>{formatPurchaseDate(sale.sale_date)}</strong><small>Moneda {sale.currency}</small></div><div><span>Estado</span><strong><span className={`badge sale-status sale-status--${sale.status}`}>{labelSaleStatus(sale.status)}</span></strong><small>Actualizada {formatPurchaseDateTime(sale.updated_at)}</small></div><div className="purchase-detail-notes"><span>Notas</span><p>{sale.notes || "Sin notas"}</p></div></section>
    <section className="inventory-table-card" aria-label="Líneas de venta"><div className="inventory-table-scroll"><table className="inventory-table sale-table"><thead><tr><th>Tipo</th><th>Descripción</th><th>Cantidad</th><th>Unidad</th><th>Precio</th><th>Descuento</th><th>Subtotal</th><th>Total</th></tr></thead><tbody>{sale.items.map((item) => <tr key={item.id} className="inventory-table__row--static"><td><span className="badge">{item.line_type === "product" ? "Producto" : "Servicio"}</span></td><td className="sale-text"><strong>{item.description_snapshot}</strong><small>{item.internal_code_snapshot || "Línea manual"}</small></td><td>{item.quantity}</td><td>{item.unit_snapshot}</td><td className="sale-money">{formatPurchaseCurrency(item.unit_price_ars)}</td><td>{item.discount_percentage}% · {formatPurchaseCurrency(item.line_discount_ars)}</td><td className="sale-money">{formatPurchaseCurrency(item.line_subtotal_ars)}</td><td className="sale-money"><strong>{formatPurchaseCurrency(item.line_total_ars)}</strong></td></tr>)}</tbody></table></div></section>
    <section className="panel purchase-summary"><div><span>Subtotal</span><strong>{formatPurchaseCurrency(sale.subtotal_ars)}</strong></div><div><span>Descuentos</span><strong>{formatPurchaseCurrency(sale.discount_total_ars)}</strong></div><div><span>Total</span><strong>{formatPurchaseCurrency(sale.total_ars)}</strong></div></section>
    <SalePaymentsPanel sale={sale} onUpdated={load} />
    <SaleFiscalDocumentPanel sale={sale} onUpdated={load} />
    <section className="panel purchase-traceability"><h2>Trazabilidad</h2><dl><div><dt>Creada por</dt><dd>{formatPurchaseUser(sale.created_by_user_name, sale.created_by_user_email)}</dd></div><div><dt>Creada el</dt><dd>{formatPurchaseDateTime(sale.created_at)}</dd></div><div><dt>ID</dt><dd>{sale.id}</dd></div></dl></section>
    {sale.confirmed_at ? <section className="panel purchase-receipt-trace"><div className="section-heading"><h2>Venta confirmada</h2><p>{productCount} producto{productCount === 1 ? "" : "s"} · {serviceCount} servicio{serviceCount === 1 ? "" : "s"}</p></div><dl><div><dt>Confirmada por</dt><dd>{formatPurchaseUser(sale.confirmed_by_user_name, sale.confirmed_by_user_email)}</dd></div><div><dt>Fecha</dt><dd>{formatPurchaseDateTime(sale.confirmed_at)}</dd></div><div><dt>Operación de inventario</dt><dd>{sale.inventory_operation_id || "Sin movimientos: venta sólo de servicios"}</dd></div></dl>{sale.inventory_operation_id ? <Link className="secondary-button" href={`/inventory/movements?operation_id=${sale.inventory_operation_id}`}><ExternalLink size={17} /> Ver movimientos originales</Link> : null}</section> : null}
    {sale.status === "reversed" ? <section className="panel purchase-reversal-trace"><div className="section-heading"><h2>Venta revertida</h2><p>La venta permanece histórica, cerrada y en sólo lectura.</p></div><dl><div><dt>Revertida por</dt><dd>{formatPurchaseUser(sale.reversed_by_user_name, sale.reversed_by_user_email)}</dd></div><div><dt>Fecha</dt><dd>{formatPurchaseDateTime(sale.reversed_at)}</dd></div><div><dt>Motivo</dt><dd>{sale.reversal_reason}</dd></div><div><dt>Operación original</dt><dd>{sale.inventory_operation_id || "Sin movimientos"}</dd></div><div><dt>Operación de reversión</dt><dd>{sale.reversal_operation_id || "Sin movimientos"}</dd></div></dl>{sale.reversal_operation_id ? <Link className="secondary-button" href={`/inventory/movements?operation_id=${sale.reversal_operation_id}`}><ExternalLink size={17} /> Ver movimientos de reversión</Link> : null}</section> : null}
    {sale.status === "cancelled" ? <section className="panel purchase-cancellation"><h2>Cancelación</h2><p>{sale.cancellation_reason}</p><small>{formatPurchaseUser(sale.cancelled_by_user_name, sale.cancelled_by_user_email)} · {formatPurchaseDateTime(sale.cancelled_at)}</small></section> : null}
    {sale.status === "draft" ? <section className="panel purchase-cancel-form"><div><h2>Cancelar borrador</h2><p>La venta permanecerá histórica; no se eliminarán sus líneas.</p></div><label className="field"><span>Motivo *</span><textarea rows={3} maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} /></label><button className="danger-button" type="button" disabled={isCancelling} onClick={() => void handleCancel()}><Ban size={17} /> {isCancelling ? "Cancelando..." : "Cancelar venta"}</button></section> : null}

    {showConfirmation ? createPortal(<div className="purchase-modal-backdrop" role="presentation"><section ref={dialogRef} tabIndex={-1} className="panel purchase-modal" role="dialog" aria-modal="true" aria-labelledby="sale-confirm-title" aria-describedby="sale-confirm-description"><button className="icon-button purchase-modal__close" type="button" aria-label="Cerrar confirmación" disabled={isConfirming} onClick={() => { setShowConfirmation(false); setModalError(null); }}><X size={18} /></button><div className="section-heading"><h2 id="sale-confirm-title">Confirmar venta</h2><p id="sale-confirm-description">Se aplicarán exactamente las líneas guardadas en este borrador.</p></div><ul className="purchase-receive-effects"><li>Se descontará inventario de cada producto.</li><li>Los servicios no afectarán stock.</li><li>La venta quedará cerrada y no podrá editarse.</li><li>La facturación se realizará en un paso posterior.</li></ul><div className="purchase-receive-summary"><div><span>Cliente</span><strong>{sale.owner_name_snapshot || "Venta de mostrador"}</strong></div><div><span>Paciente</span><strong>{sale.patient_name_snapshot || "Sin paciente"}</strong></div><div><span>Líneas</span><strong>{sale.items.length}</strong></div><div><span>Productos</span><strong>{productCount}</strong></div><div><span>Servicios</span><strong>{serviceCount}</strong></div><div><span>Total</span><strong>{formatPurchaseCurrency(sale.total_ars)}</strong></div></div><div className="purchase-modal-lines">{sale.items.map((line) => <div key={line.id}><span><strong>{line.description_snapshot}</strong><small>{line.line_type === "product" ? `${line.quantity} ${line.unit_snapshot} · descuenta stock` : `${line.quantity} · sin movimiento de inventario`}</small></span><strong>{formatPurchaseCurrency(line.line_total_ars)}</strong></div>)}</div>{modalError ? <div className="error-state" role="alert">{modalError}</div> : null}<div className="purchase-modal__actions"><button className="secondary-button" type="button" disabled={isConfirming} onClick={() => { setShowConfirmation(false); setModalError(null); }}>Volver</button><button className="primary-button" type="button" disabled={isConfirming} onClick={() => void handleConfirm()}><CheckCircle2 size={17} /> {isConfirming ? "Confirmando..." : "Confirmar venta"}</button></div></section></div>, document.body) : null}
    {showReversal ? createPortal(<div className="purchase-modal-backdrop" role="presentation"><section ref={dialogRef} tabIndex={-1} className="panel purchase-modal" role="dialog" aria-modal="true" aria-labelledby="sale-reverse-title"><button className="icon-button purchase-modal__close" type="button" aria-label="Cerrar reversión" disabled={isReversing} onClick={() => { setShowReversal(false); setModalError(null); }}><X size={18} /></button><div className="section-heading"><h2 id="sale-reverse-title">Revertir venta completa</h2><p>Se restaurará el stock de todos los productos. Los movimientos originales permanecerán en el historial.</p></div><label className="field"><span>Motivo *</span><textarea rows={4} maxLength={1000} value={reversalReason} onChange={(event) => setReversalReason(event.target.value)} /></label>{modalError ? <div className="error-state" role="alert">{modalError}</div> : null}<div className="purchase-modal__actions"><button className="secondary-button" type="button" disabled={isReversing} onClick={() => { setShowReversal(false); setModalError(null); }}>Volver</button><button className="danger-button" type="button" disabled={isReversing} onClick={() => void handleReverse()}><RotateCcw size={17} /> {isReversing ? "Revirtiendo..." : "Confirmar reversión"}</button></div></section></div>, document.body) : null}
  </div>;
}

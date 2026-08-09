"use client";

import { ArrowLeft, Ban, CheckCircle2, ExternalLink, Pencil, RotateCcw, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import {
  formatPurchaseCurrency,
  formatPurchaseDate,
  formatPurchaseDateTime,
  formatPurchaseUser,
  labelPurchaseDocumentType,
  labelPurchaseStatus,
} from "@/features/purchases/components/purchase-helpers";
import { ApiClientError, getApiErrorMessage } from "@/lib/api";
import { cancelPurchase, getPurchase, receivePurchase, reversePurchaseReceipt } from "@/services/purchases";
import type { Purchase } from "@/types/api";


type Props = { purchaseId: string };

export function PurchaseDetailScreen({ purchaseId }: Props) {
  const [purchase, setPurchase] = useState<Purchase | null>(null);
  const [reason, setReason] = useState("");
  const [isCancelling, setIsCancelling] = useState(false);
  const [showReceiveConfirmation, setShowReceiveConfirmation] = useState(false);
  const [showReverseConfirmation, setShowReverseConfirmation] = useState(false);
  const [reversalReason, setReversalReason] = useState("");
  const [isReceiving, setIsReceiving] = useState(false);
  const [isReversing, setIsReversing] = useState(false);
  const [receiveErrorMessage, setReceiveErrorMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const dialogRef = useRef<HTMLElement>(null);

  const load = useCallback(async () => {
    setErrorMessage(null);
    try {
      const response = await getPurchase(purchaseId);
      setPurchase(response.data);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    }
  }, [purchaseId]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!showReceiveConfirmation && !showReverseConfirmation) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.requestAnimationFrame(() => dialogRef.current?.focus());
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || isReceiving || isReversing) return;
      setShowReceiveConfirmation(false);
      setShowReverseConfirmation(false);
      setReceiveErrorMessage(null);
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isReceiving, isReversing, showReceiveConfirmation, showReverseConfirmation]);

  async function handleCancel() {
    if (!reason.trim()) {
      setErrorMessage("Ingresa un motivo de cancelación.");
      return;
    }
    setIsCancelling(true);
    setErrorMessage(null);
    try {
      const response = await cancelPurchase(purchaseId, reason.trim());
      setPurchase(response.data);
      setReason("");
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsCancelling(false);
    }
  }

  async function handleReceive() {
    if (isReceiving) return;
    setIsReceiving(true);
    setReceiveErrorMessage(null);
    try {
      const response = await receivePurchase(purchaseId);
      setPurchase(response.data);
      setShowReceiveConfirmation(false);
    } catch (error) {
      const message = getPurchaseReceiveErrorMessage(error);
      try {
        const latest = await getPurchase(purchaseId);
        setPurchase(latest.data);
        if (latest.data.status === "received") {
          setShowReceiveConfirmation(false);
          return;
        }
        if (latest.data.status !== "draft") {
          setShowReceiveConfirmation(false);
          setErrorMessage(message);
          return;
        }
      } catch {
        // The original receive error remains the most useful message.
      }
      setReceiveErrorMessage(message);
    } finally {
      setIsReceiving(false);
    }
  }

  async function handleReverseReceipt() {
    if (!reversalReason.trim()) {
      setErrorMessage("Ingresa el motivo de reversión.");
      return;
    }
    setIsReversing(true);
    setErrorMessage(null);
    try {
      const response = await reversePurchaseReceipt(purchaseId, reversalReason.trim());
      setPurchase(response.data);
      setReversalReason("");
      setShowReverseConfirmation(false);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsReversing(false);
    }
  }

  if (!purchase && !errorMessage) return <div className="loading-card" aria-label="Cargando detalle de compra" />;

  return (
    <div className="page-stack purchases-page">
      <section className="screen-heading list-page__header">
        <div>
          <Link className="back-link" href="/purchases"><ArrowLeft size={18} /> Compras</Link>
          <h1>{purchase?.supplier_name ?? "Detalle de compra"}</h1>
          <p>{purchase ? `${formatPurchaseDate(purchase.purchase_date)} · ${labelPurchaseStatus(purchase.status)}` : "Compra no disponible"}</p>
        </div>
        {purchase ? <div className="screen-heading__actions">
          {purchase.status === "draft" ? <><Link className="secondary-button" href={`/purchases/${purchase.id}/edit`}><Pencil size={17} /> Editar</Link><button className="primary-button" type="button" onClick={() => { setErrorMessage(null); setReceiveErrorMessage(null); setShowReceiveConfirmation(true); }}><CheckCircle2 size={17} /> Recibir compra</button></> : null}
          {purchase.inventory_operation_id ? <Link className="secondary-button" href={`/inventory/movements?operation_id=${purchase.inventory_operation_id}`}><ExternalLink size={17} /> Ver movimientos</Link> : null}
          {purchase.status === "received" ? <button className="danger-button" type="button" onClick={() => setShowReverseConfirmation(true)}><RotateCcw size={17} /> Revertir recepción</button> : null}
        </div> : null}
      </section>

      {errorMessage ? <section className="error-state" role="alert">{errorMessage}</section> : null}

      {purchase ? (
        <>
          <section className="panel purchase-detail-grid">
            <div>
              <span>Proveedor al registrar</span>
              <strong>{purchase.supplier_name}</strong>
              <small>{purchase.supplier_tax_id || "Sin identificación fiscal"}</small>
              {purchase.supplier ? <Link className="back-link" href={`/suppliers/${purchase.supplier_id}`}>Ver proveedor actual: {purchase.supplier.name}</Link> : null}
            </div>
            <div><span>Comprobante</span><strong>{labelPurchaseDocumentType(purchase.document_type)}</strong><small>{purchase.document_number || "Sin número"}</small></div>
            <div><span>Fecha</span><strong>{formatPurchaseDate(purchase.purchase_date)}</strong><small>Moneda {purchase.currency}</small></div>
            <div><span>Estado</span><strong><span className={`badge purchase-status purchase-status--${purchase.status}`}>{labelPurchaseStatus(purchase.status)}</span></strong><small>Actualizada {formatPurchaseDateTime(purchase.updated_at)}</small></div>
            <div className="purchase-detail-notes"><span>Notas</span><p>{purchase.notes || "Sin notas"}</p></div>
          </section>

          <section className="inventory-table-card" aria-label="Líneas de compra">
            <div className="inventory-table-scroll">
              <table className="inventory-table purchase-table">
                <thead><tr><th>Producto</th><th>Cantidad</th><th>Unidad</th><th>Precio sin IVA</th><th>IVA</th><th>Subtotal</th><th>Total</th></tr></thead>
                <tbody>
                  {purchase.items.map((line) => (
                    <tr key={line.id} className="inventory-table__row--static">
                      <td className="purchase-wrap"><strong>{line.description_snapshot}</strong><small>{line.internal_code_snapshot}</small></td>
                      <td>{line.quantity}</td><td>{line.unit}</td>
                      <td>{formatPurchaseCurrency(line.unit_price_without_tax_ars)}</td>
                      <td>{line.tax_rate_percentage}% · {formatPurchaseCurrency(line.line_tax_ars)}</td>
                      <td>{formatPurchaseCurrency(line.line_subtotal_ars)}</td>
                      <td><strong>{formatPurchaseCurrency(line.line_total_ars)}</strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel purchase-summary" aria-label="Totales de compra">
            <div><span>Subtotal</span><strong>{formatPurchaseCurrency(purchase.subtotal_ars)}</strong></div>
            <div><span>IVA</span><strong>{formatPurchaseCurrency(purchase.tax_total_ars)}</strong></div>
            <div><span>Total</span><strong>{formatPurchaseCurrency(purchase.total_ars)}</strong></div>
          </section>

          <section className="panel purchase-traceability">
            <h2>Trazabilidad</h2>
            <dl>
              <div><dt>Creada por</dt><dd>{formatPurchaseUser(purchase.created_by_user_name, purchase.created_by_user_email)}</dd></div>
              <div><dt>Creada el</dt><dd>{formatPurchaseDateTime(purchase.created_at)}</dd></div>
              <div><dt>ID</dt><dd>{purchase.id}</dd></div>
            </dl>
          </section>

          {purchase.received_at ? (
            <section className="panel purchase-receipt-trace">
              <div className="section-heading"><h2>Recepción de inventario</h2><p>{purchase.items.length} producto{purchase.items.length === 1 ? "" : "s"} · recepción total</p></div>
              <dl>
                <div><dt>Recibida por</dt><dd>{formatPurchaseUser(purchase.received_by_user_name, purchase.received_by_user_email)}</dd></div>
                <div><dt>Fecha</dt><dd>{formatPurchaseDateTime(purchase.received_at)}</dd></div>
                <div><dt>Operación</dt><dd>{purchase.inventory_operation_id}</dd></div>
              </dl>
              {purchase.inventory_operation_id ? <Link className="secondary-button" href={`/inventory/movements?operation_id=${purchase.inventory_operation_id}`}><ExternalLink size={17} /> Ver movimientos originales</Link> : null}
            </section>
          ) : null}

          {purchase.status === "reversed" ? (
            <section className="panel purchase-reversal-trace">
              <div className="section-heading"><h2>Recepción revertida</h2><p>La compra permanece en sólo lectura y conserva toda su trazabilidad.</p></div>
              <dl>
                <div><dt>Revertida por</dt><dd>{formatPurchaseUser(purchase.reversed_by_user_name, purchase.reversed_by_user_email)}</dd></div>
                <div><dt>Fecha</dt><dd>{formatPurchaseDateTime(purchase.reversed_at)}</dd></div>
                <div><dt>Motivo</dt><dd>{purchase.reversal_reason}</dd></div>
                <div><dt>Operación de reversión</dt><dd>{purchase.reversal_operation_id}</dd></div>
              </dl>
              {purchase.reversal_operation_id ? <Link className="secondary-button" href={`/inventory/movements?operation_id=${purchase.reversal_operation_id}`}><ExternalLink size={17} /> Ver movimientos de reversión</Link> : null}
              {purchase.reversal_warnings.map((warning) => <p className="purchase-reversal-warning" key={warning}>{warning}</p>)}
            </section>
          ) : null}

          {purchase.status === "cancelled" ? (
            <section className="panel purchase-cancellation">
              <h2>Cancelación</h2>
              <p>{purchase.cancellation_reason}</p>
              <small>{formatPurchaseUser(purchase.cancelled_by_user_name, purchase.cancelled_by_user_email)} · {formatPurchaseDateTime(purchase.cancelled_at)}</small>
            </section>
          ) : null}

          {purchase.status === "draft" ? (
            <section className="panel purchase-cancel-form">
              <div><h2>Cancelar borrador</h2><p>La compra permanecerá visible y no se eliminarán sus líneas.</p></div>
              <label className="field"><span>Motivo *</span><textarea rows={3} maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
              <button className="danger-button" type="button" disabled={isCancelling} onClick={() => void handleCancel()}><Ban size={17} /> {isCancelling ? "Cancelando..." : "Cancelar compra"}</button>
            </section>
          ) : null}
        </>
      ) : null}

      {purchase && showReceiveConfirmation ? createPortal(
        <div className="purchase-modal-backdrop" role="presentation">
          <section ref={dialogRef} tabIndex={-1} className="panel purchase-modal" role="dialog" aria-modal="true" aria-labelledby="receive-title" aria-describedby="receive-description">
            <button className="icon-button purchase-modal__close" type="button" aria-label="Cerrar confirmación" disabled={isReceiving} onClick={() => { setShowReceiveConfirmation(false); setReceiveErrorMessage(null); }}><X size={18} /></button>
            <div className="section-heading"><h2 id="receive-title">Confirmar recepción</h2><p id="receive-description">Se aplicarán exactamente las líneas guardadas en esta compra.</p></div>
            <ul className="purchase-receive-effects"><li>Aumentará el stock de cada producto.</li><li>Actualizará el último costo de compra y su IVA.</li><li>No cambiará el precio de venta ni el margen.</li><li>La compra quedará inmutable después de recibirla.</li></ul>
            <div className="purchase-receive-summary"><div><span>Proveedor</span><strong>{purchase.supplier_name}</strong></div><div><span>Líneas</span><strong>{purchase.items.length}</strong></div><div><span>Total</span><strong>{formatPurchaseCurrency(purchase.total_ars)}</strong></div></div>
            <div className="purchase-modal-lines">{purchase.items.map((line) => <div key={line.id}><span><strong>{line.description_snapshot}</strong><small>{line.quantity} {line.unit}</small></span><strong>{formatPurchaseCurrency(line.line_total_ars)}</strong></div>)}</div>
            {receiveErrorMessage ? <div className="error-state" role="alert">{receiveErrorMessage}</div> : null}
            <div className="purchase-modal__actions"><button className="secondary-button" type="button" disabled={isReceiving} onClick={() => { setShowReceiveConfirmation(false); setReceiveErrorMessage(null); }}>Volver</button><button className="primary-button" type="button" disabled={isReceiving} onClick={() => void handleReceive()}><CheckCircle2 size={17} /> {isReceiving ? "Recibiendo..." : "Confirmar recepción"}</button></div>
          </section>
        </div>,
        document.body,
      ) : null}

      {purchase && showReverseConfirmation ? createPortal(
        <div className="purchase-modal-backdrop" role="presentation">
          <section ref={dialogRef} tabIndex={-1} className="panel purchase-modal" role="dialog" aria-modal="true" aria-labelledby="reverse-title">
            <button className="icon-button purchase-modal__close" type="button" aria-label="Cerrar reversión" onClick={() => setShowReverseConfirmation(false)}><X size={18} /></button>
            <div className="section-heading"><h2 id="reverse-title">Revertir recepción completa</h2><p>Se retirarán todas las cantidades recibidas. La operación fallará sin cambios si algún producto no tiene stock suficiente.</p></div>
            <label className="field"><span>Motivo *</span><textarea rows={4} maxLength={1000} value={reversalReason} onChange={(event) => setReversalReason(event.target.value)} /></label>
            <div className="purchase-modal__actions"><button className="secondary-button" type="button" disabled={isReversing} onClick={() => setShowReverseConfirmation(false)}>Volver</button><button className="danger-button" type="button" disabled={isReversing} onClick={() => void handleReverseReceipt()}><RotateCcw size={17} /> {isReversing ? "Revirtiendo..." : "Confirmar reversión"}</button></div>
          </section>
        </div>,
        document.body,
      ) : null}
    </div>
  );
}

function getPurchaseReceiveErrorMessage(error: unknown) {
  if (error instanceof ApiClientError) {
    if (error.status === 401) return "Tu sesión expiró. Vuelve a iniciar sesión.";
    if (error.status === 403) return "No tienes permiso para recibir esta compra.";
    if (error.status > 0 && error.message) return error.message;
  }
  return "No se pudo recibir la compra. Intenta nuevamente.";
}

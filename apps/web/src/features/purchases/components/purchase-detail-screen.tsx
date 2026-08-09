"use client";

import { ArrowLeft, Ban, Pencil } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  formatPurchaseCurrency,
  formatPurchaseDate,
  formatPurchaseDateTime,
  formatPurchaseUser,
  labelPurchaseDocumentType,
  labelPurchaseStatus,
} from "@/features/purchases/components/purchase-helpers";
import { getApiErrorMessage } from "@/lib/api";
import { cancelPurchase, getPurchase } from "@/services/purchases";
import type { Purchase } from "@/types/api";


type Props = { purchaseId: string };

export function PurchaseDetailScreen({ purchaseId }: Props) {
  const [purchase, setPurchase] = useState<Purchase | null>(null);
  const [reason, setReason] = useState("");
  const [isCancelling, setIsCancelling] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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

  if (!purchase && !errorMessage) return <div className="loading-card" aria-label="Cargando detalle de compra" />;

  return (
    <div className="page-stack purchases-page">
      <section className="screen-heading list-page__header">
        <div>
          <Link className="back-link" href="/purchases"><ArrowLeft size={18} /> Compras</Link>
          <h1>{purchase?.supplier_name ?? "Detalle de compra"}</h1>
          <p>{purchase ? `${formatPurchaseDate(purchase.purchase_date)} · ${labelPurchaseStatus(purchase.status)}` : "Compra no disponible"}</p>
        </div>
        {purchase?.status === "draft" ? (
          <Link className="secondary-button" href={`/purchases/${purchase.id}/edit`}><Pencil size={17} /> Editar</Link>
        ) : null}
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
    </div>
  );
}

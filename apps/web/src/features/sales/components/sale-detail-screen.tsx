"use client";

import { ArrowLeft, Ban, Pencil } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { formatPurchaseCurrency, formatPurchaseDate, formatPurchaseDateTime, formatPurchaseUser } from "@/features/purchases/components/purchase-helpers";
import { getApiErrorMessage } from "@/lib/api";
import { cancelSale, getSale } from "@/services/sales";
import type { Sale } from "@/types/api";

export function SaleDetailScreen({ saleId }: { saleId: string }) {
  const [sale, setSale] = useState<Sale | null>(null); const [reason, setReason] = useState(""); const [isCancelling, setIsCancelling] = useState(false); const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { setError(null); try { setSale((await getSale(saleId)).data); } catch (value) { setError(getApiErrorMessage(value)); } }, [saleId]);
  useEffect(() => { void load(); }, [load]);
  async function handleCancel() { if (!reason.trim()) { setError("Ingresa un motivo de cancelación."); return; } setIsCancelling(true); setError(null); try { setSale((await cancelSale(saleId, reason.trim())).data); setReason(""); } catch (value) { setError(getApiErrorMessage(value)); } finally { setIsCancelling(false); } }
  if (!sale && !error) return <div className="loading-card" aria-label="Cargando venta" />;
  if (!sale) return <div className="page-stack sales-page"><section className="error-state">{error}</section><Link className="secondary-button" href="/sales">Volver</Link></div>;
  return <div className="page-stack sales-page">
    <section className="screen-heading list-page__header"><div><Link className="back-link" href="/sales"><ArrowLeft size={18} /> Ventas</Link><h1>{sale.owner_name_snapshot || "Venta de mostrador"}</h1><p>{formatPurchaseDate(sale.sale_date)} · {sale.status === "draft" ? "Borrador" : "Cancelada"}</p></div>{sale.status === "draft" ? <Link className="primary-button" href={`/sales/${sale.id}/edit`}><Pencil size={17} /> Editar</Link> : null}</section>
    {error ? <section className="error-state" role="alert">{error}</section> : null}
    <section className="panel purchase-detail-grid"><div><span>Cliente</span><strong>{sale.owner_name_snapshot || "Venta de mostrador"}</strong><small>{sale.owner_document_snapshot || "Sin identificación"}</small></div><div><span>Paciente</span><strong>{sale.patient_name_snapshot || "Sin paciente"}</strong><small>{sale.patient_species_snapshot || "—"}</small></div><div><span>Fecha</span><strong>{formatPurchaseDate(sale.sale_date)}</strong><small>Moneda {sale.currency}</small></div><div><span>Estado</span><strong><span className={`badge sale-status sale-status--${sale.status}`}>{sale.status === "draft" ? "Borrador" : "Cancelada"}</span></strong><small>Actualizada {formatPurchaseDateTime(sale.updated_at)}</small></div><div className="purchase-detail-notes"><span>Notas</span><p>{sale.notes || "Sin notas"}</p></div></section>
    <section className="inventory-table-card" aria-label="Líneas de venta"><div className="inventory-table-scroll"><table className="inventory-table sale-table"><thead><tr><th>Tipo</th><th>Descripción</th><th>Cantidad</th><th>Unidad</th><th>Precio</th><th>Descuento</th><th>Subtotal</th><th>Total</th></tr></thead><tbody>{sale.items.map((item) => <tr key={item.id} className="inventory-table__row--static"><td><span className="badge">{item.line_type === "product" ? "Producto" : "Servicio"}</span></td><td className="sale-text"><strong>{item.description_snapshot}</strong><small>{item.internal_code_snapshot || "Línea manual"}</small></td><td>{item.quantity}</td><td>{item.unit_snapshot}</td><td className="sale-money">{formatPurchaseCurrency(item.unit_price_ars)}</td><td>{item.discount_percentage}% · {formatPurchaseCurrency(item.line_discount_ars)}</td><td className="sale-money">{formatPurchaseCurrency(item.line_subtotal_ars)}</td><td className="sale-money"><strong>{formatPurchaseCurrency(item.line_total_ars)}</strong></td></tr>)}</tbody></table></div></section>
    <section className="panel purchase-summary"><div><span>Subtotal</span><strong>{formatPurchaseCurrency(sale.subtotal_ars)}</strong></div><div><span>Descuentos</span><strong>{formatPurchaseCurrency(sale.discount_total_ars)}</strong></div><div><span>Total</span><strong>{formatPurchaseCurrency(sale.total_ars)}</strong></div></section>
    <section className="panel purchase-traceability"><h2>Trazabilidad</h2><dl><div><dt>Creada por</dt><dd>{formatPurchaseUser(sale.created_by_user_name, sale.created_by_user_email)}</dd></div><div><dt>Creada el</dt><dd>{formatPurchaseDateTime(sale.created_at)}</dd></div><div><dt>ID</dt><dd>{sale.id}</dd></div></dl></section>
    {sale.status === "cancelled" ? <section className="panel purchase-cancellation"><h2>Cancelación</h2><p>{sale.cancellation_reason}</p><small>{formatPurchaseUser(sale.cancelled_by_user_name, sale.cancelled_by_user_email)} · {formatPurchaseDateTime(sale.cancelled_at)}</small></section> : null}
    {sale.status === "draft" ? <section className="panel purchase-cancel-form"><div><h2>Cancelar borrador</h2><p>La venta permanecerá histórica; no se eliminarán sus líneas.</p></div><label className="field"><span>Motivo *</span><textarea rows={3} maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} /></label><button className="danger-button" type="button" disabled={isCancelling} onClick={() => void handleCancel()}><Ban size={17} /> {isCancelling ? "Cancelando..." : "Cancelar venta"}</button></section> : null}
  </div>;
}

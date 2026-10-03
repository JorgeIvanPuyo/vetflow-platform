"use client";

import { RefreshCw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { getApiErrorMessage } from "@/lib/api";
import { formatExactCurrency, resolveMoneyPreferences } from "@/lib/money";
import { getOwnerReceivables } from "@/services/owners";
import type { OwnerReceivablesResponse } from "@/types/api";

type ReceivablesState = {
  ownerId: string;
  page: number;
  loading: boolean;
  response: OwnerReceivablesResponse | null;
  error: string | null;
};

export function OwnerReceivablesPanel({ ownerId, isArchived = false }: { ownerId: string; isArchived?: boolean }) {
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [state, setState] = useState<ReceivablesState>({ ownerId, page: 1, loading: true, response: null, error: null });

  useEffect(() => {
    let current = true;
    setState({ ownerId, page, loading: true, response: null, error: null });
    void getOwnerReceivables(ownerId, { page }).then((response) => {
      if (!current) return;
      if (page > Math.max(1, response.meta.total_pages)) {
        setPage(Math.max(1, response.meta.total_pages));
        return;
      }
      setState({ ownerId, page, loading: false, response, error: null });
    }).catch((error: unknown) => {
      if (current) setState({ ownerId, page, loading: false, response: null, error: getApiErrorMessage(error) });
    });
    return () => { current = false; };
  }, [ownerId, page, refresh]);

  const loading = state.loading || state.ownerId !== ownerId || state.page !== page;
  const response = loading ? null : state.response;
  const error = loading ? null : state.error;
  const data = response?.data;
  const money = resolveMoneyPreferences(data?.currency && data.locale ? { currency_code: data.currency, locale: data.locale } : null, data?.currency);

  return <section className="panel owner-receivables-panel" aria-labelledby="owner-receivables-title" aria-busy={loading}>
    <div className="section-heading section-heading--row">
      <div><h2 id="owner-receivables-title">Saldo pendiente</h2>{isArchived ? <p>Propietario archivado · historial conservado</p> : null}</div>
      <button className="secondary-button" type="button" disabled={loading} onClick={() => {
        setState({ ownerId, page, loading: true, response: null, error: null });
        setRefresh((value) => value + 1);
      }}><RefreshCw size={15} aria-hidden="true" /> Actualizar saldo</button>
    </div>
    {loading ? <p role="status">Cargando saldo pendiente…</p> : error ? <div className="error-state" role="alert">{error}</div> : data ? (
      !data.tracking_configured ? <p className="empty-state">Control de cuentas por cobrar no configurado.</p> : <>
        <div className="owner-receivables-summary">
          <strong>{formatExactCurrency(data.total_outstanding_ars, money)}</strong>
          <span>{data.open_sales_count} venta{data.open_sales_count === 1 ? "" : "s"} pendiente{data.open_sales_count === 1 ? "" : "s"}</span>
        </div>
        {data.open_sales_count === 0 ? <p className="empty-state">No hay ventas con saldo pendiente desde el inicio del control.</p> : <details className="owner-receivables-details" open={expanded} onToggle={(event) => setExpanded(event.currentTarget.open)}>
          <summary>Ver ventas pendientes</summary>
          <div className="owner-receivables-table-scroll"><table>
            <thead><tr><th>Venta</th><th>Total</th><th>Pagado</th><th>Pendiente</th></tr></thead>
            <tbody>{data.sales.map((sale) => {
              const saleMoney = resolveMoneyPreferences({ currency_code: data.currency ?? sale.currency, locale: data.locale ?? money.locale }, sale.currency);
              return <tr key={sale.sale_id}>
                <td><Link href={`/sales/${sale.sale_id}`}>Venta #{sale.sale_id.slice(0, 8).toUpperCase()}</Link><small>{new Intl.DateTimeFormat(money.locale, { dateStyle: "medium" }).format(new Date(`${sale.sale_date}T12:00:00`))}{sale.patient_name_snapshot ? ` · ${sale.patient_name_snapshot}` : ""}</small></td>
                <td>{formatExactCurrency(sale.total_ars, saleMoney)}</td>
                <td>{formatExactCurrency(sale.paid_total_ars, saleMoney)}</td>
                <td><strong>{formatExactCurrency(sale.balance_due_ars, saleMoney)}</strong></td>
              </tr>;
            })}</tbody>
          </table></div>
          {response.meta.total_pages > 1 ? <nav className="list-pagination" aria-label="Paginación de ventas pendientes">
            <span className="list-pagination__range">Página {response.meta.page} de {response.meta.total_pages}</span>
            <div className="list-pagination__actions">
              <button className="secondary-button" type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Anterior</button>
              <button className="secondary-button" type="button" disabled={page >= response.meta.total_pages} onClick={() => setPage((value) => value + 1)}>Siguiente</button>
            </div>
          </nav> : null}
        </details>}
        <p className="owner-receivables-scope">Incluye ventas confirmadas desde {data.tracking_started_at ? new Intl.DateTimeFormat(money.locale, { dateStyle: "medium" }).format(new Date(data.tracking_started_at)) : "el inicio del control"}.</p>
      </>
    ) : null}
  </section>;
}

"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { clinicCalendarDate } from "@/features/clinic/components/receivables-settings-helpers";
import { getApiErrorMessage } from "@/lib/api";
import { formatExactCurrency } from "@/lib/money";
import { getPaymentReport, PaymentReportFilters, PaymentReportResponse } from "@/services/payment-reports";
import type { PaymentReportEntry, PaymentReportMethod } from "@/types/api";

export function PaymentReportScreen() {
  // The server supplies today's clinic dates, avoiding the browser's timezone.
  const [filters, setFilters] = useState<PaymentReportFilters>({});
  const [draft, setDraft] = useState({ date_from: "", date_to: "", payment_method_id: "" });
  const [response, setResponse] = useState<PaymentReportResponse | null>(null);
  const [methods, setMethods] = useState<PaymentReportMethod[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [validation, setValidation] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    getPaymentReport(filters).then((result) => {
      if (cancelled) return;
      setResponse(result);
      setMethods(result.data.methods);
      if (!filters.date_from) setDraft({ date_from: result.data.date_from, date_to: result.data.date_to, payment_method_id: "" });
    }).catch((value) => { if (!cancelled) setError(getApiErrorMessage(value)); })
      .finally(() => { if (!cancelled) setIsLoading(false); });
    return () => { cancelled = true; };
  }, [filters, retry]);

  function apply(event: FormEvent) {
    event.preventDefault();
    if (!draft.date_from || !draft.date_to || draft.date_from > draft.date_to) {
      setValidation("Selecciona un rango de fechas válido.");
      return;
    }
    setValidation(null);
    setFilters({ ...draft, page: 1, page_size: filters.page_size ?? 20 });
  }
  function changePage(page: number) {
    if (!response) return;
    setFilters({ ...filters, date_from: response.data.date_from, date_to: response.data.date_to, page });
  }
  const data = response?.data;
  const money = { currencyCode: data?.currency_code ?? "ARS", locale: data?.locale ?? "es-AR" };
  const amount = (value: string) => formatExactCurrency(value, money);
  const timestamp = (value: string) => `${dateLabel(clinicCalendarDate(value, data?.timezone ?? "America/Panama"))} ${new Intl.DateTimeFormat(data?.locale ?? "es-AR", {
    timeZone: data?.timezone, hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).format(new Date(value))}`;
  const saleLink = (payment: PaymentReportEntry) => <Link href={`/sales/${payment.sale_id}`} className="text-link">Ver venta #{payment.sale_id.slice(0, 8).toUpperCase()}</Link>;

  return <div className="page-stack payment-report-page">
    <section className="screen-heading"><div><Link href="/sales" className="text-link">Volver a ventas</Link><h1>Cobros por forma de pago</h1><p>Cobros activos según su fecha efectiva de recepción.</p></div></section>
    <form className="panel payment-report-filters" aria-label="Filtros de cobros" onSubmit={apply}>
      <label className="field" htmlFor="report-from"><span>Desde</span><input id="report-from" type="date" required value={draft.date_from} disabled={!data} onChange={(event) => setDraft({ ...draft, date_from: event.target.value })} /></label>
      <label className="field" htmlFor="report-to"><span>Hasta</span><input id="report-to" type="date" required value={draft.date_to} disabled={!data} onChange={(event) => setDraft({ ...draft, date_to: event.target.value })} /></label>
      <label className="field" htmlFor="report-method"><span>Forma de pago</span><select id="report-method" value={draft.payment_method_id} disabled={!data} onChange={(event) => setDraft({ ...draft, payment_method_id: event.target.value })}><option value="">Todas</option>{methods.map((method) => <option key={method.payment_method_id} value={method.payment_method_id}>{method.label}{method.is_active ? "" : " (inactiva)"}</option>)}</select></label>
      <button className="primary-button" type="submit" disabled={!data || isLoading}>Aplicar</button>
      {validation ? <p role="alert" className="payment-report-filter-error">{validation}</p> : null}
    </form>
    {isLoading ? <div className="loading-card" role="status" aria-label="Cargando cobros">Cargando cobros…</div> : null}
    {!isLoading && error ? <section className="error-state" role="alert"><p>{error}</p><button type="button" className="secondary-button" onClick={() => setRetry((value) => value + 1)}>Reintentar</button></section> : null}
    {!isLoading && !error && data ? <>
      <p className="muted payment-report-period">Período: {dateLabel(data.date_from)} al {dateLabel(data.date_to)} · Zona horaria: {data.timezone}</p>
      <section className="payment-report-summary" aria-label="Resumen de cobros">
        <article className="panel payment-report-total"><span>Total cobrado</span><strong>{amount(data.summary.total_amount_ars)}</strong><span>{data.summary.payment_count} cobros</span></article>
        {data.summary.by_method.map((group) => <article className="panel" key={group.payment_method_id}><strong>{group.label}</strong>{!group.is_active ? <span className="badge">Inactiva</span> : null}<strong>{amount(group.amount_ars)}</strong><span>{group.payment_count} {group.payment_count === 1 ? "cobro" : "cobros"}</span></article>)}
      </section>
      {data.summary.payment_count > 0 ? <p className="muted">Los nombres de los cobros conservan su registro histórico. Cada grupo usa el nombre de su cobro más reciente en el período. Revertir una venta no anula sus cobros.</p> : null}
      {!data.summary.payment_count ? <section className="empty-state"><h2>No hay cobros registrados para este período.</h2></section> : <>
        <section className="panel payment-report-desktop" aria-label="Detalle de cobros">
          <table className="payment-report-table"><thead><tr><th>Fecha/hora</th><th>Forma de pago</th><th>Importe</th><th>Venta / propietario / paciente</th><th>Referencia / usuario</th></tr></thead><tbody>{data.payments.map((payment) => <tr key={payment.payment_id}>
            <td>{timestamp(payment.received_at)}</td><td>{payment.payment_method_label}</td><td className="payment-report-money">{amount(payment.amount_ars)}</td>
            <td>{saleLink(payment)}<span>{payment.owner_name || "Sin propietario"}</span><span>{payment.patient_name || "Sin paciente"}</span></td>
            <td><span>{payment.reference || "Sin referencia"}</span><span>{payment.created_by_user_name || "Sin usuario registrado"}</span></td>
          </tr>)}</tbody></table>
        </section>
        <section className="payment-report-mobile" aria-label="Detalle de cobros móvil">{data.payments.map((payment) => <article className="panel" key={payment.payment_id}>
          <div className="payment-report-card-heading"><strong>{payment.payment_method_label}</strong><strong>{amount(payment.amount_ars)}</strong></div>
          <time dateTime={payment.received_at}>{timestamp(payment.received_at)}</time>
          <dl><div><dt>Propietario</dt><dd>{payment.owner_name || "Sin propietario"}</dd></div><div><dt>Paciente</dt><dd>{payment.patient_name || "Sin paciente"}</dd></div><div><dt>Referencia</dt><dd>{payment.reference || "Sin referencia"}</dd></div><div><dt>Usuario</dt><dd>{payment.created_by_user_name || "Sin usuario registrado"}</dd></div></dl>{saleLink(payment)}
        </article>)}</section>
        {data.payments.length === 0 ? <p role="status">Esta página no tiene cobros. Vuelve a la página anterior.</p> : null}
        <nav className="purchase-pagination" aria-label="Paginación de cobros"><button className="secondary-button" disabled={response.meta.page <= 1} onClick={() => changePage(response.meta.page - 1)}>Anterior</button><span>Página {response.meta.page} de {Math.max(response.meta.total_pages, 1)} · {response.meta.total} cobros</span><button className="secondary-button" disabled={response.meta.page >= response.meta.total_pages} onClick={() => changePage(response.meta.page + 1)}>Siguiente</button></nav>
      </>}
    </> : null}
  </div>;
}

function dateLabel(value: string) { const [year, month, day] = value.split("-"); return `${day}/${month}/${year}`; }

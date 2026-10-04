"use client";

import { ArrowLeft, RefreshCw } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { getApiErrorMessage } from "@/lib/api";
import { formatExactCurrency, resolveMoneyPreferences } from "@/lib/money";
import { getOwner, getOwnerReceivables, getOwnerReceivablesActivity } from "@/services/owners";
import { getPatients } from "@/services/patients";
import type { OwnerReceivablesActivityEvent, OwnerReceivablesResponse } from "@/types/api";

type Filters = { dateFrom: string; dateTo: string; patientId: string };
const emptyFilters: Filters = { dateFrom: "", dateTo: "", patientId: "" };

function useAccountRead<T>(ownerId: string, load: () => Promise<T>, refresh = 0) {
  const [state, setState] = useState<{ ownerId: string; load: typeof load; refresh: number; data: T | null; loading: boolean; error: string | null }>({ ownerId, load, refresh, data: null, loading: true, error: null });
  useEffect(() => {
    let current = true;
    setState((previous) => ({ ownerId, load, refresh, data: previous.ownerId === ownerId ? previous.data : null, loading: true, error: null }));
    void load().then((data) => {
      if (current) setState({ ownerId, load, refresh, data, loading: false, error: null });
    }).catch((error: unknown) => {
      if (current) setState({ ownerId, load, refresh, data: null, loading: false, error: getApiErrorMessage(error) });
    });
    return () => { current = false; };
  }, [ownerId, load, refresh]);
  return state.load === load && state.refresh === refresh && state.ownerId === ownerId ? state : { ...state, data: state.ownerId === ownerId ? state.data : null, loading: true, error: null };
}

export function OwnerAccountScreen({ ownerId }: { ownerId: string }) {
  const [refresh, setRefresh] = useState(0);
  const [salesPage, setSalesPage] = useState(1);
  const [activityPage, setActivityPage] = useState(1);
  const [draft, setDraft] = useState<Filters>(emptyFilters);
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [filterError, setFilterError] = useState<string | null>(null);
  const owner = useAccountRead(ownerId, useCallback(() => getOwner(ownerId), [ownerId]));
  const patients = useAccountRead(ownerId, useCallback(() => getPatients({ ownerId, sortBy: "name" }), [ownerId]));
  const sales = useAccountRead(ownerId, useCallback(() => getOwnerReceivables(ownerId, { page: salesPage, ...filters }), [ownerId, salesPage, filters]), refresh);
  const activity = useAccountRead(ownerId, useCallback(() => getOwnerReceivablesActivity(ownerId, { page: activityPage }), [ownerId, activityPage]), refresh);

  // Browser back/forward may restore this screen from cache. Refetch on return;
  // ordinary route mounts also load afresh, without a timer or polling.
  useEffect(() => {
    const update = () => setRefresh((value) => value + 1);
    window.addEventListener("pageshow", update);
    window.addEventListener("focus", update);
    return () => { window.removeEventListener("pageshow", update); window.removeEventListener("focus", update); };
  }, []);
  useEffect(() => {
    if (sales.data && salesPage > Math.max(1, sales.data.meta.total_pages)) setSalesPage(Math.max(1, sales.data.meta.total_pages));
  }, [sales.data, salesPage]);
  useEffect(() => {
    if (activity.data && activityPage > Math.max(1, activity.data.meta.total_pages)) setActivityPage(Math.max(1, activity.data.meta.total_pages));
  }, [activity.data, activityPage]);

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    if (draft.dateFrom && draft.dateTo && draft.dateFrom > draft.dateTo) {
      setFilterError("La fecha desde debe ser anterior o igual a la fecha hasta.");
      return;
    }
    setFilterError(null); setSalesPage(1); setFilters({ ...draft });
  }

  const data = sales.data?.data;
  const money = resolveMoneyPreferences(data?.currency && data.locale ? { currency_code: data.currency, locale: data.locale } : null, data?.currency);
  const configured = data?.tracking_configured;
  const hasFilters = Boolean(filters.dateFrom || filters.dateTo || filters.patientId);
  const updating = sales.loading || activity.loading;

  return <div className="page-stack owner-account-page">
    <header className="screen-heading list-page__header">
      <div><Link className="back-link" href={`/owners/${ownerId}`}><ArrowLeft size={18} aria-hidden="true" /> Volver al propietario</Link>
        <h1>Cuenta corriente</h1>{owner.data ? <p>{owner.data.data.full_name}</p> : null}
        {owner.data?.data.is_active === false ? <span className="badge">Propietario archivado</span> : null}
      </div>
      <button className="secondary-button" type="button" disabled={updating} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={17} aria-hidden="true" /> Actualizar</button>
    </header>
    {owner.loading ? <p role="status">Cargando propietario…</p> : owner.error ? <div className="error-state" role="alert">{owner.error}</div> : <>
      <section className="panel" aria-label="Resumen de cuenta corriente" aria-busy={sales.loading}>
        {sales.loading ? <p role="status">Cargando saldo pendiente…</p> : sales.error ? <div className="error-state" role="alert">{sales.error}</div> : configured === false ?
          <p className="empty-state">El control de cuentas por cobrar aún no está configurado para esta clínica.</p> : data ? <>
            <dl className="owner-account-summary"><div><dt>Saldo pendiente global</dt><dd>{formatExactCurrency(data.total_outstanding_ars, money)}</dd></div><div><dt>Ventas pendientes</dt><dd>{data.open_sales_count}</dd></div></dl>
            <p className="owner-receivables-scope">Ventas confirmadas desde {data.tracking_started_at ? formatDate(data.tracking_started_at, money.locale) : "el inicio del control"}. El saldo global no cambia al filtrar la lista.</p>
          </> : null}
      </section>
      {configured === true ? <>
        <section className="panel" aria-labelledby="account-sales-title" aria-busy={sales.loading}>
          <div className="section-heading"><h2 id="account-sales-title">Ventas pendientes</h2><p>Abre una venta para registrar un cobro mediante su flujo habitual. Los filtros de fecha usan la fecha de venta.</p></div>
          <form className="owner-account-filters" aria-label="Filtros de ventas pendientes" onSubmit={applyFilters}>
            <label className="field"><span>Fecha desde</span><input type="date" value={draft.dateFrom} onChange={(event) => setDraft((value) => ({ ...value, dateFrom: event.target.value }))} /></label>
            <label className="field"><span>Fecha hasta</span><input type="date" value={draft.dateTo} onChange={(event) => setDraft((value) => ({ ...value, dateTo: event.target.value }))} /></label>
            <label className="field"><span>Paciente</span><select value={draft.patientId} disabled={patients.loading || Boolean(patients.error)} onChange={(event) => setDraft((value) => ({ ...value, patientId: event.target.value }))}><option value="">Todos los pacientes</option>{patients.data?.data.map((patient) => <option key={patient.id} value={patient.id}>{patient.name}</option>)}</select></label>
            <div className="owner-account-filter-actions"><button className="secondary-button" type="submit">Aplicar filtros</button><button className="secondary-button" type="button" onClick={() => { setDraft(emptyFilters); setFilters(emptyFilters); setSalesPage(1); setFilterError(null); }}>Limpiar filtros</button></div>
          </form>
          {patients.error ? <p role="alert">No pudimos cargar el filtro de pacientes. Puedes usar las fechas.</p> : null}
          {filterError ? <p className="error-state" role="alert">{filterError}</p> : null}
          {sales.loading ? <p role="status">Cargando ventas pendientes…</p> : data.sales.length ? <ul className="owner-account-sales">{data.sales.map((sale) => <li className="owner-account-sale" key={sale.sale_id}>
            <div className="owner-account-sale-heading"><div><h3>Venta #{sale.sale_id.slice(0, 8).toUpperCase()}</h3><p>{formatDate(`${sale.sale_date}T12:00:00`, money.locale)} · {sale.patient_name_snapshot || "Sin paciente"}</p><small>Confirmada {formatDate(sale.confirmed_at, money.locale, true)}</small></div><span className="badge">{sale.payment_status === "partial" ? "Cobro parcial" : "Sin cobrar"}</span></div>
            <dl className="owner-account-amounts"><div><dt>Total</dt><dd>{formatExactCurrency(sale.total_ars, resolveMoneyPreferences({ currency_code: money.currencyCode, locale: money.locale }, sale.currency))}</dd></div><div><dt>Pagado</dt><dd>{formatExactCurrency(sale.paid_total_ars, resolveMoneyPreferences({ currency_code: money.currencyCode, locale: money.locale }, sale.currency))}</dd></div><div><dt>Pendiente</dt><dd><strong>{formatExactCurrency(sale.balance_due_ars, resolveMoneyPreferences({ currency_code: money.currencyCode, locale: money.locale }, sale.currency))}</strong></dd></div></dl>
            <Link className="secondary-button" href={`/sales/${sale.sale_id}`}>Ver venta<span className="sr-only"> #{sale.sale_id.slice(0, 8).toUpperCase()}</span></Link>
          </li>)}</ul> : <p className="empty-state">{hasFilters ? "No hay ventas pendientes que coincidan con estos filtros." : "No hay ventas con saldo pendiente."}</p>}
          {!sales.loading ? <AccountPagination meta={sales.data!.meta} label="ventas pendientes" onPage={setSalesPage} /> : null}
        </section>
        <section className="panel" aria-labelledby="account-activity-title" aria-busy={activity.loading}>
          <div className="section-heading"><h2 id="account-activity-title">Actividad de cuenta corriente</h2><p>Historial desde el inicio del control, independiente de los filtros de pendientes. Los importes explican eventos; no representan un saldo acumulado ni un crédito.</p></div>
          {activity.loading ? <p role="status">Cargando actividad…</p> : activity.error ? <div className="error-state" role="alert">{activity.error}</div> : activity.data?.data.events.length ? <>
            <ol className="owner-account-activity">{activity.data.data.events.map((event) => <li key={event.event_id}>
              <div className="owner-account-event-heading"><div><time dateTime={event.occurred_at}>{formatDate(event.occurred_at, money.locale, true)}</time><h3>{labelEvent(event)}{event.payment_method_label ? ` · ${event.payment_method_label}` : ""}</h3></div>{event.amount_ars !== null ? <strong className="owner-account-event-amount">{event.type === "payment_recorded" ? "−" : "+"} {formatExactCurrency(event.amount_ars, resolveMoneyPreferences({ currency_code: money.currencyCode, locale: money.locale }, event.currency))}</strong> : null}</div>
              <p><Link href={`/sales/${event.sale_id}`}>Venta #{event.sale_id.slice(0, 8).toUpperCase()}</Link>{event.patient_name_snapshot ? ` · ${event.patient_name_snapshot}` : ""}</p>
              {event.type === "payment_recorded" && event.payment_is_active === false ? <p>Este cobro fue anulado; su anulación figura como evento separado.</p> : null}
              {event.type === "sale_reversed" ? <p>Venta excluida del saldo pendiente. La reversión no devuelve ni anula cobros automáticamente.</p> : null}
              {event.reference ? <p>Referencia: {event.reference}</p> : null}{event.notes ? <p>Notas: {event.notes}</p> : null}{event.reason ? <p>Motivo: {event.reason}</p> : null}
            </li>)}</ol>
            <AccountPagination meta={activity.data.meta} label="actividad" onPage={setActivityPage} />
          </> : <p className="empty-state">Sin actividad desde el inicio del control.</p>}
        </section>
      </> : null}
    </>}
  </div>;
}

function AccountPagination({ meta, label, onPage }: { meta: OwnerReceivablesResponse["meta"]; label: string; onPage: (page: number) => void }) {
  return meta.total_pages > 1 ? <nav className="list-pagination" aria-label={`Paginación de ${label}`}><span>Página {meta.page} de {meta.total_pages} · {meta.total} resultados</span><div className="list-pagination__actions"><button className="secondary-button" type="button" disabled={meta.page <= 1} onClick={() => onPage(meta.page - 1)}>Anterior</button><button className="secondary-button" type="button" disabled={meta.page >= meta.total_pages} onClick={() => onPage(meta.page + 1)}>Siguiente</button></div></nav> : null;
}
function labelEvent(event: OwnerReceivablesActivityEvent) {
  return { sale_confirmed: "Venta confirmada", payment_recorded: "Pago registrado", payment_cancelled: "Pago anulado", sale_reversed: "Venta revertida" }[event.type];
}
function formatDate(value: string, locale: string, withTime = false) {
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", ...(withTime ? { timeStyle: "short" as const } : {}) }).format(new Date(value));
}

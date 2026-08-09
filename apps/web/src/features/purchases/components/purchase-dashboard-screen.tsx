"use client";

import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  ClipboardList,
  FileWarning,
  Plus,
  ReceiptText,
  RefreshCw,
  RotateCcw,
  ShoppingCart,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  formatPurchaseCurrency,
  formatPurchaseDate,
  formatPurchaseDateTime,
  formatPurchaseUser,
  labelPurchaseDocumentType,
  labelPurchaseStatus,
} from "@/features/purchases/components/purchase-helpers";
import { getApiErrorMessage } from "@/lib/api";
import { getPurchaseDashboard, getPurchaseFilterOptions } from "@/services/purchases";
import { getSuppliers } from "@/services/suppliers";
import type {
  PurchaseCreatorOption,
  PurchaseDashboard,
  PurchaseDashboardAttention,
  PurchaseDashboardFilters,
  PurchaseDocumentType,
  SupplierSummary,
} from "@/types/api";


type DashboardQuery = {
  dateFrom: string;
  dateTo: string;
  supplierId: string;
  createdByUserId: string;
  documentType: PurchaseDocumentType | "";
};

export function PurchaseDashboardScreen() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryString = searchParams.toString();
  const query = useMemo(() => readDashboardQuery(queryString), [queryString]);
  const [data, setData] = useState<PurchaseDashboard | null>(null);
  const [suppliers, setSuppliers] = useState<SupplierSummary[]>([]);
  const [creators, setCreators] = useState<PurchaseCreatorOption[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const filters = useMemo<PurchaseDashboardFilters>(() => ({
    date_from: query.dateFrom,
    date_to: query.dateTo,
    supplier_id: query.supplierId || undefined,
    created_by_user_id: query.createdByUserId || undefined,
    document_type: query.documentType || undefined,
  }), [query]);

  const updateUrl = useCallback((updates: Record<string, string | null>) => {
    const params = new URLSearchParams(queryString);
    Object.entries(updates).forEach(([key, value]) => {
      if (!value) params.delete(key);
      else params.set(key, value);
    });
    router.push(`${pathname}?${params.toString()}`, { scroll: false });
  }, [pathname, queryString, router]);

  const loadDashboard = useCallback(async () => {
    if (data) setIsRefreshing(true);
    else setIsLoading(true);
    setErrorMessage(null);
    try {
      const response = await getPurchaseDashboard(filters);
      setData(response.data);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [data, filters]);

  useEffect(() => {
    const params = new URLSearchParams(queryString);
    let changed = false;
    if (!params.has("date_from")) {
      params.set("date_from", query.dateFrom);
      changed = true;
    }
    if (!params.has("date_to")) {
      params.set("date_to", query.dateTo);
      changed = true;
    }
    if (changed) router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }, [pathname, query.dateFrom, query.dateTo, queryString, router]);

  useEffect(() => { void loadDashboard(); }, [filters]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    Promise.all([
      getSuppliers({ is_active: true, page_size: 100, sort_by: "name", sort_direction: "asc" }),
      getSuppliers({ is_active: false, page_size: 100, sort_by: "name", sort_direction: "asc" }),
      getPurchaseFilterOptions(),
    ])
      .then(([active, inactive, options]) => {
        setSuppliers([...active.data, ...inactive.data].sort((left, right) => left.name.localeCompare(right.name)));
        setCreators(options.data.creators);
      })
      .catch(() => undefined);
  }, []);

  const listHref = useCallback((updates: Record<string, string | null> = {}) => {
    const params = new URLSearchParams();
    params.set("date_from", query.dateFrom);
    params.set("date_to", query.dateTo);
    if (query.supplierId) params.set("supplier_id", query.supplierId);
    if (query.createdByUserId) params.set("created_by_user_id", query.createdByUserId);
    if (query.documentType) params.set("document_type", query.documentType);
    Object.entries(updates).forEach(([key, value]) => {
      if (!value) params.delete(key);
      else params.set(key, value);
    });
    return `/purchases?${params.toString()}`;
  }, [query]);

  return (
    <div className="page-stack purchases-page purchase-dashboard-page">
      <section className="screen-heading list-page__header">
        <div>
          <p className="eyebrow">Operaciones</p>
          <h1>Dashboard de compras</h1>
          <p>{data ? `Actualizado ${formatPurchaseDateTime(data.generated_at)}` : "Totales, documentación y actividad del período"}</p>
        </div>
        <div className="screen-heading__actions">
          <Link className="secondary-button" href="/purchases"><ShoppingCart size={17} /> Ver compras</Link>
          <Link className="secondary-button" href="/suppliers"><Building2 size={17} /> Proveedores</Link>
          <Link className="primary-button" href="/purchases/new"><Plus size={17} /> Nueva compra</Link>
        </div>
      </section>

      <section className="panel purchase-dashboard-filters" aria-label="Filtros del dashboard de compras">
        <label className="field"><span>Desde</span><input type="date" value={query.dateFrom} onChange={(event) => updateUrl({ date_from: event.target.value })} /></label>
        <label className="field"><span>Hasta</span><input type="date" value={query.dateTo} onChange={(event) => updateUrl({ date_to: event.target.value })} /></label>
        <label className="field"><span>Proveedor</span><select value={query.supplierId} onChange={(event) => updateUrl({ supplier_id: event.target.value })}><option value="">Todos</option>{suppliers.map((supplier) => <option value={supplier.id} key={supplier.id}>{supplier.name}{supplier.is_active ? "" : " (inactivo)"}</option>)}</select></label>
        <label className="field"><span>Creador</span><select value={query.createdByUserId} onChange={(event) => updateUrl({ created_by_user_id: event.target.value })}><option value="">Todos</option>{creators.map((creator) => <option value={creator.id} key={creator.id}>{creator.full_name}{creator.is_active ? "" : " (inactivo)"}</option>)}</select></label>
        <label className="field"><span>Tipo de comprobante</span><select value={query.documentType} onChange={(event) => updateUrl({ document_type: event.target.value })}><option value="">Todos</option><option value="invoice">Factura</option><option value="receipt">Recibo</option><option value="ticket">Ticket</option><option value="delivery_note">Remito</option><option value="other">Otro</option></select></label>
        <button className="secondary-button" type="button" onClick={() => { const period = currentMonthRange(); updateUrl({ date_from: period.from, date_to: period.to, supplier_id: null, created_by_user_id: null, document_type: null }); }}>Limpiar</button>
        <button className="secondary-button" type="button" disabled={isRefreshing} onClick={() => void loadDashboard()}><RefreshCw size={17} /> {isRefreshing ? "Actualizando..." : "Actualizar"}</button>
      </section>

      {errorMessage ? <section className="error-state" role="alert">{errorMessage}</section> : null}
      {isLoading ? <div className="loading-card" aria-label="Cargando dashboard de compras" /> : null}

      {data ? <>
        <section className="purchase-dashboard-metrics" aria-label="Métricas de compras">
          <DashboardMetric href={listHref()} label="Total registrado" value={formatPurchaseCurrency(data.summary.registered_total_ars)} icon={<ReceiptText size={19} />} />
          <DashboardMetric href={listHref({ status: "received" })} label="Total recibido" value={formatPurchaseCurrency(data.summary.received_total_ars)} icon={<CheckCircle2 size={19} />} />
          <DashboardMetric label="IVA registrado" value={formatPurchaseCurrency(data.summary.registered_tax_total_ars)} icon={<ReceiptText size={19} />} />
          <DashboardMetric href={listHref({ status: "draft" })} label="Borradores" value={data.summary.draft_count} icon={<ClipboardList size={19} />} />
          <DashboardMetric href={listHref({ status: "received" })} label="Recibidas" value={data.summary.received_count} icon={<CheckCircle2 size={19} />} />
          <DashboardMetric href={listHref({ attachment_status: "pending" })} label="Pendientes de comprobante" value={data.summary.attachment_pending_count} tone="warning" icon={<FileWarning size={19} />} />
          <DashboardMetric href={listHref({ status: "reversed" })} label="Revertidas" value={data.summary.reversed_count} tone="info" icon={<RotateCcw size={19} />} />
          <DashboardMetric href={listHref()} label="Compras del período" value={data.summary.purchase_count} icon={<ShoppingCart size={19} />} />
        </section>

        <section className="panel purchase-dashboard-attention">
          <div className="section-heading-inline"><div><h2>Requieren atención</h2><p>Condiciones documentales y operativas derivadas.</p></div><Link href={listHref({ attachment_status: "pending" })}>Ver pendientes</Link></div>
          {data.attention.length === 0 ? <p className="empty-state empty-state--compact">No hay compras que requieran atención en este período.</p> : <div className="purchase-dashboard-attention-list">{data.attention.map((item) => <AttentionRow item={item} key={item.id} />)}</div>}
        </section>

        <section className="purchase-dashboard-columns">
          <section className="panel purchase-dashboard-recent">
            <div className="section-heading-inline"><h2>Compras recientes</h2><Link href={listHref()}>Ver listado</Link></div>
            {data.recent_purchases.length === 0 ? <p className="empty-state empty-state--compact">Sin compras en el período.</p> : <div className="purchase-dashboard-recent-list">{data.recent_purchases.map((purchase) => {
              const userLabel = formatPurchaseUser(purchase.created_by_user_name, purchase.created_by_user_email);
              return <Link href={`/purchases/${purchase.id}`} className="purchase-dashboard-recent-row" key={purchase.id} aria-label={`Abrir compra de ${purchase.supplier_name}`}>
                <span className="purchase-dashboard-recent-heading">
                  <strong className="purchase-dashboard-recent-supplier" title={purchase.supplier_name}>{purchase.supplier_name}</strong>
                  <strong className="purchase-dashboard-recent-total">{formatPurchaseCurrency(purchase.total_ars)}</strong>
                </span>
                <span className="purchase-dashboard-recent-meta">
                  <span className="purchase-dashboard-recent-date-status">
                    <time dateTime={purchase.purchase_date}>{formatPurchaseDate(purchase.purchase_date)}</time>
                    <span className={`badge purchase-status purchase-status--${purchase.status}`}>{labelPurchaseStatus(purchase.status)}</span>
                  </span>
                  <small className="purchase-dashboard-recent-user" title={userLabel}>Usuario: {userLabel}</small>
                </span>
              </Link>;
            })}</div>}
          </section>

          <section className="panel purchase-dashboard-suppliers">
            <div className="section-heading-inline"><h2>Principales proveedores</h2><Link href="/suppliers">Ver proveedores</Link></div>
            {data.top_suppliers.length === 0 ? <p className="empty-state empty-state--compact">Sin proveedores en el período.</p> : <div className="purchase-dashboard-supplier-list">{data.top_suppliers.map((supplier) => {
              const useReceived = data.top_suppliers.some((item) => Number(item.received_total_ars) > 0);
              const amount = Number(useReceived ? supplier.received_total_ars : supplier.registered_total_ars);
              const maximum = Math.max(...data.top_suppliers.map((item) => Number(useReceived ? item.received_total_ars : item.registered_total_ars)), 1);
              return <Link href={listHref({ supplier_id: supplier.supplier_id })} className="purchase-dashboard-supplier-row" key={supplier.supplier_id}><span><strong>{supplier.supplier_name}</strong><small>{supplier.purchase_count} compra{supplier.purchase_count === 1 ? "" : "s"} · {useReceived ? "recibido" : "registrado"}</small></span><strong>{formatPurchaseCurrency(amount)}</strong><span className="purchase-dashboard-supplier-bar" aria-hidden="true"><i style={{ width: `${Math.max(3, amount / maximum * 100)}%` }} /></span></Link>;
            })}</div>}
          </section>
        </section>
      </> : null}
    </div>
  );
}

function DashboardMetric({ label, value, href, icon, tone }: { label: string; value: ReactNode; href?: string; icon: ReactNode; tone?: "warning" | "info" }) {
  const className = `purchase-dashboard-metric${tone ? ` purchase-dashboard-metric--${tone}` : ""}`;
  const content = <><span aria-hidden="true">{icon}</span><small>{label}</small><strong>{value}</strong></>;
  return href ? <Link className={className} href={href}>{content}</Link> : <article className={className}>{content}</article>;
}

function AttentionRow({ item }: { item: PurchaseDashboardAttention }) {
  return <Link href={`/purchases/${item.id}`} className={`purchase-dashboard-attention-row purchase-dashboard-attention-row--${item.priority}`}><AlertTriangle size={18} /><span><strong>{item.supplier_name}</strong><small>{formatPurchaseDate(item.purchase_date)} · {item.document_number || "Sin número"}</small></span><span className="purchase-dashboard-alert-labels">{item.alerts.map((alert) => <small key={alert}>{attentionLabel(alert)}</small>)}</span><strong>{formatPurchaseCurrency(item.total_ars)}</strong></Link>;
}

function attentionLabel(alert: PurchaseDashboardAttention["alerts"][number]) {
  if (alert === "old_draft") return "Borrador antiguo";
  if (alert === "attachment_pending") return "Sin comprobante";
  if (alert === "document_number_missing") return "Sin número";
  return "Recepción revertida";
}

function readDashboardQuery(queryString: string): DashboardQuery {
  const params = new URLSearchParams(queryString);
  const defaults = currentMonthRange();
  const documentType = params.get("document_type");
  return {
    dateFrom: readIsoDate(params.get("date_from")) || defaults.from,
    dateTo: readIsoDate(params.get("date_to")) || defaults.to,
    supplierId: params.get("supplier_id") || "",
    createdByUserId: params.get("created_by_user_id") || "",
    documentType: ["invoice", "receipt", "ticket", "delivery_note", "other"].includes(documentType ?? "") ? documentType as PurchaseDocumentType : "",
  };
}

function currentMonthRange() {
  const today = new Date();
  return { from: toDateInput(new Date(today.getFullYear(), today.getMonth(), 1)), to: toDateInput(new Date(today.getFullYear(), today.getMonth() + 1, 0)) };
}

function toDateInput(value: Date) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

function readIsoDate(value: string | null) {
  return value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : "";
}

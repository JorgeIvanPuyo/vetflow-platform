"use client";

import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Boxes,
  ChevronRight,
  ClipboardList,
  PackageCheck,
  RefreshCw,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  formatInventoryCurrency,
  formatInventoryDateTime,
  getInventoryCategoryLabel,
  getInventoryMovementTypeLabel,
} from "@/features/inventory/components/inventory-helpers";
import {
  formatUserName,
  labelBulkOperation,
  labelBulkStatus,
} from "@/features/inventory/components/inventory-bulk-operations-screen";
import { ApiClientError, getApiErrorMessage } from "@/lib/api";
import {
  getInventoryDashboard,
  getInventoryFilterOptions,
} from "@/services/inventory";
import type {
  InventoryCategory,
  InventoryDashboard,
  InventoryDashboardFilters,
  InventoryFilterOptions,
  InventoryMovement,
} from "@/types/api";

type DashboardState = {
  isLoading: boolean;
  isRefreshing: boolean;
  data: InventoryDashboard | null;
  errorMessage: string | null;
};

type DashboardQuery = {
  category: InventoryCategory | "all";
  brand: string;
  supplier: string;
  activeState: "all" | "true" | "false";
  dateFrom: string;
  dateTo: string;
};

const DEFAULT_DAYS = 30;
const categoryOptions: Array<{ value: InventoryCategory | "all"; label: string }> = [
  { value: "all", label: "Todas" },
  { value: "medication", label: "Medicamentos" },
  { value: "vaccine", label: "Vacunas" },
  { value: "supply", label: "Insumos" },
  { value: "food", label: "Alimentos" },
  { value: "accessory", label: "Accesorios" },
  { value: "other", label: "Otros" },
];

export function InventoryDashboardScreen() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryString = searchParams.toString();
  const query = useMemo(() => readDashboardQuery(queryString), [queryString]);
  const [state, setState] = useState<DashboardState>({
    isLoading: true,
    isRefreshing: false,
    data: null,
    errorMessage: null,
  });
  const [filterOptions, setFilterOptions] = useState<InventoryFilterOptions>({
    brands: [],
    suppliers: [],
  });

  const filters = useMemo<InventoryDashboardFilters>(() => {
    return {
      category: query.category === "all" ? null : query.category,
      brand: query.brand || null,
      supplier: query.supplier || null,
      is_active:
        query.activeState === "all"
          ? null
          : query.activeState === "true",
      date_from: query.dateFrom,
      date_to: query.dateTo,
    };
  }, [query]);

  const updateUrl = useCallback(
    (updates: Partial<Record<string, string | boolean | null | undefined>>) => {
      const params = new URLSearchParams(queryString);
      Object.entries(updates).forEach(([key, value]) => {
        if (value === undefined || value === null || value === "" || value === "all") {
          params.delete(key);
          return;
        }
        params.set(key, String(value));
      });
      router.push(`${pathname}${params.toString() ? `?${params.toString()}` : ""}`, { scroll: false });
    },
    [pathname, queryString, router],
  );

  const loadVersion = useRef(0);

  const loadDashboard = useCallback(async () => {
    const version = ++loadVersion.current;
    setState((current) => ({
      ...current,
      isLoading: current.data === null,
      isRefreshing: current.data !== null,
      errorMessage: null,
    }));
    try {
      const response = await getInventoryDashboard(filters);
      if (version !== loadVersion.current) return;
      setState({
        data: response.data,
        isLoading: false,
        isRefreshing: false,
        errorMessage: null,
      });
    } catch (error) {
      if (version !== loadVersion.current || (error instanceof ApiClientError && error.code === "read_cancelled") || (error instanceof DOMException && error.name === "AbortError")) return;
      setState((current) => ({
        ...current,
        isLoading: false,
        isRefreshing: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }, [filters]);

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
    if (changed) {
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    }
  }, [pathname, query.dateFrom, query.dateTo, queryString, router]);

  useEffect(() => {
    void loadDashboard();
    return () => { loadVersion.current += 1; };
  }, [loadDashboard]);

  useEffect(() => {
    let isMounted = true;
    getInventoryFilterOptions()
      .then((response) => {
        if (isMounted) {
          setFilterOptions(response.data);
        }
      })
      .catch(() => undefined);
    return () => {
      isMounted = false;
    };
  }, []);

  const data = state.data;

  return (
    <div className="page-stack inventory-page inventory-dashboard-page">
      <section className="screen-heading list-page__header">
        <div>
          <Link className="back-link" href="/inventory">
            <ArrowLeft size={18} />
            Productos
          </Link>
          <h1>Dashboard de inventario</h1>
          <p>
            {data
              ? `Actualizado ${formatInventoryDateTime(data.generated_at)}`
              : "Vista operativa de stock, alertas y actividad reciente"}
          </p>
        </div>
        <div className="inventory-header-actions">
          <Link className="secondary-button" href="/inventory">
            Productos
          </Link>
          <Link className="secondary-button" href="/inventory/movements">
            Movimientos
          </Link>
          <Link className="secondary-button" href="/inventory/import">
            Importar
          </Link>
          <Link className="secondary-button" href="/inventory/bulk-operations">
            Operaciones grupales
          </Link>
          <button className="secondary-button" type="button" onClick={() => void loadDashboard()}>
            <RefreshCw size={18} />
            Actualizar
          </button>
        </div>
      </section>

      <section className="panel inventory-dashboard-filters" aria-label="Filtros de dashboard">
        <label className="field">
          <span>Categoría</span>
          <select
            value={query.category}
            onChange={(event) => updateUrl({ category: event.target.value })}
          >
            {categoryOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Marca</span>
          <select value={query.brand} onChange={(event) => updateUrl({ brand: event.target.value })}>
            <option value="">Todas</option>
            {filterOptions.brands.map((brand) => (
              <option key={brand} value={brand}>
                {brand}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Proveedor</span>
          <select value={query.supplier} onChange={(event) => updateUrl({ supplier: event.target.value })}>
            <option value="">Todos</option>
            {filterOptions.suppliers.map((supplier) => (
              <option key={supplier} value={supplier}>
                {supplier}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Estado</span>
          <select value={query.activeState} onChange={(event) => updateUrl({ is_active: event.target.value })}>
            <option value="all">Todos</option>
            <option value="true">Activos</option>
            <option value="false">Inactivos</option>
          </select>
        </label>
        <label className="field">
          <span>Desde</span>
          <input type="date" value={query.dateFrom} onChange={(event) => updateUrl({ date_from: event.target.value })} />
        </label>
        <label className="field">
          <span>Hasta</span>
          <input type="date" value={query.dateTo} onChange={(event) => updateUrl({ date_to: event.target.value })} />
        </label>
        <button className="secondary-button" type="button" onClick={() => updateUrl({
          category: null,
          brand: null,
          supplier: null,
          is_active: null,
          date_from: defaultDateRange().from,
          date_to: defaultDateRange().to,
        })}>
          Limpiar
        </button>
      </section>

      {state.errorMessage ? (
        <section className="error-state">
          <strong>No pudimos cargar el dashboard.</strong> {state.errorMessage}
        </section>
      ) : null}
      {state.isLoading ? <div className="loading-card" aria-label="Cargando dashboard de inventario" /> : null}

      {data ? (
        <>
          <section className="inventory-dashboard-kpis" aria-label="Indicadores de inventario">
            <DashboardMetric href="/inventory" label="Productos" value={data.indicators.total_products} icon={<Boxes size={19} />} />
            <DashboardMetric href="/inventory?stock_status=in_stock" label="Disponibles" value={data.indicators.in_stock_products} icon={<PackageCheck size={19} />} />
            <DashboardMetric href="/inventory?stock_status=low_stock" label="Stock bajo" value={data.indicators.low_stock_products} tone="warning" icon={<AlertTriangle size={19} />} />
            <DashboardMetric href="/inventory?stock_status=out_of_stock" label="Agotados" value={data.indicators.out_of_stock_products} tone="danger-soft" icon={<AlertTriangle size={19} />} />
            <DashboardMetric href="/inventory?stock_status=negative" label="Negativos" value={data.indicators.negative_stock_products} tone="danger" icon={<AlertTriangle size={19} />} />
            <DashboardMetric href="/inventory?is_active=true" label="Activos" value={data.indicators.active_products} icon={<ClipboardList size={19} />} />
            <DashboardMetric href="/inventory?is_active=false" label="Inactivos" value={data.indicators.inactive_products} icon={<ClipboardList size={19} />} />
            <DashboardMetric label="Movimientos" value={data.movement_metrics.total_movements} icon={<Activity size={19} />} />
          </section>

          <section className="inventory-dashboard-band" aria-label="Valoración de inventario">
            <article>
              <span>Valor estimado a costo</span>
              <strong>{formatInventoryCurrency(data.valuation.estimated_cost_value_ars)}</strong>
            </article>
            <article>
              <span>Valor estimado a precio de venta</span>
              <strong>{formatInventoryCurrency(data.valuation.estimated_sale_value_ars)}</strong>
            </article>
            <p>{data.valuation.disclaimer}</p>
          </section>

          <section className="inventory-dashboard-grid">
            <section className="panel inventory-dashboard-alerts" aria-label="Alertas operativas">
              <div className="section-heading-inline">
                <h2>Alertas</h2>
                <Link href="/inventory?stock_status=low_stock">Ver todos</Link>
              </div>
              <div className="inventory-dashboard-alert-list">
                {data.alerts.map((alert) => (
                  <div key={alert.alert_type} className={`inventory-alert-pill inventory-alert-pill--${alert.priority}`}>
                    <span>{alert.label}</span>
                    <strong>{alert.count}</strong>
                  </div>
                ))}
              </div>
            </section>

            <section className="panel inventory-dashboard-attention" aria-label="Productos que requieren atención">
              <div className="section-heading-inline">
                <h2>Requieren atención</h2>
                <Link href="/inventory?stock_status=low_stock">Ver todos</Link>
              </div>
              {data.attention_items.length === 0 ? (
                <p className="empty-state empty-state--compact">No hay productos con alertas para estos filtros.</p>
              ) : (
                <div className="inventory-dashboard-attention-list">
                  {data.attention_items.map((item) => (
                    <Link key={item.id} className="inventory-dashboard-attention-item" href={`/inventory/${item.id}`}>
                      <span>
                        <strong>{item.name}</strong>
                        <small>{item.internal_code} · {getInventoryCategoryLabel(item.category)}</small>
                      </span>
                      <span>
                        Stock {item.current_stock} / mín. {item.minimum_stock}
                      </span>
                      <ChevronRight size={16} />
                    </Link>
                  ))}
                </div>
              )}
            </section>
          </section>

          <section className="inventory-dashboard-grid inventory-dashboard-grid--activity">
            <ActivityPanel title="Movimientos recientes" isEmpty={data.activity.recent_movements.length === 0}>
              {data.activity.recent_movements.map((movement) => (
                <RecentMovementRow key={movement.id} movement={movement} />
              ))}
            </ActivityPanel>
            <ActivityPanel title="Importaciones recientes" isEmpty={data.activity.recent_imports.length === 0}>
              {data.activity.recent_imports.map((entry) => (
                <Link key={entry.id} className="inventory-dashboard-activity-row" href={`/inventory/import?step=${entry.status === "confirmed" ? "result" : "preview"}&import_id=${entry.id}&filter=all`}>
                  <span>
                    <strong>{entry.original_filename}</strong>
                    <small>{labelImportMode(entry.mode)} · {formatUserName(entry.created_by_user_name, entry.created_by_user_email)}</small>
                  </span>
                  <span>{entry.row_count} filas</span>
                </Link>
              ))}
            </ActivityPanel>
            <ActivityPanel title="Operaciones grupales recientes" isEmpty={data.activity.recent_bulk_operations.length === 0}>
              {data.activity.recent_bulk_operations.map((operation) => (
                <Link key={operation.id} className="inventory-dashboard-activity-row" href={`/inventory/bulk-operations/${operation.id}`}>
                  <span>
                    <strong>{labelBulkOperation(operation.operation_type)}</strong>
                    <small>{formatUserName(operation.created_by_user_name, operation.created_by_user_email)}</small>
                  </span>
                  <span>{labelBulkStatus(operation.status)} · {operation.affected_count}</span>
                </Link>
              ))}
            </ActivityPanel>
          </section>
        </>
      ) : null}
    </div>
  );
}

function DashboardMetric({
  label,
  value,
  href,
  tone,
  icon,
}: {
  label: string;
  value: number;
  href?: string;
  tone?: "warning" | "danger" | "danger-soft";
  icon: ReactNode;
}) {
  const className = `inventory-dashboard-kpi${tone ? ` inventory-dashboard-kpi--${tone}` : ""}`;
  const content = (
    <>
      <span aria-hidden="true">{icon}</span>
      <small>{label}</small>
      <strong>{value}</strong>
    </>
  );
  if (href) {
    return (
      <Link className={className} href={href}>
        {content}
      </Link>
    );
  }
  return <article className={className}>{content}</article>;
}

function ActivityPanel({ title, children, isEmpty }: { title: string; children: ReactNode; isEmpty: boolean }) {
  return (
    <section className="panel inventory-dashboard-activity-panel">
      <h2>{title}</h2>
      <div>{isEmpty ? <p className="empty-state empty-state--compact">Sin actividad en el período.</p> : children}</div>
    </section>
  );
}

function RecentMovementRow({ movement }: { movement: InventoryMovement }) {
  return (
    <Link className="inventory-dashboard-activity-row" href={`/inventory/movements/${movement.id}`}>
      <span>
        <strong>{movement.inventory_item_name ?? "Producto"}</strong>
        <small>
          {movement.inventory_item_internal_code ?? "Sin código"} · {getInventoryMovementTypeLabel(movement.movement_type)}
        </small>
      </span>
      <span>
        {movement.quantity} · {formatUserName(movement.created_by_user_name, movement.created_by_user_email)}
      </span>
    </Link>
  );
}

function readDashboardQuery(queryString: string): DashboardQuery {
  const params = new URLSearchParams(queryString);
  const defaults = defaultDateRange();
  return {
    category: readCategory(params.get("category")),
    brand: params.get("brand")?.trim() || "",
    supplier: params.get("supplier")?.trim() || "",
    activeState: readActiveState(params.get("is_active")),
    dateFrom: readIsoDate(params.get("date_from")) || defaults.from,
    dateTo: readIsoDate(params.get("date_to")) || defaults.to,
  };
}

function readCategory(value: string | null): InventoryCategory | "all" {
  if (categoryOptions.some((option) => option.value === value)) {
    return value as InventoryCategory | "all";
  }
  return "all";
}

function readActiveState(value: string | null): DashboardQuery["activeState"] {
  if (value === "true" || value === "active") {
    return "true";
  }
  if (value === "false" || value === "inactive") {
    return "false";
  }
  return "all";
}

function readIsoDate(value: string | null) {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return "";
  }
  return value;
}

function defaultDateRange() {
  const end = new Date();
  const start = new Date(end);
  start.setDate(start.getDate() - DEFAULT_DAYS);
  return {
    from: toDateInput(start),
    to: toDateInput(end),
  };
}

function toDateInput(date: Date) {
  return date.toISOString().slice(0, 10);
}

function labelImportMode(mode: string) {
  return mode === "initial_load" ? "Carga inicial" : "Actualización";
}

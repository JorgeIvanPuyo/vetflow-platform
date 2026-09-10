"use client";

import { Building2, ChevronDown, LayoutDashboard, Plus, Search, ShoppingCart, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { useClinic } from "@/features/clinic/clinic-context";
import {
  formatPurchaseCurrency,
  formatPurchaseDate,
  labelPurchaseDocumentType,
  labelPurchaseStatus,
} from "@/features/purchases/components/purchase-helpers";
import { getApiErrorMessage } from "@/lib/api";
import { resolveMoneyPreferences } from "@/lib/money";
import { getPurchaseFilterOptions, getPurchases } from "@/services/purchases";
import { getSuppliers } from "@/services/suppliers";
import type { PurchaseCreatorOption, PurchaseDocumentType, PurchaseListFilters, PurchaseListSummary, PurchaseSummary, SupplierSummary } from "@/types/api";


const EMPTY_SUMMARY: PurchaseListSummary = {
  purchase_count: 0,
  subtotal_ars: "0.00",
  tax_total_ars: "0.00",
  total_ars: "0.00",
};


export function PurchasesScreen() {
  const { preferences } = useClinic();
  const moneyPreferences = resolveMoneyPreferences(preferences);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryString = searchParams.toString();
  const filters = useMemo(() => readFilters(queryString), [queryString]);
  const [searchValue, setSearchValue] = useState(filters.search ?? "");
  const [items, setItems] = useState<PurchaseSummary[]>([]);
  const [suppliers, setSuppliers] = useState<SupplierSummary[]>([]);
  const [creators, setCreators] = useState<PurchaseCreatorOption[]>([]);
  const [meta, setMeta] = useState({ page: 1, page_size: 20, total: 0, total_pages: 0, summary: EMPTY_SUMMARY });
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const activeAdvancedFilterCount = countAdvancedFilters(filters);
  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false);

  useEffect(() => setSearchValue(filters.search ?? ""), [filters.search]);

  const load = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const response = await getPurchases(filters);
      setItems(response.data);
      setMeta(response.meta);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    void load();
  }, [load]);

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
      .catch(() => { setSuppliers([]); setCreators([]); });
  }, []);

  function updateFilters(updates: Record<string, string | number | null>) {
    const params = new URLSearchParams(queryString);
    Object.entries(updates).forEach(([key, value]) => {
      if (value === null || value === "") params.delete(key);
      else params.set(key, String(value));
    });
    if (!("page" in updates)) params.delete("page");
    router.push(`${pathname}${params.toString() ? `?${params}` : ""}`, { scroll: false });
  }

  function handleSearch(event: FormEvent) {
    event.preventDefault();
    updateFilters({ search: searchValue.trim() || null });
  }

  function clearFilters() {
    setSearchValue("");
    setIsFilterPanelOpen(false);
    router.push(pathname, { scroll: false });
  }

  const hasFilters = Boolean(
    filters.search || filters.supplier_id || filters.status || filters.document_type || filters.attachment_status || filters.date_from || filters.date_to || filters.created_by_user_id,
  );

  return (
    <div className="page-stack purchases-page">
      <section className="screen-heading list-page__header">
        <div>
          <p className="eyebrow">Operaciones</p>
          <h1>Compras</h1>
          <p>Registra borradores y controla su recepción trazable en inventario.</p>
        </div>
        <div className="screen-heading__actions">
          <Link className="secondary-button" href="/purchases/dashboard"><LayoutDashboard size={18} /> Dashboard</Link>
          <Link className="secondary-button" href="/suppliers"><Building2 size={18} /> Proveedores</Link>
          <Link className="primary-button" href="/purchases/new"><Plus size={18} /> Nueva compra</Link>
        </div>
      </section>

      <nav className="purchase-quick-filters" aria-label="Filtros rápidos de compras">
        <button type="button" aria-pressed={!filters.status && !filters.attachment_status} onClick={() => updateFilters({ status: null, attachment_status: null })}>Todos</button>
        <button type="button" aria-pressed={filters.status === "draft"} onClick={() => updateFilters({ status: "draft", attachment_status: null })}>Borradores</button>
        <button type="button" aria-pressed={filters.status === "received"} onClick={() => updateFilters({ status: "received", attachment_status: null })}>Recibidas</button>
        <button type="button" aria-pressed={filters.attachment_status === "pending"} onClick={() => updateFilters({ status: null, attachment_status: "pending" })}>Pendientes comprobante</button>
      </nav>

      <section className="panel purchase-filter-toolbar" aria-label="Búsqueda y filtros de compras">
        <form className="purchase-search" onSubmit={handleSearch}>
          <label className="field">
            <span>Buscar</span>
            <input
              placeholder="Proveedor o comprobante"
              value={searchValue}
              onChange={(event) => setSearchValue(event.target.value)}
            />
          </label>
          <button className="secondary-button" type="submit"><Search size={17} /> Buscar</button>
        </form>
        <button
          aria-controls="purchase-advanced-filters"
          aria-expanded={isFilterPanelOpen}
          className="secondary-button purchase-filters-toggle"
          type="button"
          onClick={() => setIsFilterPanelOpen((current) => !current)}
        >
          <SlidersHorizontal aria-hidden="true" size={17} />
          Filtros{activeAdvancedFilterCount > 0 ? ` (${activeAdvancedFilterCount})` : ""}
          <ChevronDown aria-hidden="true" size={16} />
        </button>
      </section>

      {isFilterPanelOpen ? (
        <section id="purchase-advanced-filters" className="panel purchase-filters" aria-label="Filtros avanzados de compras">
          <label className="field">
            <span>Proveedor</span>
            <select value={filters.supplier_id ?? ""} onChange={(event) => updateFilters({ supplier_id: event.target.value || null })}>
              <option value="">Todos</option>
              {suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}{supplier.is_active ? "" : " (inactivo)"}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Estado</span>
            <select value={filters.status ?? ""} onChange={(event) => updateFilters({ status: event.target.value || null })}>
              <option value="">Todos</option>
              <option value="draft">Borrador</option>
              <option value="cancelled">Cancelada</option>
              <option value="received">Recibida</option>
              <option value="reversed">Recepción revertida</option>
            </select>
          </label>
          <label className="field">
            <span>Comprobante</span>
            <select value={filters.attachment_status ?? ""} onChange={(event) => updateFilters({ attachment_status: event.target.value || null })}>
              <option value="">Todos</option>
              <option value="attached">Cargado</option>
              <option value="pending">Pendiente</option>
            </select>
          </label>
          <label className="field">
            <span>Tipo de documento</span>
            <select value={filters.document_type ?? ""} onChange={(event) => updateFilters({ document_type: event.target.value || null })}>
              <option value="">Todos</option>
              <option value="invoice">Factura</option>
              <option value="receipt">Recibo</option>
              <option value="ticket">Ticket</option>
              <option value="delivery_note">Remito</option>
              <option value="other">Otro</option>
            </select>
          </label>
          <label className="field">
            <span>Desde</span>
            <input type="date" value={filters.date_from ?? ""} onChange={(event) => updateFilters({ date_from: event.target.value || null })} />
          </label>
          <label className="field">
            <span>Hasta</span>
            <input type="date" value={filters.date_to ?? ""} onChange={(event) => updateFilters({ date_to: event.target.value || null })} />
          </label>
          <label className="field">
            <span>Creador</span>
            <select value={filters.created_by_user_id ?? ""} onChange={(event) => updateFilters({ created_by_user_id: event.target.value || null })}>
              <option value="">Todos</option>
              {creators.map((creator) => <option key={creator.id} value={creator.id}>{creator.full_name}{creator.is_active ? "" : " (inactivo)"}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Ordenar por</span>
            <select value={filters.sort_by ?? "purchase_date"} onChange={(event) => updateFilters({ sort_by: event.target.value })}>
              <option value="purchase_date">Fecha de compra</option>
              <option value="created_at">Fecha de registro</option>
              <option value="total_ars">Total</option>
              <option value="supplier_name">Proveedor</option>
              <option value="status">Estado</option>
            </select>
          </label>
          <label className="field">
            <span>Dirección</span>
            <select value={filters.sort_direction ?? "desc"} onChange={(event) => updateFilters({ sort_direction: event.target.value })}>
              <option value="desc">Descendente</option>
              <option value="asc">Ascendente</option>
            </select>
          </label>
          <label className="field">
            <span>Por página</span>
            <select value={filters.page_size ?? 20} onChange={(event) => updateFilters({ page_size: Number(event.target.value) })}>
              <option value="10">10</option><option value="20">20</option><option value="50">50</option><option value="100">100</option>
            </select>
          </label>
          {hasFilters ? <button className="secondary-button purchase-filters__clear" type="button" onClick={clearFilters}>Limpiar filtros</button> : null}
        </section>
      ) : null}

      {errorMessage ? <section className="error-state">{errorMessage}</section> : null}
      {isLoading ? <div className="loading-card" aria-label="Cargando compras" /> : null}

      {!isLoading && !errorMessage ? (
        <section className="purchase-list-summary" aria-label="Resumen de compras filtradas">
          <div><span>Compras</span><strong>{meta.summary.purchase_count}</strong></div>
          <div><span>Subtotal</span><strong>{formatPurchaseCurrency(meta.summary.subtotal_ars, moneyPreferences)}</strong></div>
          <div><span>IVA</span><strong>{formatPurchaseCurrency(meta.summary.tax_total_ars, moneyPreferences)}</strong></div>
          <div><span>Total</span><strong>{formatPurchaseCurrency(meta.summary.total_ars, moneyPreferences)}</strong></div>
        </section>
      ) : null}

      {!isLoading && !errorMessage && items.length === 0 ? (
        <section className="empty-state purchase-empty-state">
          <ShoppingCart size={30} />
          <h2>{hasFilters ? "No hay compras para estos filtros" : "Todavía no hay compras"}</h2>
          <p>{hasFilters ? "Prueba limpiando o ajustando los filtros." : "Crea el primer borrador para comenzar el historial."}</p>
          {!hasFilters ? <Link className="primary-button" href="/purchases/new">Nueva compra</Link> : null}
        </section>
      ) : null}

      {!isLoading && items.length > 0 ? (
        <>
          <section className="inventory-table-card" aria-label="Listado de compras">
            <div className="inventory-table-scroll">
              <table className="inventory-table purchase-table">
                <thead>
                  <tr>
                    <th>Fecha</th><th>Proveedor</th><th>Comprobante</th><th>Líneas</th>
                    <th>Subtotal</th><th>IVA</th><th>Total</th><th>Estado</th><th>Usuario</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((purchase) => (
                    <tr
                      key={purchase.id}
                      className="inventory-table__row--clickable"
                      role="link"
                      tabIndex={0}
                      aria-label={`Abrir compra de ${purchase.supplier_name}`}
                      onClick={() => router.push(`/purchases/${purchase.id}`)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          router.push(`/purchases/${purchase.id}`);
                        }
                      }}
                    >
                      <td className="purchase-cell--date">{formatPurchaseDate(purchase.purchase_date)}</td>
                      <td className="purchase-cell-text purchase-cell--supplier"><strong className="purchase-clamp-two" title={purchase.supplier_name}>{purchase.supplier_name}</strong><small className="purchase-ellipsis" title={purchase.supplier_tax_id || "Sin identificación fiscal"}>{purchase.supplier_tax_id || "Sin identificación fiscal"}</small></td>
                      <td className="purchase-cell-text purchase-cell--document"><strong>{labelPurchaseDocumentType(purchase.document_type)}</strong><small className="purchase-ellipsis" title={purchase.document_number || "Sin número"}>{purchase.document_number || "Sin número"}</small><span className={`badge purchase-attachment-status purchase-attachment-status--${purchase.attachment_status}`}>{purchase.attachment_status === "attached" ? "Cargado" : "Pendiente"}</span></td>
                      <td className="purchase-cell--number">{purchase.item_count}</td>
                      <td className="purchase-cell--money">{formatPurchaseCurrency(purchase.subtotal_ars, moneyPreferences)}</td>
                      <td className="purchase-cell--money">{formatPurchaseCurrency(purchase.tax_total_ars, moneyPreferences)}</td>
                      <td className="purchase-cell--money"><strong>{formatPurchaseCurrency(purchase.total_ars, moneyPreferences)}</strong></td>
                      <td className="purchase-cell--status"><span className={`badge purchase-status purchase-status--${purchase.status}`}>{labelPurchaseStatus(purchase.status)}</span>{purchase.return_status !== "none" ? <small className={`badge purchase-return-indicator purchase-return-indicator--${purchase.return_status}`}>{purchase.return_status === "full" ? "Devolución total" : "Devolución parcial"}</small> : null}</td>
                      <td className="purchase-cell-text purchase-cell--user"><strong className="purchase-clamp-two" title={purchase.created_by_user_name || purchase.created_by_user_email || "Sin usuario registrado"}>{purchase.created_by_user_name || purchase.created_by_user_email || "Sin usuario registrado"}</strong>{purchase.created_by_user_name && purchase.created_by_user_email ? <small className="purchase-ellipsis" title={purchase.created_by_user_email}>{purchase.created_by_user_email}</small> : null}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <nav className="purchase-pagination" aria-label="Paginación de compras">
            <button className="secondary-button" type="button" disabled={meta.page <= 1} onClick={() => updateFilters({ page: meta.page - 1 })}>Anterior</button>
            <span>Página {meta.page} de {Math.max(meta.total_pages, 1)} · {meta.total} compras</span>
            <button className="secondary-button" type="button" disabled={meta.page >= meta.total_pages} onClick={() => updateFilters({ page: meta.page + 1 })}>Siguiente</button>
          </nav>
        </>
      ) : null}
    </div>
  );
}

function readFilters(queryString: string): PurchaseListFilters {
  const params = new URLSearchParams(queryString);
  const status = params.get("status");
  const documentType = params.get("document_type") as PurchaseDocumentType | null;
  const attachmentStatus = params.get("attachment_status");
  const sortBy = params.get("sort_by");
  const sortDirection = params.get("sort_direction");
  const pageSize = Number(params.get("page_size"));
  return {
    search: params.get("search") || undefined,
    supplier_id: params.get("supplier_id") || undefined,
    status: status === "draft" || status === "cancelled" || status === "received" || status === "reversed" ? status : undefined,
    document_type: ["invoice", "receipt", "ticket", "delivery_note", "other"].includes(documentType ?? "") ? documentType ?? undefined : undefined,
    attachment_status: attachmentStatus === "pending" || attachmentStatus === "attached" ? attachmentStatus : undefined,
    date_from: params.get("date_from") || undefined,
    date_to: params.get("date_to") || undefined,
    created_by_user_id: params.get("created_by_user_id") || undefined,
    page: Math.max(1, Number(params.get("page")) || 1),
    page_size: [10, 20, 50, 100].includes(pageSize) ? pageSize : 20,
    sort_by: ["purchase_date", "created_at", "total_ars", "supplier_name", "status"].includes(sortBy ?? "") ? sortBy as PurchaseListFilters["sort_by"] : "purchase_date",
    sort_direction: sortDirection === "asc" ? "asc" : "desc",
  };
}

function countAdvancedFilters(filters: PurchaseListFilters) {
  return [
    Boolean(filters.supplier_id),
    Boolean(filters.status),
    Boolean(filters.attachment_status),
    Boolean(filters.document_type),
    Boolean(filters.date_from || filters.date_to),
    Boolean(filters.created_by_user_id),
  ].filter(Boolean).length;
}

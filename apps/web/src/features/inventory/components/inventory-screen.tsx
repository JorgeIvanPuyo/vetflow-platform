"use client";

import {
  ChevronLeft,
  ChevronRight,
  Filter,
  Plus,
  Search,
  X,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  buildInventoryListFilters,
  formatInventoryCurrency,
  formatInventoryDateCompact,
  formatInventoryQuantity,
  getInventoryCategoryIcon,
  getInventoryCategoryLabel,
  getInventoryStatusBadges,
  initialInventoryFilterState,
  inventoryCategoryOptions,
  inventoryStatusOptions,
  InventoryFilterState,
} from "@/features/inventory/components/inventory-helpers";
import { getApiErrorMessage } from "@/lib/api";
import { getInventoryItems, getInventorySummary } from "@/services/inventory";
import type { InventoryItem, InventorySummary } from "@/types/api";

type InventoryScreenState = {
  isLoading: boolean;
  isRefreshing: boolean;
  items: InventoryItem[];
  summary: InventorySummary | null;
  errorMessage: string | null;
  meta: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
};

const initialState: InventoryScreenState = {
  isLoading: true,
  isRefreshing: false,
  items: [],
  summary: null,
  errorMessage: null,
  meta: {
    page: 1,
    page_size: 10,
    total: 0,
    total_pages: 0,
  },
};

export function InventoryScreen() {
  const [state, setState] = useState<InventoryScreenState>(initialState);
  const [queryInput, setQueryInput] = useState("");
  const [query, setQuery] = useState("");
  const [filterState, setFilterState] = useState<InventoryFilterState>(
    initialInventoryFilterState,
  );
  const [draftFilterState, setDraftFilterState] = useState<InventoryFilterState>(
    initialInventoryFilterState,
  );
  const [page, setPage] = useState(1);
  const [isFilterOpen, setIsFilterOpen] = useState(false);

  const activeFilters = useMemo(
    () => buildInventoryListFilters(query, filterState, page),
    [filterState, page, query],
  );

  const loadInventory = useCallback(async () => {
    setState((current) => ({
      ...current,
      isLoading: current.summary === null,
      isRefreshing: current.summary !== null,
      errorMessage: null,
    }));

    try {
      const [summaryResponse, itemsResponse] = await Promise.all([
        getInventorySummary(),
        getInventoryItems(activeFilters),
      ]);

      setState({
        isLoading: false,
        isRefreshing: false,
        summary: summaryResponse.data,
        items: itemsResponse.data,
        errorMessage: null,
        meta: itemsResponse.meta,
      });
    } catch (error) {
      setState((current) => ({
        ...current,
        isLoading: false,
        isRefreshing: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }, [activeFilters]);

  useEffect(() => {
    void loadInventory();
  }, [loadInventory]);

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setQuery(queryInput);
  }

  function applyFilters() {
    setFilterState(draftFilterState);
    setPage(1);
    setIsFilterOpen(false);
  }

  function clearFilters() {
    setDraftFilterState(initialInventoryFilterState);
    setFilterState(initialInventoryFilterState);
    setQuery("");
    setQueryInput("");
    setPage(1);
    setIsFilterOpen(false);
  }

  function applyStatusQuickFilter(status: InventoryFilterState["status"]) {
    const nextFilters = {
      ...filterState,
      status,
    };
    setFilterState(nextFilters);
    setDraftFilterState(nextFilters);
    setPage(1);
  }

  return (
    <div className="page-stack inventory-page">
      <section className="screen-heading">
        <div className="screen-heading--with-action inventory-heading-row">
          <div>
            <p className="eyebrow">Clínica</p>
            <h1>Inventario</h1>
            <p>
              {state.summary?.total_items ?? 0} items registrados
            </p>
          </div>
          <Link className="primary-button inventory-create-button" href="/inventory/new" aria-label="Nuevo item">
            <Plus size={18} />
            <span>Nuevo item</span>
          </Link>
        </div>
      </section>

      <section className="inventory-summary-grid" aria-label="Resumen de inventario">
        <button
          type="button"
          className="inventory-summary-card inventory-summary-card--danger"
          onClick={() => applyStatusQuickFilter("low_stock")}
        >
          <span className="inventory-summary-card__label">Bajo stock</span>
          <strong>{state.summary?.low_stock_count ?? 0}</strong>
          <small>Requieren reposición</small>
        </button>
        <button
          type="button"
          className="inventory-summary-card inventory-summary-card--warning"
          onClick={() => applyStatusQuickFilter("expiring_soon")}
        >
          <span className="inventory-summary-card__label">Por vencer</span>
          <strong>{state.summary?.expiring_soon_count ?? 0}</strong>
          <small>Próximos 30 días</small>
        </button>
        <button
          type="button"
          className="inventory-summary-card inventory-summary-card--danger-soft"
          onClick={() => applyStatusQuickFilter("expired")}
        >
          <span className="inventory-summary-card__label">Vencidos</span>
          <strong>{state.summary?.expired_count ?? 0}</strong>
          <small>Necesitan revisión</small>
        </button>
      </section>

      <section className="panel inventory-toolbar">
        <form className="search-form" onSubmit={handleSearch}>
          <label className="search-field">
            <Search size={18} />
            <input
              value={queryInput}
              onChange={(event) => setQueryInput(event.target.value)}
              placeholder="Buscar por nombre o proveedor..."
            />
          </label>
          <button className="search-button" type="submit">
            Buscar
          </button>
        </form>
        <button className="filter-button" type="button" onClick={() => setIsFilterOpen(true)}>
          <Filter size={18} />
          <span>Filtros</span>
        </button>
      </section>

      {state.errorMessage && state.summary === null ? (
        <section className="error-state">
          <strong>No pudimos cargar el inventario.</strong> {state.errorMessage}
          <button className="secondary-button secondary-button--full" type="button" onClick={() => void loadInventory()}>
            Reintentar
          </button>
        </section>
      ) : null}

      {state.isLoading && state.summary === null ? (
        <section className="panel empty-state">
          <strong>Cargando inventario...</strong>
          <span>Estamos trayendo el resumen y los items registrados.</span>
        </section>
      ) : null}

      {state.summary ? (
        <>
          {state.errorMessage ? (
            <section className="error-state">
              <strong>Mostrando la última información disponible.</strong> {state.errorMessage}
            </section>
          ) : null}

          {state.items.length > 0 ? (
            <section className="inventory-card-list">
              {state.items.map((item) => (
                <Link key={item.id} className="inventory-card" href={`/inventory/${item.id}`}>
                  <span className="inventory-card__icon" aria-hidden="true">
                    {getInventoryCategoryIcon(item.category)}
                  </span>
                  <div className="inventory-card__body">
                    <div className="inventory-card__title-row">
                      <h2>{item.name}</h2>
                      <ChevronRight size={18} className="inventory-card__chevron" />
                    </div>
                    <p className="inventory-card__meta">
                      {getInventoryCategoryLabel(item.category)}
                      {item.supplier ? ` · ${item.supplier}` : ""}
                    </p>
                    <div className="inventory-card__stats">
                      <span>Stock: {formatInventoryQuantity(item.current_stock, item.unit)}</span>
                      <span>Mínimo: {formatInventoryQuantity(item.minimum_stock, item.unit)}</span>
                      <span>Venta: {formatInventoryCurrency(item.sale_price_ars)}</span>
                    </div>
                    <div className="timeline-card__badges">
                      {getInventoryStatusBadges(item).map((badge) => (
                        <span key={badge.label} className={badge.className}>
                          {badge.label}
                        </span>
                      ))}
                      {item.expiration_date ? (
                        <span className="badge badge--blue">
                          Vence {formatInventoryDateCompact(item.expiration_date)}
                        </span>
                      ) : null}
                    </div>
                  </div>
                </Link>
              ))}
            </section>
          ) : (
            <section className="empty-state">
              No hay items en inventario.
            </section>
          )}

          <section className="panel inventory-pagination">
            <button
              className="secondary-button"
              type="button"
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              disabled={state.meta.page <= 1 || state.isRefreshing}
            >
              <ChevronLeft size={18} />
              Anterior
            </button>
            <span>
              Página {state.meta.page} de {Math.max(state.meta.total_pages, 1)}
            </span>
            <button
              className="secondary-button"
              type="button"
              onClick={() =>
                setPage((current) =>
                  current >= state.meta.total_pages ? current : current + 1,
                )
              }
              disabled={
                state.meta.total_pages === 0 ||
                state.meta.page >= state.meta.total_pages ||
                state.isRefreshing
              }
            >
              Siguiente
              <ChevronRight size={18} />
            </button>
          </section>
        </>
      ) : null}

      {isFilterOpen ? (
        <div className="modal-backdrop" role="presentation" onClick={() => setIsFilterOpen(false)}>
          <section className="bottom-sheet" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="bottom-sheet__header">
              <div>
                <p className="eyebrow">Filtros</p>
                <h2>Filtrar inventario</h2>
              </div>
              <button className="icon-button" type="button" onClick={() => setIsFilterOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <label className="field">
              <span>Categoría</span>
              <select
                value={draftFilterState.category}
                onChange={(event) =>
                  setDraftFilterState((current) => ({
                    ...current,
                    category: event.target.value as InventoryFilterState["category"],
                  }))
                }
              >
                <option value="all">Todas</option>
                {inventoryCategoryOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>Estado</span>
              <select
                value={draftFilterState.status}
                onChange={(event) =>
                  setDraftFilterState((current) => ({
                    ...current,
                    status: event.target.value as InventoryFilterState["status"],
                  }))
                }
              >
                {inventoryStatusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>Proveedor</span>
              <input
                value={draftFilterState.supplier}
                onChange={(event) =>
                  setDraftFilterState((current) => ({
                    ...current,
                    supplier: event.target.value,
                  }))
                }
                placeholder="Laboratorio o distribuidora"
              />
            </label>

            <div className="modal-actions">
              <button className="secondary-button" type="button" onClick={clearFilters}>
                Limpiar
              </button>
              <button className="primary-button" type="button" onClick={applyFilters}>
                Aplicar filtros
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}

"use client";

import {
  ChevronLeft,
  ChevronRight,
  Download,
  Edit3,
  FileSpreadsheet,
  Filter,
  History,
  LayoutGrid,
  List,
  Plus,
  Search,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  buildInventoryListFilters,
  formatInventoryCurrency,
  formatInventoryDateCompact,
  formatInventoryDateTime,
  formatInventoryQuantity,
  getInventoryCategoryIcon,
  getInventoryCategoryLabel,
  getInventoryStatusBadges,
  initialInventoryFilterState,
  inventoryActiveStatusOptions,
  inventoryCategoryOptions,
  inventorySortDirectionOptions,
  inventorySortOptions,
  inventoryStockStatusOptions,
  InventoryFilterState,
} from "@/features/inventory/components/inventory-helpers";
import { formatUserName } from "@/features/inventory/components/inventory-bulk-operations-screen";
import { getApiErrorMessage } from "@/lib/api";
import {
  exportInventory,
  confirmInventoryBulkOperation,
  getInventoryFilterOptions,
  getInventoryItems,
  getInventorySummary,
  previewInventoryBulkOperation,
} from "@/services/inventory";
import type {
  InventoryBulkOperation,
  InventoryBulkOperationPreviewPayload,
  InventoryBulkOperationType,
  InventoryCategory,
  InventoryExportPayload,
  InventoryFilterOptions,
  InventoryItem,
  InventorySortBy,
  InventorySortOrder,
  InventoryStatusFilter,
  InventoryStockStatus,
  InventorySummary,
} from "@/types/api";

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

type InventoryViewMode = "cards" | "table";
type BulkSelectionMode = "selected" | "filtered";

type InventoryFilterOptionsState = {
  data: InventoryFilterOptions;
  isLoading: boolean;
  errorMessage: string | null;
};

type InventoryQueryState = {
  search: string;
  filterState: InventoryFilterState;
  legacyStatus: InventoryStatusFilter | null;
  page: number;
  pageSize: number;
};

const DEFAULT_PAGE = 1;
const DEFAULT_PAGE_SIZE = 20;
const DEFAULT_SORT_BY: InventorySortBy = "name";
const DEFAULT_SORT_DIRECTION: InventorySortOrder = "asc";
const SEARCH_DEBOUNCE_MS = 400;
const bulkOperationOptions: Array<{ value: InventoryBulkOperationType; label: string }> = [
  { value: "increase_sale_price_percentage", label: "Aumentar precio %" },
  { value: "decrease_sale_price_percentage", label: "Disminuir precio %" },
  { value: "set_profit_margin_percentage", label: "Establecer margen" },
  { value: "set_sale_price", label: "Establecer precio final" },
  { value: "set_brand", label: "Establecer marca" },
  { value: "set_supplier", label: "Establecer proveedor" },
  { value: "set_minimum_stock", label: "Establecer stock mínimo" },
  { value: "activate", label: "Activar" },
  { value: "deactivate", label: "Inactivar" },
];

const inventoryCategoryValues = new Set<InventoryFilterState["category"]>([
  "all",
  ...inventoryCategoryOptions.map((option) => option.value),
]);
const inventoryStockStatusValues = new Set<InventoryFilterState["stock_status"]>(
  inventoryStockStatusOptions.map((option) => option.value),
);
const inventorySortValues = new Set(inventorySortOptions.map((option) => option.value));
const inventorySortDirectionValues = new Set(
  inventorySortDirectionOptions.map((option) => option.value),
);
const legacyStatusValues = new Set<InventoryStatusFilter>([
  "low_stock",
  "expiring_soon",
  "expired",
  "active",
  "inactive",
]);

const initialState: InventoryScreenState = {
  isLoading: true,
  isRefreshing: false,
  items: [],
  summary: null,
  errorMessage: null,
  meta: {
    page: DEFAULT_PAGE,
    page_size: DEFAULT_PAGE_SIZE,
    total: 0,
    total_pages: 0,
  },
};

export function InventoryScreen() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryString = searchParams.toString();
  const latestLoadRef = useRef(0);
  const latestFilterOptionsLoadRef = useRef(0);
  const [state, setState] = useState<InventoryScreenState>(initialState);
  const [filterOptionsState, setFilterOptionsState] = useState<InventoryFilterOptionsState>({
    data: { brands: [], suppliers: [] },
    isLoading: true,
    errorMessage: null,
  });
  const [queryInput, setQueryInput] = useState("");
  const [draftFilterState, setDraftFilterState] = useState<InventoryFilterState>(
    initialInventoryFilterState,
  );
  const [viewMode, setViewMode] = useState<InventoryViewMode>("cards");
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [isExportOpen, setIsExportOpen] = useState(false);
  const [exportMode, setExportMode] = useState<"all" | "filtered">("filtered");
  const [isExporting, setIsExporting] = useState(false);
  const [exportErrorMessage, setExportErrorMessage] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkSelectionMode, setBulkSelectionMode] = useState<BulkSelectionMode>("selected");
  const [excludedIds, setExcludedIds] = useState<Set<string>>(new Set());
  const [isBulkOpen, setIsBulkOpen] = useState(false);
  const [bulkOperationType, setBulkOperationType] =
    useState<InventoryBulkOperationType>("increase_sale_price_percentage");
  const [bulkValue, setBulkValue] = useState("");
  const [bulkConfirmClear, setBulkConfirmClear] = useState(false);
  const [bulkPreview, setBulkPreview] = useState<InventoryBulkOperation | null>(null);
  const [bulkResult, setBulkResult] = useState<InventoryBulkOperation | null>(null);
  const [bulkErrorMessage, setBulkErrorMessage] = useState<string | null>(null);
  const [isBulkPreviewing, setIsBulkPreviewing] = useState(false);
  const [isBulkConfirming, setIsBulkConfirming] = useState(false);

  const queryState = useMemo(() => readInventoryQuery(queryString), [queryString]);
  const { filterState, legacyStatus, page, pageSize } = queryState;
  const filterOptions = filterOptionsState.data;

  const activeFilters = useMemo(() => {
    const filters = buildInventoryListFilters(
      queryState.search,
      filterState,
      page,
      pageSize,
    );
    if (legacyStatus) {
      filters.status = legacyStatus;
    }
    return filters;
  }, [filterState, legacyStatus, page, pageSize, queryState.search]);

  const listReturnHref = useMemo(() => {
    return `${pathname}${queryString ? `?${queryString}` : ""}`;
  }, [pathname, queryString]);
  const selectedCount =
    bulkSelectionMode === "filtered"
      ? Math.max(0, state.meta.total - excludedIds.size)
      : selectedIds.size;
  const isPageSelected =
    state.items.length > 0 &&
    state.items.every((item) =>
      bulkSelectionMode === "filtered" ? !excludedIds.has(item.id) : selectedIds.has(item.id),
    );

  const updateInventoryUrl = useCallback(
    (
      updates: Partial<Record<string, string | number | boolean | null | undefined>>,
      options: { resetPage?: boolean; replace?: boolean } = {},
    ) => {
      const nextParams = new URLSearchParams(queryString);

      Object.entries(updates).forEach(([key, value]) => {
        if (value === undefined || value === null || value === "") {
          nextParams.delete(key);
          return;
        }
        nextParams.set(key, String(value));
      });

      if (options.resetPage !== false) {
        nextParams.set("page", String(DEFAULT_PAGE));
      }

      const nextQuery = nextParams.toString();
      const nextUrl = `${pathname}${nextQuery ? `?${nextQuery}` : ""}`;
      if (nextUrl === listReturnHref) {
        return;
      }

      if (options.replace) {
        router.replace(nextUrl, { scroll: false });
        return;
      }
      router.push(nextUrl, { scroll: false });
    },
    [listReturnHref, pathname, queryString, router],
  );

  const loadInventory = useCallback(async () => {
    const loadId = latestLoadRef.current + 1;
    latestLoadRef.current = loadId;

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

      if (latestLoadRef.current !== loadId) {
        return;
      }

      setState({
        isLoading: false,
        isRefreshing: false,
        summary: summaryResponse.data,
        items: itemsResponse.data,
        errorMessage: null,
        meta: itemsResponse.meta,
      });
    } catch (error) {
      if (latestLoadRef.current !== loadId) {
        return;
      }

      setState((current) => ({
        ...current,
        isLoading: false,
        isRefreshing: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }, [activeFilters]);

  const loadFilterOptions = useCallback(async () => {
    const loadId = latestFilterOptionsLoadRef.current + 1;
    latestFilterOptionsLoadRef.current = loadId;

    setFilterOptionsState((current) => ({
      ...current,
      isLoading: true,
      errorMessage: null,
    }));

    try {
      const response = await getInventoryFilterOptions();
      if (latestFilterOptionsLoadRef.current !== loadId) {
        return;
      }
      setFilterOptionsState({
        data: response.data,
        isLoading: false,
        errorMessage: null,
      });
    } catch (error) {
      if (latestFilterOptionsLoadRef.current !== loadId) {
        return;
      }
      setFilterOptionsState((current) => ({
        ...current,
        isLoading: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }, []);

  useEffect(() => {
    const nextParams = new URLSearchParams(queryString);
    let changed = false;

    if (!nextParams.has("page")) {
      nextParams.set("page", String(DEFAULT_PAGE));
      changed = true;
    }
    if (!nextParams.has("page_size")) {
      nextParams.set("page_size", String(DEFAULT_PAGE_SIZE));
      changed = true;
    }
    if (!nextParams.has("sort_by")) {
      nextParams.set("sort_by", DEFAULT_SORT_BY);
      changed = true;
    }
    if (!nextParams.has("sort_direction")) {
      nextParams.set("sort_direction", DEFAULT_SORT_DIRECTION);
      changed = true;
    }

    if (changed) {
      router.replace(`${pathname}?${nextParams.toString()}`, { scroll: false });
    }
  }, [pathname, queryString, router]);

  useEffect(() => {
    setQueryInput(queryState.search);
  }, [queryState.search]);

  useEffect(() => {
    if (!isFilterOpen) {
      setDraftFilterState(filterState);
    }
  }, [filterState, isFilterOpen]);

  useEffect(() => {
    void loadInventory();
  }, [loadInventory]);

  useEffect(() => {
    void loadFilterOptions();
  }, [loadFilterOptions]);

  useEffect(() => {
    const trimmedQuery = queryInput.trim();
    if (trimmedQuery === queryState.search) {
      return;
    }

    if (!trimmedQuery) {
      updateInventoryUrl({ search: null, status: null }, { resetPage: true });
      return;
    }

    const timeoutId = window.setTimeout(() => {
      updateInventoryUrl(
        { search: trimmedQuery, status: null },
        { resetPage: true },
      );
    }, SEARCH_DEBOUNCE_MS);

    return () => window.clearTimeout(timeoutId);
  }, [queryInput, queryState.search, updateInventoryUrl]);

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    updateInventoryUrl(
      { search: queryInput.trim() || null, status: null },
      { resetPage: true },
    );
  }

  function applyFilters() {
    updateInventoryUrl(
      {
        category: draftFilterState.category === "all" ? null : draftFilterState.category,
        brand: draftFilterState.brand.trim() || null,
        supplier: draftFilterState.supplier.trim() || null,
        stock_status:
          draftFilterState.stock_status === "all" ? null : draftFilterState.stock_status,
        is_active: draftFilterState.active_status === "inactive" ? false : null,
        sort_by: draftFilterState.sort_by,
        sort_direction: draftFilterState.sort_direction,
        status: null,
      },
      { resetPage: true },
    );
    setIsFilterOpen(false);
  }

  function clearFilters() {
    setQueryInput("");
    setDraftFilterState(initialInventoryFilterState);
    updateInventoryUrl(
      {
        search: null,
        category: null,
        brand: null,
        supplier: null,
        stock_status: null,
        is_active: null,
        status: null,
        sort_by: DEFAULT_SORT_BY,
        sort_direction: DEFAULT_SORT_DIRECTION,
        page_size: DEFAULT_PAGE_SIZE,
      },
      { resetPage: true },
    );
    setIsFilterOpen(false);
  }

  function applyStockQuickFilter(stockStatus: InventoryStockStatus) {
    updateInventoryUrl(
      { stock_status: stockStatus, status: null, is_active: null },
      { resetPage: true },
    );
  }

  function applyLegacyStatusQuickFilter(status: InventoryStatusFilter) {
    updateInventoryUrl(
      { status, stock_status: null, is_active: null },
      { resetPage: true },
    );
  }

  function toggleItemSelection(itemId: string) {
    if (bulkSelectionMode === "filtered") {
      setExcludedIds((current) => {
        const next = new Set(current);
        if (next.has(itemId)) {
          next.delete(itemId);
        } else {
          next.add(itemId);
        }
        return next;
      });
      return;
    }
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
  }

  function selectCurrentPage() {
    setBulkSelectionMode("selected");
    setExcludedIds(new Set());
    setSelectedIds(new Set(state.items.map((item) => item.id)));
  }

  function selectAllFiltered() {
    setBulkSelectionMode("filtered");
    setSelectedIds(new Set());
    setExcludedIds(new Set());
  }

  function clearBulkSelection() {
    setBulkSelectionMode("selected");
    setSelectedIds(new Set());
    setExcludedIds(new Set());
    setBulkPreview(null);
    setBulkErrorMessage(null);
  }

  async function handleBulkPreview() {
    const payload = buildBulkOperationPayload(
      bulkSelectionMode,
      selectedIds,
      excludedIds,
      queryState,
      bulkOperationType,
      bulkValue,
      bulkConfirmClear,
    );
    if (typeof payload === "string") {
      setBulkErrorMessage(payload);
      return;
    }
    setIsBulkPreviewing(true);
    setBulkErrorMessage(null);
    try {
      const response = await previewInventoryBulkOperation(payload);
      setBulkPreview(response.data);
      setBulkResult(null);
    } catch (error) {
      setBulkErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsBulkPreviewing(false);
    }
  }

  async function handleBulkConfirm() {
    if (!bulkPreview) {
      return;
    }
    setIsBulkConfirming(true);
    setBulkErrorMessage(null);
    try {
      const response = await confirmInventoryBulkOperation(bulkPreview.id);
      setBulkPreview(response.data);
      setBulkResult(response.data);
      await loadInventory();
      clearBulkSelection();
      setIsBulkOpen(false);
    } catch (error) {
      setBulkErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsBulkConfirming(false);
    }
  }

  async function handleExport() {
    setIsExporting(true);
    setExportErrorMessage(null);
    try {
      const response = await exportInventory(buildInventoryExportPayload(exportMode, queryState));
      const url = URL.createObjectURL(response.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = response.filename ?? "vetflow_inventario.xlsx";
      link.click();
      URL.revokeObjectURL(url);
      setIsExportOpen(false);
    } catch (error) {
      setExportErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsExporting(false);
    }
  }

  const hasFilters = hasInventoryFilters(queryState);
  const emptyMessage = hasFilters
    ? "No se encontraron items con los filtros aplicados."
    : "No hay items en inventario.";

  return (
    <div className="page-stack inventory-page">
      <section className="screen-heading list-page__header">
        <div>
          <h1>Inventario</h1>
          <p>
            {state.isLoading && state.summary === null
              ? "Cargando inventario..."
              : `${state.meta.total} item${state.meta.total === 1 ? "" : "s"} encontrado${state.meta.total === 1 ? "" : "s"}`}
          </p>
        </div>
        <div className="inventory-header-actions">
          <Link className="secondary-button" href="/inventory/bulk-operations">
            <History size={18} />
            Historial grupal
          </Link>
          <button
            className="secondary-button"
            type="button"
            onClick={() => {
              setExportMode(hasFilters ? "filtered" : "all");
              setExportErrorMessage(null);
              setIsExportOpen(true);
            }}
          >
            <Download size={18} />
            Exportar
          </button>
          <Link className="secondary-button" href="/inventory/import">
            <FileSpreadsheet size={18} />
            Importar
          </Link>
          <Link className="secondary-button" href="/inventory/movements">
            <History size={18} />
            Movimientos
          </Link>
        </div>
      </section>

      <Link
        className="floating-add-button list-page__fab"
        href="/inventory/new"
        aria-label="Nuevo item"
      >
        <Plus aria-hidden="true" size={24} />
      </Link>

      <section className="inventory-summary-grid" aria-label="Resumen de inventario">
        <button
          type="button"
          className="inventory-summary-card inventory-summary-card--danger"
          onClick={() => applyStockQuickFilter("low_stock")}
        >
          <span className="inventory-summary-card__label">Bajo stock</span>
          <strong>{state.summary?.low_stock_count ?? 0}</strong>
          <small>Requieren reposición</small>
        </button>
        <button
          type="button"
          className="inventory-summary-card inventory-summary-card--warning"
          onClick={() => applyLegacyStatusQuickFilter("expiring_soon")}
        >
          <span className="inventory-summary-card__label">Por vencer</span>
          <strong>{state.summary?.expiring_soon_count ?? 0}</strong>
          <small>Próximos 30 días</small>
        </button>
        <button
          type="button"
          className="inventory-summary-card inventory-summary-card--danger-soft"
          onClick={() => applyLegacyStatusQuickFilter("expired")}
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
            <span className="sr-only">Buscar inventario</span>
            <input
              value={queryInput}
              onChange={(event) => setQueryInput(event.target.value)}
              placeholder="Buscar por nombre o código..."
            />
          </label>
          <button className="search-button" type="submit">
            Buscar
          </button>
        </form>
        <div className="inventory-toolbar__controls">
          <div className="inventory-view-toggle" aria-label="Vista de inventario">
            <button
              type="button"
              aria-pressed={viewMode === "cards"}
              className={
                viewMode === "cards"
                  ? "inventory-view-toggle__button inventory-view-toggle__button--active"
                  : "inventory-view-toggle__button"
              }
              onClick={() => setViewMode("cards")}
            >
              <LayoutGrid size={16} />
              Tarjetas
            </button>
            <button
              type="button"
              aria-pressed={viewMode === "table"}
              className={
                viewMode === "table"
                  ? "inventory-view-toggle__button inventory-view-toggle__button--active"
                  : "inventory-view-toggle__button"
              }
              onClick={() => setViewMode("table")}
            >
              <List size={16} />
              Tabla
            </button>
          </div>
          <label className="list-page-size-control list-page-size-control--toolbar">
            <span>Mostrar</span>
            <select
              value={pageSize}
              onChange={(event) =>
                updateInventoryUrl(
                  { page_size: Number(event.target.value) },
                  { resetPage: true },
                )
              }
            >
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
          </label>
          <button
            className="filter-button"
            type="button"
            onClick={() => {
              setDraftFilterState(filterState);
              setIsFilterOpen(true);
              if (
                !filterOptionsState.isLoading &&
                filterOptionsState.errorMessage &&
                filterOptions.brands.length === 0 &&
                filterOptions.suppliers.length === 0
              ) {
                void loadFilterOptions();
              }
            }}
          >
            <Filter size={18} />
            <span>Filtros</span>
          </button>
          {hasFilters ? (
            <button className="filter-button filter-button--quiet" type="button" onClick={clearFilters}>
              <X size={18} />
              <span>Limpiar</span>
            </button>
          ) : null}
        </div>
      </section>

      <section className="panel inventory-bulk-selection-bar">
        <div>
          <strong>{selectedCount} seleccionado{selectedCount === 1 ? "" : "s"}</strong>
          <span>
            {bulkSelectionMode === "filtered"
              ? "Todos los productos que cumplen los filtros, con exclusiones locales."
              : "Selección manual de productos visibles."}
          </span>
        </div>
        <div className="inventory-bulk-selection-bar__actions">
          <button className="secondary-button" type="button" onClick={selectCurrentPage}>
            Seleccionar esta página
          </button>
          <button className="secondary-button" type="button" onClick={selectAllFiltered}>
            Seleccionar todos los resultados
          </button>
          <button className="secondary-button" type="button" onClick={clearBulkSelection}>
            Limpiar
          </button>
          <button
            className="primary-button"
            disabled={selectedCount === 0}
            type="button"
            onClick={() => {
              setBulkPreview(null);
              setBulkResult(null);
              setBulkErrorMessage(null);
              setIsBulkOpen(true);
            }}
          >
            <Edit3 size={18} />
            Editar grupo
          </button>
        </div>
      </section>

      {bulkResult ? (
        <section className="panel-note inventory-bulk-result" aria-live="polite">
          Operación confirmada por{" "}
          {formatUserName(bulkResult.created_by_user_name, bulkResult.created_by_user_email)} el{" "}
          {formatInventoryDateTime(bulkResult.confirmed_at)}. {bulkResult.affected_count} productos cambiados.
          <Link href={`/inventory/bulk-operations/${bulkResult.id}`}>Ver detalle</Link>
        </section>
      ) : null}

      {state.errorMessage && state.summary === null ? (
        <section className="error-state">
          <strong>No pudimos cargar el inventario.</strong> {state.errorMessage}
          <button
            className="secondary-button secondary-button--full"
            type="button"
            onClick={() => void loadInventory()}
          >
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

          {state.items.length > 0 && viewMode === "cards" ? (
            <section className="inventory-card-list" aria-busy={state.isRefreshing}>
                  {state.items.map((item) => (
                <article
                  key={item.id}
                  className="inventory-card inventory-card--selectable"
                >
                  <label className="inventory-row-checkbox">
                    <input
                      checked={bulkSelectionMode === "filtered" ? !excludedIds.has(item.id) : selectedIds.has(item.id)}
                      type="checkbox"
                      onChange={() => toggleItemSelection(item.id)}
                    />
                    <span className="sr-only">Seleccionar {item.name}</span>
                  </label>
                  <Link
                    className="inventory-card__link"
                    href={`/inventory/${item.id}?return_to=${encodeURIComponent(listReturnHref)}`}
                  >
                  <span className="inventory-card__icon" aria-hidden="true">
                    {getInventoryCategoryIcon(item.category)}
                  </span>
                  <div className="inventory-card__body">
                    <div className="inventory-card__title-row">
                      <h2>{item.name}</h2>
                      <ChevronRight size={18} className="inventory-card__chevron" />
                    </div>
                    <p className="inventory-card__meta">
                      {item.internal_code} · {getInventoryCategoryLabel(item.category)}
                      {item.brand ? ` · ${item.brand}` : ""}
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
                </article>
              ))}
            </section>
          ) : null}

          {state.items.length > 0 && viewMode === "table" ? (
            <section className="inventory-table-card" aria-label="Tabla de inventario">
              <div className="inventory-table-scroll">
                <table className="inventory-table">
                  <caption className="sr-only">Items de inventario</caption>
                  <thead>
                    <tr>
                      <th>
                        <input
                          aria-label="Seleccionar página"
                          checked={isPageSelected}
                          type="checkbox"
                          onChange={() => {
                            if (isPageSelected) {
                              clearBulkSelection();
                            } else {
                              selectCurrentPage();
                            }
                          }}
                        />
                      </th>
                      <th>Producto</th>
                      <th>Categoría / proveedor</th>
                      <th>Stock</th>
                      <th>Mínimo</th>
                      <th>Venta</th>
                      <th>Estado</th>
                      <th>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {state.items.map((item) => {
                      const statusBadges = getInventoryStatusBadges(item);
                      return (
                        <tr
                          key={item.id}
                          className="inventory-table__row--static"
                        >
                          <td>
                            <input
                              aria-label={`Seleccionar ${item.name}`}
                              checked={bulkSelectionMode === "filtered" ? !excludedIds.has(item.id) : selectedIds.has(item.id)}
                              type="checkbox"
                              onChange={() => toggleItemSelection(item.id)}
                            />
                          </td>
                          <td>
                            <span className="inventory-table__product">
                              <span className="inventory-table__icon" aria-hidden="true">
                                {getInventoryCategoryIcon(item.category)}
                              </span>
                              <span>
                                <strong>{item.name}</strong>
                                <small>{item.internal_code}</small>
                              </span>
                            </span>
                          </td>
                          <td>
                            <span className="inventory-table__secondary">
                              <strong>{getInventoryCategoryLabel(item.category)}</strong>
                              <small>
                                {[item.brand, item.supplier].filter(Boolean).join(" · ") ||
                                  "Sin marca/proveedor"}
                              </small>
                            </span>
                          </td>
                          <td>{formatInventoryQuantity(item.current_stock, item.unit)}</td>
                          <td>{formatInventoryQuantity(item.minimum_stock, item.unit)}</td>
                          <td>{formatInventoryCurrency(item.sale_price_ars)}</td>
                          <td>
                            <span className="inventory-table__badges">
                              {statusBadges.map((badge) => (
                                <span key={badge.label} className={badge.className}>
                                  {badge.label}
                                </span>
                              ))}
                            </span>
                          </td>
                          <td>
                            <Link
                              className="inventory-table__action"
                              href={`/inventory/${item.id}?return_to=${encodeURIComponent(listReturnHref)}`}
                            >
                              Abrir
                              <ChevronRight size={16} aria-hidden="true" />
                            </Link>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}

          {state.items.length === 0 ? (
            <section className="empty-state">{emptyMessage}</section>
          ) : null}

          <section className="panel inventory-pagination">
            <button
              className="secondary-button"
              type="button"
              onClick={() =>
                updateInventoryUrl(
                  { page: Math.max(1, state.meta.page - 1) },
                  { resetPage: false },
                )
              }
              disabled={state.meta.page <= 1 || state.isRefreshing}
            >
              <ChevronLeft size={18} />
              Anterior
            </button>
            <span>
              {state.meta.total > 0
                ? `${(state.meta.page - 1) * state.meta.page_size + 1}-${Math.min(state.meta.page * state.meta.page_size, state.meta.total)} de ${state.meta.total}`
                : "0 items"}
            </span>
            <button
              className="secondary-button"
              type="button"
              onClick={() =>
                updateInventoryUrl(
                  {
                    page:
                      state.meta.page >= state.meta.total_pages
                        ? state.meta.page
                        : state.meta.page + 1,
                  },
                  { resetPage: false },
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
          <section
            className="bottom-sheet"
            role="dialog"
            aria-modal="true"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="bottom-sheet__header">
              <div>
                <p className="eyebrow">Filtros</p>
                <h2>Filtrar inventario</h2>
              </div>
              <button className="icon-button" type="button" onClick={() => setIsFilterOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <div className="inventory-filter-grid">
              {filterOptionsState.isLoading ? (
                <p className="inventory-filter-grid__status">Cargando opciones...</p>
              ) : null}
              {filterOptionsState.errorMessage ? (
                <p className="inventory-filter-grid__status">
                  No se pudieron cargar marca y proveedor.
                </p>
              ) : null}

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
                <span>Marca</span>
                <select
                  value={draftFilterState.brand}
                  onChange={(event) =>
                    setDraftFilterState((current) => ({
                      ...current,
                      brand: event.target.value,
                    }))
                  }
                >
                  <option value="">Todas</option>
                  {includeSelectedOption(filterOptions.brands, draftFilterState.brand).map(
                    (brand) => (
                      <option key={brand} value={brand}>
                        {brand}
                      </option>
                    ),
                  )}
                </select>
              </label>

              <label className="field">
                <span>Proveedor</span>
                <select
                  value={draftFilterState.supplier}
                  onChange={(event) =>
                    setDraftFilterState((current) => ({
                      ...current,
                      supplier: event.target.value,
                    }))
                  }
                >
                  <option value="">Todos</option>
                  {includeSelectedOption(
                    filterOptions.suppliers,
                    draftFilterState.supplier,
                  ).map((supplier) => (
                    <option key={supplier} value={supplier}>
                      {supplier}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Stock</span>
                <select
                  value={draftFilterState.stock_status}
                  onChange={(event) =>
                    setDraftFilterState((current) => ({
                      ...current,
                      stock_status: event.target.value as InventoryFilterState["stock_status"],
                    }))
                  }
                >
                  {inventoryStockStatusOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Actividad</span>
                <select
                  value={draftFilterState.active_status}
                  onChange={(event) =>
                    setDraftFilterState((current) => ({
                      ...current,
                      active_status: event.target.value as InventoryFilterState["active_status"],
                    }))
                  }
                >
                  {inventoryActiveStatusOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Ordenar por</span>
                <select
                  value={draftFilterState.sort_by}
                  onChange={(event) =>
                    setDraftFilterState((current) => ({
                      ...current,
                      sort_by: event.target.value as InventorySortBy,
                    }))
                  }
                >
                  {inventorySortOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Dirección</span>
                <select
                  value={draftFilterState.sort_direction}
                  onChange={(event) =>
                    setDraftFilterState((current) => ({
                      ...current,
                      sort_direction: event.target.value as InventorySortOrder,
                    }))
                  }
                >
                  {inventorySortDirectionOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

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

      {isExportOpen ? (
        <div className="modal-backdrop" role="presentation" onClick={() => setIsExportOpen(false)}>
          <section
            className="bottom-sheet inventory-export-sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby="inventory-export-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="bottom-sheet__header">
              <div>
                <p className="eyebrow">Inventario</p>
                <h2 id="inventory-export-title">Exportar a Excel</h2>
              </div>
              <button className="icon-button" type="button" onClick={() => setIsExportOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <div className="inventory-export-options">
              <button
                type="button"
                className={`choice-card${exportMode === "all" ? " choice-card--selected" : ""}`}
                onClick={() => setExportMode("all")}
              >
                <span className="inventory-import-choice__icon" aria-hidden="true">
                  <Download size={20} />
                </span>
                <strong>Exportar inventario completo</strong>
                <small>Incluye todos los productos activos de la clínica.</small>
              </button>
              <button
                type="button"
                className={`choice-card${exportMode === "filtered" ? " choice-card--selected" : ""}`}
                onClick={() => setExportMode("filtered")}
              >
                <span className="inventory-import-choice__icon" aria-hidden="true">
                  <Filter size={20} />
                </span>
                <strong>Exportar resultados filtrados</strong>
                <small>Incluye todos los resultados, no solo esta página.</small>
              </button>
            </div>

            <div className="panel-note inventory-export-summary">
              {exportMode === "filtered"
                ? describeInventoryExportFilters(queryState)
                : "Se exportarán todos los productos activos, sin depender de la página visible."}
            </div>

            {exportErrorMessage ? (
              <div className="error-state">{exportErrorMessage}</div>
            ) : null}

            <div className="modal-actions">
              <button className="secondary-button" type="button" onClick={() => setIsExportOpen(false)}>
                Cancelar
              </button>
              <button className="primary-button" disabled={isExporting} type="button" onClick={handleExport}>
                {isExporting ? (
                  <span className="vf-spinner vf-spinner--sm vf-spinner--button" />
                ) : (
                  <Download size={18} />
                )}
                Descargar
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {isBulkOpen ? (
        <div className="modal-backdrop" role="presentation" onClick={() => setIsBulkOpen(false)}>
          <section
            className="bottom-sheet inventory-bulk-sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby="inventory-bulk-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="bottom-sheet__header">
              <div>
                <p className="eyebrow">Inventario</p>
                <h2 id="inventory-bulk-title">Edición grupal</h2>
              </div>
              <button className="icon-button" type="button" onClick={() => setIsBulkOpen(false)}>
                <X size={18} />
              </button>
            </div>
            <div className="inventory-filter-grid">
              <label className="field">
                <span>Operación</span>
                <select
                  value={bulkOperationType}
                  onChange={(event) => {
                    setBulkOperationType(event.target.value as InventoryBulkOperationType);
                    setBulkPreview(null);
                  }}
                >
                  {bulkOperationOptions.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </label>
              {requiresBulkValue(bulkOperationType) ? (
                <label className="field">
                  <span>Valor</span>
                  <input
                    value={bulkValue}
                    onChange={(event) => {
                      setBulkValue(event.target.value);
                      setBulkPreview(null);
                    }}
                    placeholder={bulkValuePlaceholder(bulkOperationType)}
                  />
                </label>
              ) : null}
              {bulkOperationType === "set_brand" || bulkOperationType === "set_supplier" ? (
                <label className="inventory-import-row-checkbox">
                  <input
                    checked={bulkConfirmClear}
                    type="checkbox"
                    onChange={(event) => setBulkConfirmClear(event.target.checked)}
                  />
                  <span>Confirmar limpieza si el valor está vacío</span>
                </label>
              ) : null}
            </div>
            <div className="panel-note">
              {bulkSelectionMode === "filtered"
                ? "Se seleccionaron todos los productos que cumplen los filtros actuales."
                : `${selectedIds.size} productos seleccionados manualmente.`}
            </div>
            {bulkErrorMessage ? <div className="error-state">{bulkErrorMessage}</div> : null}
            {bulkPreview ? (
              <section className="inventory-table-card" aria-label="Preview de edición grupal">
                <div className="inventory-table-scroll">
                  <table className="inventory-table">
                    <thead>
                      <tr>
                        <th>Producto</th>
                        <th>Campo</th>
                        <th>Anterior</th>
                        <th>Nuevo</th>
                        <th>Estado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {bulkPreview.items.slice(0, 20).map((row) => (
                        <tr key={row.id} className="inventory-table__row--static">
                          <td>{row.inventory_item_name ?? row.inventory_item_id}</td>
                          <td>{row.field_name}</td>
                          <td>{formatBulkValue(row.old_value_json)}</td>
                          <td>{formatBulkValue(row.new_value_json)}</td>
                          <td>{row.status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="panel-note">
                  Afectados {bulkPreview.affected_count}, sin cambio {bulkPreview.unchanged_count}, inválidos {bulkPreview.invalid_count}.
                </p>
              </section>
            ) : null}
            <div className="modal-actions">
              <button className="secondary-button" type="button" onClick={() => setIsBulkOpen(false)}>
                Cancelar
              </button>
              <button className="secondary-button" disabled={isBulkPreviewing} type="button" onClick={handleBulkPreview}>
                Simular
              </button>
              <button
                className="primary-button"
                disabled={!bulkPreview || bulkPreview.affected_count === 0 || isBulkConfirming}
                type="button"
                onClick={handleBulkConfirm}
              >
                Confirmar
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}

function readInventoryQuery(queryString: string): InventoryQueryState {
  const searchParams = new URLSearchParams(queryString);
  const search = searchParams.get("search")?.trim() || "";
  const category = readAllowedValue(
    searchParams.get("category"),
    inventoryCategoryValues,
    "all",
  );
  const stockStatus = readAllowedValue(
    searchParams.get("stock_status"),
    inventoryStockStatusValues,
    "all",
  );
  const sortBy = readAllowedValue(
    searchParams.get("sort_by"),
    inventorySortValues,
    DEFAULT_SORT_BY,
  );
  const sortDirection = readAllowedValue(
    searchParams.get("sort_direction"),
    inventorySortDirectionValues,
    DEFAULT_SORT_DIRECTION,
  );
  const legacyStatus = readAllowedValue(searchParams.get("status"), legacyStatusValues, null);
  const isInactive = searchParams.get("is_active") === "false";

  return {
    search,
    filterState: {
      category,
      brand: searchParams.get("brand")?.trim() || "",
      supplier: searchParams.get("supplier")?.trim() || "",
      stock_status: stockStatus,
      active_status: isInactive ? "inactive" : "active",
      sort_by: sortBy,
      sort_direction: sortDirection,
    },
    legacyStatus,
    page: readPositiveInt(searchParams.get("page"), DEFAULT_PAGE, 1, Number.MAX_SAFE_INTEGER),
    pageSize: readPositiveInt(searchParams.get("page_size"), DEFAULT_PAGE_SIZE, 1, 100),
  };
}

function readAllowedValue<T extends string>(
  value: string | null,
  allowedValues: Set<T>,
  fallback: T,
): T;
function readAllowedValue<T extends string>(
  value: string | null,
  allowedValues: Set<T>,
  fallback: T | null,
): T | null;
function readAllowedValue<T extends string>(
  value: string | null,
  allowedValues: Set<T>,
  fallback: T | null,
) {
  return value && allowedValues.has(value as T) ? (value as T) : fallback;
}

function readPositiveInt(
  value: string | null,
  fallback: number,
  min: number,
  max: number,
) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
    return fallback;
  }
  return parsed;
}

function includeSelectedOption(options: string[], selected: string) {
  if (!selected || options.includes(selected)) {
    return options;
  }
  return [...options, selected].sort((left, right) =>
    left.localeCompare(right, "es", { sensitivity: "base" }),
  );
}

function hasInventoryFilters(queryState: InventoryQueryState) {
  const { filterState } = queryState;
  return Boolean(
    queryState.search ||
      queryState.legacyStatus ||
      filterState.category !== "all" ||
      filterState.brand ||
      filterState.supplier ||
      filterState.stock_status !== "all" ||
      filterState.active_status !== "active",
  );
}

function buildInventoryExportPayload(
  mode: "all" | "filtered",
  queryState: InventoryQueryState,
): InventoryExportPayload {
  if (mode === "all") {
    return {
      mode: "all",
      filters: { is_active: true },
      selected_ids: [],
    };
  }

  const { page: _page, page_size: _pageSize, status: _status, ...filters } =
    buildInventoryListFilters(
      queryState.search,
      queryState.filterState,
      queryState.page,
      queryState.pageSize,
    );
  return {
    mode: "filtered",
    filters,
    selected_ids: [],
  };
}

function describeInventoryExportFilters(queryState: InventoryQueryState) {
  const filters = buildInventoryListFilters(
    queryState.search,
    queryState.filterState,
    queryState.page,
    queryState.pageSize,
  );
  const parts = [
    filters.search ? `búsqueda "${filters.search}"` : null,
    filters.category ? `categoría ${filters.category}` : null,
    filters.brand ? `marca ${filters.brand}` : null,
    filters.supplier ? `proveedor ${filters.supplier}` : null,
    filters.stock_status ? `stock ${filters.stock_status}` : null,
    filters.is_active === false ? "inactivos" : "activos",
    `orden ${filters.sort_by ?? DEFAULT_SORT_BY} ${filters.sort_direction ?? DEFAULT_SORT_DIRECTION}`,
  ].filter(Boolean);

  return `${parts.join(" · ")}. Se exportan todos los resultados filtrados, no solo la página ${queryState.page}.`;
}

function buildBulkOperationPayload(
  selectionMode: BulkSelectionMode,
  selectedIds: Set<string>,
  excludedIds: Set<string>,
  queryState: InventoryQueryState,
  operationType: InventoryBulkOperationType,
  rawValue: string,
  confirmClear: boolean,
): InventoryBulkOperationPreviewPayload | string {
  const operation: InventoryBulkOperationPreviewPayload["operation"] = {
    operation_type: operationType,
    confirm_clear: confirmClear,
  };

  if (operationType === "increase_sale_price_percentage" || operationType === "decrease_sale_price_percentage") {
    const value = readBulkNumber(rawValue);
    if (value === null || value <= 0) {
      return "Ingresa un porcentaje mayor que cero.";
    }
    operation.percentage = value;
  } else if (operationType === "set_profit_margin_percentage") {
    const value = readBulkNumber(rawValue);
    if (value === null || value < 0) {
      return "Ingresa un margen mayor o igual a cero.";
    }
    operation.profit_margin_percentage = value;
  } else if (operationType === "set_sale_price") {
    const value = readBulkNumber(rawValue);
    if (value === null || value < 0) {
      return "Ingresa un precio mayor o igual a cero.";
    }
    operation.sale_price_ars = value;
  } else if (operationType === "set_minimum_stock") {
    const value = readBulkNumber(rawValue);
    if (value === null || value < 0) {
      return "Ingresa un stock mínimo mayor o igual a cero.";
    }
    operation.minimum_stock = value;
  } else if (operationType === "set_brand") {
    operation.brand = rawValue.trim();
  } else if (operationType === "set_supplier") {
    operation.supplier = rawValue.trim();
  }

  if (selectionMode === "selected") {
    if (selectedIds.size === 0) {
      return "Selecciona al menos un producto.";
    }
    return {
      selection: {
        selection_mode: "selected",
        selected_ids: Array.from(selectedIds),
        excluded_ids: Array.from(excludedIds),
      },
      operation,
    };
  }

  const { page: _page, page_size: _pageSize, status: _status, sort_by: _sortBy, sort_direction: _sortDirection, ...filters } =
    buildInventoryListFilters(
      queryState.search,
      queryState.filterState,
      queryState.page,
      queryState.pageSize,
    );
  return {
    selection: {
      selection_mode: "filtered",
      filters,
      excluded_ids: Array.from(excludedIds),
    },
    operation,
  };
}

function readBulkNumber(value: string) {
  const normalized = value.trim().replace(",", ".");
  if (!normalized) {
    return null;
  }
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function requiresBulkValue(operationType: InventoryBulkOperationType) {
  return !["activate", "deactivate"].includes(operationType);
}

function bulkValuePlaceholder(operationType: InventoryBulkOperationType) {
  if (operationType.includes("percentage")) {
    return "Porcentaje";
  }
  if (operationType === "set_sale_price") {
    return "Precio final";
  }
  if (operationType === "set_minimum_stock") {
    return "Stock mínimo";
  }
  if (operationType === "set_brand") {
    return "Marca";
  }
  if (operationType === "set_supplier") {
    return "Proveedor";
  }
  return "Valor";
}

function formatBulkValue(value: Record<string, unknown> | null) {
  if (!value) {
    return "";
  }
  const innerValue = value.value;
  if (innerValue && typeof innerValue === "object") {
    return Object.entries(innerValue as Record<string, unknown>)
      .map(([key, item]) => `${key}: ${String(item ?? "")}`)
      .join(", ");
  }
  return String(innerValue ?? "");
}

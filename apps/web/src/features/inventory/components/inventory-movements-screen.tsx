"use client";

import {
  ArrowDown,
  ArrowUp,
  ChevronLeft,
  ChevronRight,
  Filter,
  Package,
  Search,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  formatInventoryDateTime,
  formatInventorySignedQuantity,
  getInventoryMovementDirection,
  getInventoryMovementTypeLabel,
} from "@/features/inventory/components/inventory-helpers";
import { getApiErrorMessage } from "@/lib/api";
import { getInventoryMovementList } from "@/services/inventory";
import type {
  InventoryMovement,
  InventoryMovementType,
  InventoryReversalStatus,
  InventorySortOrder,
  InventoryUnit,
} from "@/types/api";

type MovementListState = {
  isLoading: boolean;
  isRefreshing: boolean;
  data: InventoryMovement[];
  errorMessage: string | null;
  meta: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
};

type MovementQueryState = {
  search: string;
  movementType: InventoryMovementType | "all";
  reversalStatus: InventoryReversalStatus;
  dateFrom: string;
  dateTo: string;
  sortDirection: InventorySortOrder;
  page: number;
  pageSize: number;
  operationId: string;
};

const DEFAULT_PAGE = 1;
const DEFAULT_PAGE_SIZE = 20;
const DEFAULT_SORT_DIRECTION: InventorySortOrder = "desc";
const movementTypeOptions: Array<{ value: InventoryMovementType | "all"; label: string }> = [
  { value: "all", label: "Todos" },
  { value: "manual_entry", label: "Entradas manuales" },
  { value: "manual_exit", label: "Salidas manuales" },
  { value: "purchase", label: "Compras" },
  { value: "sale", label: "Ventas" },
  { value: "clinical_consumption", label: "Consumo clínico" },
  { value: "adjustment_in", label: "Ajustes positivos" },
  { value: "adjustment_out", label: "Ajustes negativos" },
  { value: "expiration", label: "Vencimientos" },
  { value: "loss", label: "Pérdidas" },
  { value: "breakage", label: "Roturas" },
  { value: "reversal", label: "Reversas" },
  { value: "entry", label: "Entradas legadas" },
  { value: "exit", label: "Salidas legadas" },
  { value: "adjustment", label: "Ajustes legados" },
];
const reversalStatusOptions: Array<{ value: InventoryReversalStatus; label: string }> = [
  { value: "all", label: "Todos" },
  { value: "active", label: "Activos" },
  { value: "reversed", label: "Revertidos" },
  { value: "reversal", label: "Reversas" },
];
const movementTypeValues = new Set(movementTypeOptions.map((option) => option.value));
const reversalStatusValues = new Set(reversalStatusOptions.map((option) => option.value));
const sortDirectionValues = new Set<InventorySortOrder>(["asc", "desc"]);

const initialState: MovementListState = {
  isLoading: true,
  isRefreshing: false,
  data: [],
  errorMessage: null,
  meta: {
    page: DEFAULT_PAGE,
    page_size: DEFAULT_PAGE_SIZE,
    total: 0,
    total_pages: 0,
  },
};

export function InventoryMovementsScreen() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryString = searchParams.toString();
  const latestLoadRef = useRef(0);
  const [state, setState] = useState<MovementListState>(initialState);
  const [queryInput, setQueryInput] = useState("");
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const queryState = useMemo(() => readMovementQuery(queryString), [queryString]);

  const activeFilters = useMemo(
    () => ({
      page: queryState.page,
      page_size: queryState.pageSize,
      search: queryState.search || undefined,
      movement_type:
        queryState.movementType === "all" ? undefined : queryState.movementType,
      reversal_status: queryState.reversalStatus,
      date_from: queryState.dateFrom || undefined,
      date_to: queryState.dateTo || undefined,
      sort_direction: queryState.sortDirection,
      operation_id: queryState.operationId || undefined,
    }),
    [queryState],
  );

  const updateUrl = useCallback(
    (
      updates: Partial<Record<string, string | number | null | undefined>>,
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
      if (nextUrl === `${pathname}${queryString ? `?${queryString}` : ""}`) {
        return;
      }
      if (options.replace) {
        router.replace(nextUrl, { scroll: false });
        return;
      }
      router.push(nextUrl, { scroll: false });
    },
    [pathname, queryString, router],
  );

  const loadMovements = useCallback(async () => {
    const loadId = latestLoadRef.current + 1;
    latestLoadRef.current = loadId;
    setState((current) => ({
      ...current,
      isLoading: current.data.length === 0,
      isRefreshing: current.data.length > 0,
      errorMessage: null,
    }));

    try {
      const response = await getInventoryMovementList(activeFilters);
      if (latestLoadRef.current !== loadId) {
        return;
      }
      setState({
        isLoading: false,
        isRefreshing: false,
        data: response.data,
        meta: response.meta,
        errorMessage: null,
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
    void loadMovements();
  }, [loadMovements]);

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    updateUrl({ search: queryInput.trim() || null }, { resetPage: true });
  }

  function clearFilters() {
    setQueryInput("");
    updateUrl(
      {
        search: null,
        movement_type: null,
        reversal_status: "all",
        date_from: null,
        date_to: null,
        sort_direction: DEFAULT_SORT_DIRECTION,
        operation_id: null,
        page_size: DEFAULT_PAGE_SIZE,
      },
      { resetPage: true },
    );
    setIsFilterOpen(false);
  }

  const hasFilters = Boolean(
    queryState.search ||
      queryState.movementType !== "all" ||
      queryState.reversalStatus !== "all" ||
      queryState.dateFrom ||
      queryState.dateTo ||
      queryState.operationId,
  );

  return (
    <div className="page-stack inventory-page">
      <section className="screen-heading list-page__header">
        <div>
          <h1>Movimientos</h1>
          <p>
            {state.isLoading
              ? "Cargando movimientos..."
              : `${state.meta.total} movimiento${state.meta.total === 1 ? "" : "s"}`}
          </p>
        </div>
        <Link className="secondary-button" href="/inventory">
          Volver a inventario
        </Link>
      </section>

      <section className="panel inventory-toolbar">
        <form className="search-form" onSubmit={handleSearch}>
          <label className="search-field">
            <Search size={18} />
            <span className="sr-only">Buscar movimientos</span>
            <input
              value={queryInput}
              onChange={(event) => setQueryInput(event.target.value)}
              placeholder="Producto, código, motivo u origen..."
            />
          </label>
          <button className="search-button" type="submit">
            Buscar
          </button>
        </form>
        <div className="inventory-toolbar__controls">
          <label className="list-page-size-control list-page-size-control--toolbar">
            <span>Mostrar</span>
            <select
              value={queryState.pageSize}
              onChange={(event) =>
                updateUrl({ page_size: Number(event.target.value) }, { resetPage: true })
              }
            >
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </label>
          <button className="filter-button" type="button" onClick={() => setIsFilterOpen(true)}>
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

      {queryState.operationId ? (
        <section className="panel inventory-operation-filter">
          <span>Operación de inventario</span>
          <strong>{queryState.operationId}</strong>
          <button className="secondary-button" type="button" onClick={() => updateUrl({ operation_id: null })}>Quitar filtro</button>
        </section>
      ) : null}

      {state.errorMessage ? (
        <section className="error-state">
          <strong>No pudimos cargar los movimientos.</strong> {state.errorMessage}
        </section>
      ) : null}

      {!state.isLoading && !state.errorMessage && state.data.length === 0 ? (
        <section className="empty-state">
          {hasFilters ? "No hay movimientos con esos filtros." : "No hay movimientos registrados."}
        </section>
      ) : null}

      {state.isLoading ? (
        <div className="loading-card" aria-label="Cargando movimientos de inventario" />
      ) : null}

      {!state.isLoading && state.data.length > 0 ? (
        <section className="inventory-table-card" aria-label="Movimientos de inventario">
          <div className="inventory-table-scroll">
            <table className="inventory-table">
              <caption className="sr-only">Movimientos de inventario</caption>
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Movimiento</th>
                  <th>Cantidad</th>
                  <th>Stock</th>
                  <th>Origen</th>
                  <th>Estado</th>
                  <th>Fecha</th>
                </tr>
              </thead>
              <tbody>
                {state.data.map((movement) => (
                  <MovementRow
                    key={movement.id}
                    movement={movement}
                    onOpen={() => router.push(`/inventory/movements/${movement.id}`)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <section className="panel inventory-pagination">
        <button
          className="secondary-button"
          type="button"
          onClick={() =>
            updateUrl({ page: Math.max(1, state.meta.page - 1) }, { resetPage: false })
          }
          disabled={state.meta.page <= 1 || state.isRefreshing}
        >
          <ChevronLeft size={18} />
          Anterior
        </button>
        <span>
          {state.meta.total > 0
            ? `${(state.meta.page - 1) * state.meta.page_size + 1}-${Math.min(state.meta.page * state.meta.page_size, state.meta.total)} de ${state.meta.total}`
            : "0 movimientos"}
        </span>
        <button
          className="secondary-button"
          type="button"
          onClick={() =>
            updateUrl(
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
                <h2>Filtrar movimientos</h2>
              </div>
              <button className="icon-button" type="button" onClick={() => setIsFilterOpen(false)}>
                <X size={18} />
              </button>
            </div>
            <div className="inventory-filter-grid">
              <label className="field">
                <span>Tipo</span>
                <select
                  value={queryState.movementType}
                  onChange={(event) =>
                    updateUrl(
                      {
                        movement_type:
                          event.target.value === "all" ? null : event.target.value,
                      },
                      { resetPage: true, replace: true },
                    )
                  }
                >
                  {movementTypeOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Reversa</span>
                <select
                  value={queryState.reversalStatus}
                  onChange={(event) =>
                    updateUrl(
                      { reversal_status: event.target.value },
                      { resetPage: true, replace: true },
                    )
                  }
                >
                  {reversalStatusOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Desde</span>
                <input
                  type="date"
                  value={queryState.dateFrom}
                  onChange={(event) =>
                    updateUrl({ date_from: event.target.value || null }, { resetPage: true })
                  }
                />
              </label>
              <label className="field">
                <span>Hasta</span>
                <input
                  type="date"
                  value={queryState.dateTo}
                  onChange={(event) =>
                    updateUrl({ date_to: event.target.value || null }, { resetPage: true })
                  }
                />
              </label>
              <label className="field">
                <span>Orden</span>
                <select
                  value={queryState.sortDirection}
                  onChange={(event) =>
                    updateUrl(
                      { sort_direction: event.target.value },
                      { resetPage: true, replace: true },
                    )
                  }
                >
                  <option value="desc">Más recientes</option>
                  <option value="asc">Más antiguos</option>
                </select>
              </label>
            </div>
            <div className="modal-actions">
              <button className="secondary-button" type="button" onClick={clearFilters}>
                Limpiar
              </button>
              <button className="primary-button" type="button" onClick={() => setIsFilterOpen(false)}>
                Aplicar filtros
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}

function MovementRow({ movement, onOpen }: { movement: InventoryMovement; onOpen: () => void }) {
  const direction = getInventoryMovementDirection(movement.movement_type);
  const unit = (movement.unit || "unit") as InventoryUnit;
  const productName = movement.inventory_item_name || "Producto de inventario";
  const code = movement.inventory_item_internal_code || "Sin código";

  return (
    <tr
      aria-label={`Abrir movimiento de ${productName}`}
      className="inventory-table__row--clickable"
      role="link"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      }}
    >
      <td>
        <span className="inventory-table__product">
          <span className="inventory-table__icon" aria-hidden="true">
            {direction > 0 ? <ArrowUp size={16} /> : direction < 0 ? <ArrowDown size={16} /> : <Package size={16} />}
          </span>
          <span>
            <strong>{productName}</strong>
            <small>{code}</small>
          </span>
        </span>
      </td>
      <td>{getInventoryMovementTypeLabel(movement.movement_type)}</td>
      <td>{formatInventorySignedQuantity(movement.quantity, unit, movement.movement_type)}</td>
      <td>
        {movement.stock_before !== null && movement.stock_after !== null
          ? `${movement.stock_before} -> ${movement.stock_after}`
          : "Histórico"}
      </td>
      <td>{[movement.source_type, movement.source_id].filter(Boolean).join(" · ") || "Manual"}</td>
      <td>
        <span className={getReversalStatusBadgeClass(movement.reversal_status)}>
          {getReversalStatusLabel(movement.reversal_status)}
        </span>
      </td>
      <td>{formatInventoryDateTime(movement.created_at)}</td>
    </tr>
  );
}

function readMovementQuery(queryString: string): MovementQueryState {
  const searchParams = new URLSearchParams(queryString);
  return {
    search: searchParams.get("search")?.trim() || "",
    movementType: readAllowedValue(searchParams.get("movement_type"), movementTypeValues, "all"),
    reversalStatus: readAllowedValue(
      searchParams.get("reversal_status"),
      reversalStatusValues,
      "all",
    ),
    dateFrom: readIsoDate(searchParams.get("date_from")),
    dateTo: readIsoDate(searchParams.get("date_to")),
    sortDirection: readAllowedValue(
      searchParams.get("sort_direction"),
      sortDirectionValues,
      DEFAULT_SORT_DIRECTION,
    ),
    page: readPositiveInt(searchParams.get("page"), DEFAULT_PAGE, 1, Number.MAX_SAFE_INTEGER),
    pageSize: readPositiveInt(searchParams.get("page_size"), DEFAULT_PAGE_SIZE, 1, 100),
    operationId: readUuid(searchParams.get("operation_id")),
  };
}

function readAllowedValue<T extends string>(value: string | null, allowedValues: Set<T>, fallback: T) {
  return value && allowedValues.has(value as T) ? (value as T) : fallback;
}

function readPositiveInt(value: string | null, fallback: number, min: number, max: number) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
    return fallback;
  }
  return parsed;
}

function readIsoDate(value: string | null) {
  return value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : "";
}

function readUuid(value: string | null) {
  return value && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value) ? value : "";
}

function getReversalStatusLabel(status: InventoryReversalStatus) {
  if (status === "reversed") {
    return "Revertido";
  }
  if (status === "reversal") {
    return "Reversa";
  }
  if (status === "active") {
    return "Activo";
  }
  return "Todos";
}

function getReversalStatusBadgeClass(status: InventoryReversalStatus) {
  if (status === "reversed") {
    return "badge badge--warning";
  }
  if (status === "reversal") {
    return "badge badge--blue";
  }
  return "badge badge--success";
}

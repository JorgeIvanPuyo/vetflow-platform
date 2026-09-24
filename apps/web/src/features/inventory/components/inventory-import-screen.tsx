"use client";

import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Download,
  ExternalLink,
  FileSpreadsheet,
  ListFilter,
  Upload,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  formatInventoryDateCompact,
  formatInventoryQuantity,
  getInventoryCategoryLabel,
} from "@/features/inventory/components/inventory-helpers";
import { getApiErrorMessage } from "@/lib/api";
import {
  confirmInventoryImport,
  downloadInventoryImportTemplate,
  getInventoryImport,
  getInventoryImports,
  previewInventoryImport,
} from "@/services/inventory";
import type {
  InventoryImport,
  InventoryCategory,
  InventoryImportListItem,
  InventoryImportMode,
  InventoryImportRow,
  InventoryImportRowAction,
  InventoryUnit,
} from "@/types/api";

type ImportStep = "upload" | "preview" | "result";
type ImportFilter =
  | "all"
  | "valid"
  | "warning"
  | "error"
  | "selected"
  | "create"
  | "update"
  | "review_required"
  | "skip";

type RowSelection = {
  selected: boolean;
  action: InventoryImportRowAction;
};

type ScreenState = {
  isLoading: boolean;
  isPreviewing: boolean;
  isConfirming: boolean;
  isDownloading: boolean;
  errorMessage: string | null;
  successMessage: string | null;
  inventoryImport: InventoryImport | null;
  history: InventoryImportListItem[];
};

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024;
const importModeOptions: Array<{ value: InventoryImportMode; label: string; detail: string }> = [
  {
    value: "initial_load",
    label: "Carga inicial",
    detail: "Concilia stock físico y catálogo",
  },
  {
    value: "catalog_update",
    label: "Actualizar catálogo",
    detail: "Ignora stock del archivo",
  },
];

const filterOptions: Array<{ value: ImportFilter; label: string }> = [
  { value: "all", label: "Todas" },
  { value: "selected", label: "Seleccionadas" },
  { value: "valid", label: "Válidas" },
  { value: "warning", label: "Revisión" },
  { value: "error", label: "Errores" },
  { value: "create", label: "Crear" },
  { value: "update", label: "Actualizar" },
  { value: "review_required", label: "Pendientes" },
  { value: "skip", label: "Omitir" },
];

const initialState: ScreenState = {
  isLoading: false,
  isPreviewing: false,
  isConfirming: false,
  isDownloading: false,
  errorMessage: null,
  successMessage: null,
  inventoryImport: null,
  history: [],
};

export function InventoryImportScreen() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryString = searchParams.toString();
  const [state, setState] = useState<ScreenState>(initialState);
  const [mode, setMode] = useState<InventoryImportMode>("initial_load");
  const [file, setFile] = useState<File | null>(null);
  const [rowSelections, setRowSelections] = useState<Record<string, RowSelection>>({});
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [filter, setFilter] = useState<ImportFilter>("all");
  const [reason, setReason] = useState("Carga inicial de inventario");

  const step = useMemo<ImportStep>(() => readStep(queryString), [queryString]);
  const importId = useMemo(() => new URLSearchParams(queryString).get("import_id"), [queryString]);

  const filteredRows = useMemo(() => {
    const rows = state.inventoryImport?.rows ?? [];
    return rows.filter((row) => matchesFilter(row, rowSelections[row.id], filter));
  }, [filter, rowSelections, state.inventoryImport?.rows]);

  const selectedRows = useMemo(
    () =>
      (state.inventoryImport?.rows ?? []).filter((row) => {
        const selection = rowSelections[row.id];
        return selection?.selected && selection.action !== "skip";
      }),
    [rowSelections, state.inventoryImport?.rows],
  );

  const selectedMovementCount = selectedRows.filter((row) => row.expected_movement_type).length;

  const loadImport = useCallback(
    async (nextImportId: string) => {
      setState((current) => ({ ...current, isLoading: true, errorMessage: null }));
      try {
        const response = await getInventoryImport(nextImportId);
        setState((current) => ({
          ...current,
          inventoryImport: response.data,
          isLoading: false,
        }));
        setMode(response.data.mode);
        setRowSelections(buildDefaultSelections(response.data.rows));
        setReason(
          response.data.mode === "initial_load"
            ? "Carga inicial de inventario"
            : "Actualización de catálogo",
        );
      } catch (error) {
        setState((current) => ({
          ...current,
          isLoading: false,
          errorMessage: getApiErrorMessage(error),
        }));
      }
    },
    [],
  );

  useEffect(() => {
    if (!importId) {
      return;
    }
    void loadImport(importId);
  }, [importId, loadImport]);

  useEffect(() => {
    let isMounted = true;
    getInventoryImports(1, 5)
      .then((response) => {
        if (isMounted) {
          setState((current) => ({ ...current, history: response.data }));
        }
      })
      .catch(() => undefined);
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    const nextFilter = new URLSearchParams(queryString).get("filter") as ImportFilter | null;
    if (nextFilter && filterOptions.some((option) => option.value === nextFilter)) {
      setFilter(nextFilter);
    }
  }, [queryString]);

  async function handleDownloadTemplate() {
    setState((current) => ({ ...current, isDownloading: true, errorMessage: null }));
    try {
      const response = await downloadInventoryImportTemplate();
      const url = URL.createObjectURL(response.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = response.filename ?? "vetflow_inventory_template.xlsx";
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setState((current) => ({ ...current, errorMessage: getApiErrorMessage(error) }));
    } finally {
      setState((current) => ({ ...current, isDownloading: false }));
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0] ?? null;
    setFile(selectedFile);
    setState((current) => ({ ...current, errorMessage: validateFile(selectedFile) }));
  }

  async function handlePreview() {
    const fileError = validateFile(file);
    if (!file || fileError) {
      setState((current) => ({ ...current, errorMessage: fileError }));
      return;
    }
    setState((current) => ({ ...current, isPreviewing: true, errorMessage: null, successMessage: null }));
    try {
      const response = await previewInventoryImport(file, mode);
      setState((current) => ({
        ...current,
        inventoryImport: response.data,
        isPreviewing: false,
        successMessage: "Preview generado.",
      }));
      setRowSelections(buildDefaultSelections(response.data.rows));
      setFilter("all");
      replaceQuery(pathname, router, {
        step: "preview",
        import_id: response.data.id,
        filter: "all",
      });
    } catch (error) {
      setState((current) => ({
        ...current,
        isPreviewing: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }

  async function handleConfirm() {
    if (!state.inventoryImport) {
      return;
    }
    setState((current) => ({ ...current, isConfirming: true, errorMessage: null }));
    try {
      const rows = state.inventoryImport.rows.map((row) => ({
        row_id: row.id,
        selected: rowSelections[row.id]?.selected ?? false,
        action: rowSelections[row.id]?.action ?? "skip",
      }));
      const response = await confirmInventoryImport(state.inventoryImport.id, {
        explicit_confirm: true,
        rows,
        reason: reason.trim() || null,
      });
      setState((current) => ({
        ...current,
        inventoryImport: response.data,
        isConfirming: false,
        successMessage: "Importación confirmada.",
      }));
      setIsConfirmOpen(false);
      replaceQuery(pathname, router, {
        step: "result",
        import_id: response.data.id,
        filter,
      });
    } catch (error) {
      setState((current) => ({
        ...current,
        isConfirming: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }

  function updateFilter(nextFilter: ImportFilter) {
    setFilter(nextFilter);
    const params = new URLSearchParams(queryString);
    params.set("filter", nextFilter);
    router.replace(`${pathname}?${params.toString()}`);
  }

  function updateRowSelection(row: InventoryImportRow, nextSelection: Partial<RowSelection>) {
    setRowSelections((current) => {
      const previous = current[row.id] ?? defaultSelection(row);
      const next = { ...previous, ...nextSelection };
      if (!next.selected) {
        next.action = "skip";
      }
      return { ...current, [row.id]: next };
    });
  }

  const currentImport = state.inventoryImport;
  const canConfirm =
    currentImport?.status === "preview" &&
    selectedRows.length > 0 &&
    selectedRows.every((row) => row.status !== "error");

  return (
    <div className="page-stack inventory-page inventory-import-page">
      <section className="screen-heading list-page__header">
        <div>
          <Link className="back-link" href="/inventory">
            <ArrowLeft size={18} />
            Inventario
          </Link>
          <h1>Importar inventario</h1>
          <p>
            {currentImport
              ? `${currentImport.row_count} fila${currentImport.row_count === 1 ? "" : "s"} en ${currentImport.original_filename}`
              : "Plantilla Excel para carga inicial o actualización de catálogo"}
          </p>
        </div>
        <button
          className="secondary-button"
          disabled={state.isDownloading}
          type="button"
          onClick={handleDownloadTemplate}
        >
          <Download size={18} />
          Plantilla
        </button>
      </section>

      {state.errorMessage ? (
        <div className="panel-note inventory-import-message inventory-import-message--error">
          {state.errorMessage}
        </div>
      ) : null}
      {state.successMessage ? (
        <div className="panel-note inventory-import-message inventory-import-message--success">
          {state.successMessage}
        </div>
      ) : null}

      <section className="inventory-import-steps" aria-label="Pasos de importación">
        <StepPill label="Archivo" isActive={step === "upload"} isDone={Boolean(currentImport)} />
        <StepPill label="Preview" isActive={step === "preview"} isDone={currentImport?.status === "confirmed"} />
        <StepPill label="Resultado" isActive={step === "result"} isDone={currentImport?.status === "confirmed"} />
      </section>

      {step === "upload" || !currentImport ? (
        <section className="panel inventory-import-upload">
          <div className="inventory-import-mode-grid">
            {importModeOptions.map((option) => (
              <button
                key={option.value}
                className={`choice-card${mode === option.value ? " choice-card--selected" : ""}`}
                type="button"
                onClick={() => setMode(option.value)}
              >
                <span className="inventory-import-choice__icon" aria-hidden="true">
                  <FileSpreadsheet size={20} />
                </span>
                <strong>{option.label}</strong>
                <small>{option.detail}</small>
              </button>
            ))}
          </div>
          <label className="inventory-import-file-field">
            <Upload size={20} />
            <span>{file ? file.name : "Seleccionar archivo .xlsx"}</span>
            <input accept=".xlsx" type="file" onChange={handleFileChange} />
          </label>
          <div className="button-row">
            <button
              className="primary-button"
              disabled={state.isPreviewing || Boolean(validateFile(file))}
              type="button"
              onClick={handlePreview}
            >
              {state.isPreviewing ? (
                <span className="vf-spinner vf-spinner--sm vf-spinner--button" />
              ) : (
                <ListFilter size={18} />
              )}
              Generar preview
            </button>
          </div>
        </section>
      ) : null}

      {currentImport ? (
        <>
          <ImportSummary inventoryImport={currentImport} selectedRows={selectedRows.length} />

          <section className="panel inventory-toolbar inventory-import-toolbar">
            <div className="inventory-view-toggle" aria-label="Filtrar filas importadas">
              {filterOptions.map((option) => (
                <button
                  key={option.value}
                  className={
                    filter === option.value
                      ? "inventory-view-toggle__button inventory-view-toggle__button--active"
                      : "inventory-view-toggle__button"
                  }
                  type="button"
                  onClick={() => updateFilter(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <div className="inventory-import-toolbar__actions">
              {currentImport.status === "preview" ? (
                <button
                  className="primary-button"
                  disabled={!canConfirm}
                  type="button"
                  onClick={() => setIsConfirmOpen(true)}
                >
                  <CheckCircle2 size={18} />
                  Confirmar
                </button>
              ) : null}
              {currentImport.operation_id ? (
                <Link
                  className="secondary-button"
                  href={`/inventory/movements?operation_id=${currentImport.operation_id}`}
                >
                  <ExternalLink size={18} />
                  Movimientos
                </Link>
              ) : null}
            </div>
          </section>

          <section className="inventory-table-card" aria-label="Preview de importación">
            <div className="inventory-table-scroll">
              <table className="inventory-table inventory-import-table">
                <thead>
                  <tr>
                    <th>Fila</th>
                    <th>Producto</th>
                    <th>Acción</th>
                    <th>Stock</th>
                    <th>Estado</th>
                    <th>Mensajes</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRows.map((row) => (
                    <ImportRowLine
                      key={row.id}
                      row={row}
                      selection={rowSelections[row.id] ?? defaultSelection(row)}
                      readonly={currentImport.status !== "preview"}
                      onChange={updateRowSelection}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : null}

      {currentImport && filteredRows.length === 0 ? (
        <section className="panel empty-state">No hay filas para este filtro.</section>
      ) : null}

      {state.history.length > 0 ? (
        <section className="panel inventory-import-history">
          <h2>Importaciones recientes</h2>
          <div className="inventory-import-history__list">
            {state.history.map((entry) => (
              <button
                key={entry.id}
                className="inventory-import-history__item"
                type="button"
                onClick={() =>
                  replaceQuery(pathname, router, {
                    step: entry.status === "confirmed" ? "result" : "preview",
                    import_id: entry.id,
                    filter: "all",
                  })
                }
              >
                <span>{entry.original_filename}</span>
                <small>
                  {labelMode(entry.mode)} · {labelImportStatus(entry.status)} ·{" "}
                  {formatInventoryDateCompact(entry.created_at)}
                </small>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {isConfirmOpen && currentImport ? (
        <section aria-labelledby="confirm-import-title" aria-modal="true" className="bottom-sheet" role="dialog">
          <div className="bottom-sheet__header">
            <div>
              <p className="eyebrow">Inventario</p>
              <h2 id="confirm-import-title">Confirmar importación</h2>
            </div>
            <button className="icon-button" type="button" onClick={() => setIsConfirmOpen(false)}>
              <XCircle size={20} />
            </button>
          </div>
          <div className="inventory-import-confirm-body">
            <dl className="metric-list inventory-metric-list">
              <div>
                <dt>Filas seleccionadas</dt>
                <dd>{selectedRows.length}</dd>
              </div>
              <div>
                <dt>Movimientos</dt>
                <dd>{selectedMovementCount}</dd>
              </div>
              <div>
                <dt>Archivo</dt>
                <dd>{currentImport.original_filename}</dd>
              </div>
            </dl>
            <label className="form-field">
              <span>Motivo</span>
              <input value={reason} maxLength={120} onChange={(event) => setReason(event.target.value)} />
            </label>
          </div>
          <div className="button-row">
            <button className="secondary-button" type="button" onClick={() => setIsConfirmOpen(false)}>
              Cancelar
            </button>
            <button
              className="primary-button"
              disabled={state.isConfirming || !canConfirm}
              type="button"
              onClick={handleConfirm}
            >
              {state.isConfirming ? (
                <span className="vf-spinner vf-spinner--sm vf-spinner--button" />
              ) : (
                <CheckCircle2 size={18} />
              )}
              Confirmar
            </button>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function ImportSummary({
  inventoryImport,
  selectedRows,
}: {
  inventoryImport: InventoryImport;
  selectedRows: number;
}) {
  const summary = inventoryImport.summary;
  const warnings = summary?.warnings ?? [];
  return (
    <section className="inventory-summary-grid inventory-import-summary" aria-label="Resumen de importación">
      <article className="inventory-summary-card">
        <span className="inventory-summary-card__label">Válidas</span>
        <strong>{inventoryImport.valid_count}</strong>
        <small>{selectedRows} seleccionadas</small>
      </article>
      <article className="inventory-summary-card inventory-summary-card--warning">
        <span className="inventory-summary-card__label">Revisión</span>
        <strong>{inventoryImport.warning_count}</strong>
        <small>{summary?.movement_count ?? 0} movimientos previstos</small>
      </article>
      <article className="inventory-summary-card inventory-summary-card--danger">
        <span className="inventory-summary-card__label">Errores</span>
        <strong>{inventoryImport.error_count}</strong>
        <small>{labelImportStatus(inventoryImport.status)}</small>
      </article>
      {warnings.length > 0 ? (
        <article className="inventory-summary-card inventory-summary-card--danger-soft">
          <span className="inventory-summary-card__label">Advertencias</span>
          <strong>{warnings.length}</strong>
          <small>{warnings[0]}</small>
        </article>
      ) : null}
    </section>
  );
}

function ImportRowLine({
  row,
  selection,
  readonly,
  onChange,
}: {
  row: InventoryImportRow;
  selection: RowSelection;
  readonly: boolean;
  onChange: (row: InventoryImportRow, selection: Partial<RowSelection>) => void;
}) {
  const data = row.normalized_data;
  const messages = [...row.errors, ...row.warnings];
  const actions = getAllowedActions(row);
  return (
    <tr className="inventory-table__row--static">
      <td>#{row.row_number}</td>
      <td>
        <span className="inventory-table__product">
          <span className="inventory-table__icon" aria-hidden="true">
            <FileSpreadsheet size={18} />
          </span>
          <span>
            <strong>{String(data.name ?? "Sin nombre")}</strong>
            <small>
              {String(data.internal_code ?? "Código nuevo")} ·{" "}
              {getInventoryCategoryLabel(readInventoryCategory(data.category))}
            </small>
          </span>
        </span>
      </td>
      <td>
        <div className="inventory-import-row-actions">
          <label className="inventory-import-row-checkbox">
            <input
              checked={selection.selected}
              disabled={readonly || row.status === "error"}
              type="checkbox"
              onChange={(event) =>
                onChange(row, {
                  selected: event.target.checked,
                  action: event.target.checked ? defaultSelection(row).action : "skip",
                })
              }
            />
            <span>{selection.selected ? "Incluida" : "Omitida"}</span>
          </label>
          <select
            disabled={readonly || !selection.selected || row.status === "error"}
            value={selection.action}
            onChange={(event) =>
              onChange(row, {
                selected: event.target.value !== "skip",
                action: event.target.value as InventoryImportRowAction,
              })
            }
          >
            {actions.map((action) => (
              <option key={action} value={action}>
                {labelRowAction(action)}
              </option>
            ))}
          </select>
        </div>
      </td>
      <td>
        <span className="inventory-table__secondary">
          {row.stock_target !== null
            ? formatInventoryQuantity(row.stock_target, readInventoryUnit(data.unit))
            : "Sin cambio"}
          <small>{row.expected_movement_type ? labelMovement(row.expected_movement_type) : "Sin movimiento"}</small>
        </span>
      </td>
      <td>
        <span className={`inventory-import-status inventory-import-status--${row.status}`}>
          {row.status === "valid" ? <CheckCircle2 size={16} /> : null}
          {row.status === "warning" ? <AlertTriangle size={16} /> : null}
          {row.status === "error" ? <XCircle size={16} /> : null}
          {labelRowStatus(row.status)}
        </span>
      </td>
      <td>
        <span className="inventory-table__secondary">
          {row.match_type}
          <small>{messages.length ? messages.join(", ") : row.changed_fields.join(", ") || "Sin observaciones"}</small>
        </span>
      </td>
    </tr>
  );
}

function StepPill({ label, isActive, isDone }: { label: string; isActive: boolean; isDone: boolean }) {
  return (
    <span className={`inventory-import-step${isActive ? " inventory-import-step--active" : ""}`}>
      {isDone ? <CheckCircle2 size={16} /> : null}
      {label}
    </span>
  );
}

function readStep(queryString: string): ImportStep {
  const value = new URLSearchParams(queryString).get("step");
  if (value === "preview" || value === "result") {
    return value;
  }
  return "upload";
}

function validateFile(file: File | null): string | null {
  if (!file) {
    return "Selecciona un archivo .xlsx.";
  }
  if (!file.name.toLowerCase().endsWith(".xlsx")) {
    return "El archivo debe tener extensión .xlsx.";
  }
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return "El archivo supera el límite de 5 MB.";
  }
  return null;
}

function buildDefaultSelections(rows: InventoryImportRow[]) {
  return Object.fromEntries(rows.map((row) => [row.id, defaultSelection(row)]));
}

function defaultSelection(row: InventoryImportRow): RowSelection {
  if (row.status === "valid" && (row.proposed_action === "create" || row.proposed_action === "update")) {
    return { selected: true, action: row.proposed_action };
  }
  return { selected: false, action: "skip" };
}

function matchesFilter(row: InventoryImportRow, selection: RowSelection | undefined, filter: ImportFilter) {
  if (filter === "all") {
    return true;
  }
  if (filter === "selected") {
    return Boolean(selection?.selected);
  }
  if (filter === "create" || filter === "update" || filter === "review_required" || filter === "skip") {
    return (selection?.action ?? row.proposed_action) === filter || row.proposed_action === filter;
  }
  return row.status === filter;
}

function getAllowedActions(row: InventoryImportRow): InventoryImportRowAction[] {
  if (row.proposed_action === "create") {
    return ["create", "skip"];
  }
  if (row.proposed_action === "update") {
    return ["update", "skip"];
  }
  return ["skip"];
}

function replaceQuery(
  pathname: string,
  router: { replace: (href: string) => void },
  values: Record<string, string>,
) {
  const params = new URLSearchParams(values);
  router.replace(`${pathname}?${params.toString()}`);
}

function readInventoryCategory(value: unknown): InventoryCategory {
  const category = String(value ?? "");
  if (
    category === "medication" ||
    category === "vaccine" ||
    category === "supply" ||
    category === "food" ||
    category === "accessory" ||
    category === "other"
  ) {
    return category;
  }
  return "other";
}

function readInventoryUnit(value: unknown): InventoryUnit {
  const unit = String(value ?? "");
  if (
    unit === "unit" ||
    unit === "tablet" ||
    unit === "capsule" ||
    unit === "ampoule" ||
    unit === "dose" ||
    unit === "pipette" ||
    unit === "bottle" ||
    unit === "vial" ||
    unit === "syringe" ||
    unit === "ml" ||
    unit === "liter" ||
    unit === "gram" ||
    unit === "kg" ||
    unit === "pair" ||
    unit === "box" ||
    unit === "package" ||
    unit === "other"
  ) {
    return unit;
  }
  return "unit";
}

function labelMode(mode: InventoryImportMode) {
  return mode === "initial_load" ? "Carga inicial" : "Catálogo";
}

function labelImportStatus(status: string) {
  const labels: Record<string, string> = {
    preview: "Preview",
    confirmed: "Confirmada",
    failed: "Fallida",
    expired: "Expirada",
  };
  return labels[status] ?? status;
}

function labelRowStatus(status: string) {
  const labels: Record<string, string> = {
    valid: "Válida",
    warning: "Revisión",
    error: "Error",
    skipped: "Omitida",
  };
  return labels[status] ?? status;
}

function labelRowAction(action: InventoryImportRowAction) {
  const labels: Record<InventoryImportRowAction, string> = {
    create: "Crear",
    update: "Actualizar",
    skip: "Omitir",
    review_required: "Revisar",
  };
  return labels[action];
}

function labelMovement(movementType: string) {
  const labels: Record<string, string> = {
    initial_stock: "Stock inicial",
    adjustment_in: "Ajuste entrada",
    adjustment_out: "Ajuste salida",
  };
  return labels[movementType] ?? movementType;
}

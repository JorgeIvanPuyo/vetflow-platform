"use client";

import {
  ArrowDown,
  ArrowUp,
  Edit,
  Package,
  Save,
  Trash2,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { InventoryItemForm } from "@/features/inventory/components/inventory-item-form";
import {
  calculateInventoryEntryUnitCostPreview,
  formatInventoryCurrency,
  formatInventoryDate,
  formatInventoryDateTime,
  formatInventoryQuantity,
  formatInventorySignedQuantity,
  getInventoryCategoryLabel,
  getInventoryExitReasonLabel,
  getInventoryMovementAmountLabel,
  getInventoryMovementTypeLabel,
  getInventoryStatusBadges,
  getInventoryUnitLabel,
  initialInventoryEntryFormState,
  initialInventoryExitFormState,
  initialInventoryFormState,
  inventoryEntryFormToPayload,
  inventoryExitFormToPayload,
  inventoryItemToFormState,
  inventoryMovementFilterOptions,
  inventoryExitReasonOptions,
  isInventorySalePriceManual,
  validateInventoryEntryForm,
  validateInventoryExitForm,
  validateInventoryForm,
  inventoryFormToUpdatePayload,
  InventoryEntryFormState,
  InventoryExitFormState,
  InventoryFormState,
} from "@/features/inventory/components/inventory-helpers";
import { ApiClientError, getApiErrorMessage } from "@/lib/api";
import {
  createInventoryEntry,
  createInventoryExit,
  deleteInventoryItem,
  getInventoryItem,
  getInventoryMovements,
  updateInventoryItem,
} from "@/services/inventory";
import type { InventoryItem, InventoryMovementType } from "@/types/api";

type MovementFilter = Extract<InventoryMovementType, "entry" | "exit"> | "all";

type InventoryDetailProps = {
  itemId: string;
};

type InventoryDetailState = {
  isLoading: boolean;
  isSaving: boolean;
  isDeleting: boolean;
  isEntrySaving: boolean;
  isExitSaving: boolean;
  item: InventoryItem | null;
  errorMessage: string | null;
  successMessage: string | null;
  flowMessage: string | null;
  deleteMessage: string | null;
  entryMessage: string | null;
  exitMessage: string | null;
};

type MovementState = {
  isLoading: boolean;
  errorMessage: string | null;
  data: Awaited<ReturnType<typeof getInventoryMovements>>["data"];
  page: number;
  totalPages: number;
};

const initialState: InventoryDetailState = {
  isLoading: true,
  isSaving: false,
  isDeleting: false,
  isEntrySaving: false,
  isExitSaving: false,
  item: null,
  errorMessage: null,
  successMessage: null,
  flowMessage: null,
  deleteMessage: null,
  entryMessage: null,
  exitMessage: null,
};

const initialMovementState: MovementState = {
  isLoading: true,
  errorMessage: null,
  data: [],
  page: 1,
  totalPages: 1,
};

export function InventoryDetail({ itemId }: InventoryDetailProps) {
  const router = useRouter();
  const [state, setState] = useState<InventoryDetailState>(initialState);
  const [movementState, setMovementState] = useState<MovementState>(initialMovementState);
  const [movementFilter, setMovementFilter] = useState<MovementFilter>("all");
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isEntryOpen, setIsEntryOpen] = useState(false);
  const [isExitOpen, setIsExitOpen] = useState(false);
  const [formState, setFormState] = useState<InventoryFormState>(initialInventoryFormState);
  const [manualSalePriceOverride, setManualSalePriceOverride] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [entryFormState, setEntryFormState] = useState<InventoryEntryFormState>(
    initialInventoryEntryFormState,
  );
  const [exitFormState, setExitFormState] = useState<InventoryExitFormState>(
    initialInventoryExitFormState,
  );

  const loadItem = useCallback(async () => {
    try {
      const response = await getInventoryItem(itemId);
      setState((current) => ({
        ...current,
        item: response.data,
        errorMessage: null,
      }));
      return response.data;
    } catch (error) {
      setState((current) => ({
        ...current,
        errorMessage: getApiErrorMessage(error),
      }));
      throw error;
    }
  }, [itemId]);

  const loadMovements = useCallback(
    async (page: number, filter: MovementFilter) => {
      setMovementState((current) => ({
        ...current,
        isLoading: true,
        errorMessage: null,
      }));

      try {
        const response = await getInventoryMovements(itemId, {
          page,
          page_size: 10,
          movement_type: filter === "all" ? undefined : filter,
        });

        setMovementState({
          isLoading: false,
          errorMessage: null,
          data: response.data,
          page: response.meta.page,
          totalPages: response.meta.total_pages,
        });
      } catch (error) {
        setMovementState((current) => ({
          ...current,
          isLoading: false,
          errorMessage: getApiErrorMessage(error),
        }));
      }
    },
    [itemId],
  );

  const refreshDetail = useCallback(
    async (page: number, filter: MovementFilter) => {
      setState((current) => ({
        ...current,
        isLoading: true,
        errorMessage: null,
      }));

      try {
        await Promise.all([loadItem(), loadMovements(page, filter)]);
        setState((current) => ({
          ...current,
          isLoading: false,
        }));
      } catch {
        setState((current) => ({
          ...current,
          isLoading: false,
        }));
      }
    },
    [loadItem, loadMovements],
  );

  useEffect(() => {
    void refreshDetail(1, "all");
  }, [refreshDetail]);

  function openEdit() {
    if (!state.item) {
      return;
    }

    setFormState(inventoryItemToFormState(state.item));
    setManualSalePriceOverride(isInventorySalePriceManual(state.item));
    setIsEditOpen(true);
    setState((current) => ({
      ...current,
      flowMessage: null,
      successMessage: null,
    }));
  }

  function closeEdit() {
    setIsEditOpen(false);
    setFormState(initialInventoryFormState);
    setManualSalePriceOverride(false);
    setState((current) => ({
      ...current,
      flowMessage: null,
      isSaving: false,
    }));
  }

  function openEntry() {
    if (!state.item) {
      return;
    }

    setEntryFormState({
      ...initialInventoryEntryFormState,
      supplier: state.item.supplier ?? "",
    });
    setIsEntryOpen(true);
    setState((current) => ({
      ...current,
      entryMessage: null,
      successMessage: null,
    }));
  }

  function closeEntry() {
    setIsEntryOpen(false);
    setEntryFormState(initialInventoryEntryFormState);
    setState((current) => ({
      ...current,
      entryMessage: null,
      isEntrySaving: false,
    }));
  }

  function openExit() {
    if (!state.item) {
      return;
    }

    setExitFormState({
      ...initialInventoryExitFormState,
      unit_sale_price_ars: state.item.sale_price_ars ?? "",
    });
    setIsExitOpen(true);
    setState((current) => ({
      ...current,
      exitMessage: null,
      successMessage: null,
    }));
  }

  function closeExit() {
    setIsExitOpen(false);
    setExitFormState(initialInventoryExitFormState);
    setState((current) => ({
      ...current,
      exitMessage: null,
      isExitSaving: false,
    }));
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const validationMessage = validateInventoryForm(formState, { isEdit: true });
    if (validationMessage) {
      setState((current) => ({ ...current, flowMessage: validationMessage }));
      return;
    }

    setState((current) => ({
      ...current,
      isSaving: true,
      flowMessage: null,
      successMessage: null,
    }));

    try {
      const response = await updateInventoryItem(
        itemId,
        inventoryFormToUpdatePayload(formState, manualSalePriceOverride),
      );
      setState((current) => ({
        ...current,
        isSaving: false,
        item: response.data,
        successMessage: "Item actualizado correctamente.",
      }));
      setIsEditOpen(false);
    } catch (error) {
      setState((current) => ({
        ...current,
        isSaving: false,
        flowMessage: getApiErrorMessage(error),
      }));
    }
  }

  async function handleEntrySubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const validationMessage = validateInventoryEntryForm(entryFormState);
    if (validationMessage) {
      setState((current) => ({ ...current, entryMessage: validationMessage }));
      return;
    }

    setState((current) => ({
      ...current,
      isEntrySaving: true,
      entryMessage: null,
      successMessage: null,
    }));

    try {
      await createInventoryEntry(itemId, inventoryEntryFormToPayload(entryFormState));
      await refreshDetail(1, movementFilter);
      closeEntry();
      setState((current) => ({
        ...current,
        successMessage: "Entrada registrada correctamente.",
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        isEntrySaving: false,
        entryMessage: getApiErrorMessage(error),
      }));
    }
  }

  async function handleExitSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!state.item) {
      return;
    }

    const validationMessage = validateInventoryExitForm(exitFormState, state.item.current_stock);
    if (validationMessage) {
      setState((current) => ({ ...current, exitMessage: validationMessage }));
      return;
    }

    setState((current) => ({
      ...current,
      isExitSaving: true,
      exitMessage: null,
      successMessage: null,
    }));

    try {
      await createInventoryExit(itemId, inventoryExitFormToPayload(exitFormState));
      await refreshDetail(1, movementFilter);
      closeExit();
      setState((current) => ({
        ...current,
        successMessage: "Salida registrada correctamente.",
      }));
    } catch (error) {
      let message = getApiErrorMessage(error);

      if (error instanceof ApiClientError && error.code === "insufficient_stock") {
        message = "No hay stock suficiente para registrar esta salida.";
      }

      setState((current) => ({
        ...current,
        isExitSaving: false,
        exitMessage: message,
      }));
    }
  }

  async function handleDelete(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (deleteConfirmation !== "ELIMINAR") {
      return;
    }

    setState((current) => ({
      ...current,
      isDeleting: true,
      deleteMessage: null,
    }));

    try {
      await deleteInventoryItem(itemId);
      router.push("/inventory");
    } catch (error) {
      setState((current) => ({
        ...current,
        isDeleting: false,
        deleteMessage: getApiErrorMessage(error),
      }));
    }
  }

  const entryUnitCostPreview = useMemo(
    () => calculateInventoryEntryUnitCostPreview(entryFormState),
    [entryFormState],
  );

  if (state.isLoading && !state.item) {
    return <div className="loading-card" aria-label="Cargando item de inventario" />;
  }

  if (state.errorMessage && !state.item) {
    return <div className="error-state">{state.errorMessage}</div>;
  }

  if (!state.item) {
    return <div className="empty-state">Item no encontrado.</div>;
  }

  const item = state.item;
  const badges = getInventoryStatusBadges(item);

  return (
    <div className="page-stack inventory-detail-page">
      <section className="detail-hero">
        <Link className="back-link" href="/inventory">
          Volver a inventario
        </Link>
        <div className="detail-hero__main">
          <span className="inventory-form-hero__icon" aria-hidden="true">
            <Package size={28} />
          </span>
          <div>
            <h1>{item.name}</h1>
            <p>
              {getInventoryCategoryLabel(item.category)}
              {item.subcategory ? ` · ${item.subcategory}` : ""}
            </p>
          </div>
        </div>
        <div className="detail-hero__actions">
          <button className="primary-button" type="button" onClick={openEdit}>
            <Edit size={18} />
            Editar
          </button>
          <button
            className="secondary-button secondary-button--danger"
            type="button"
            onClick={() => setIsDeleteOpen(true)}
          >
            <Trash2 size={18} />
            Desactivar
          </button>
        </div>
      </section>

      {state.successMessage ? <div className="success-state">{state.successMessage}</div> : null}

      <section className="summary-grid">
        <article className="panel">
          <div className="section-heading">
            <p className="eyebrow">Resumen</p>
            <h2>Estado actual</h2>
          </div>
          <dl className="metric-list inventory-metric-list">
            <div>
              <dt>Stock actual</dt>
              <dd>{formatInventoryQuantity(item.current_stock, item.unit)}</dd>
            </div>
            <div>
              <dt>Stock mínimo</dt>
              <dd>{formatInventoryQuantity(item.minimum_stock, item.unit)}</dd>
            </div>
            <div>
              <dt>Precio compra</dt>
              <dd>{formatInventoryCurrency(item.purchase_price_ars)}</dd>
            </div>
            <div>
              <dt>Precio venta</dt>
              <dd>{formatInventoryCurrency(item.sale_price_ars)}</dd>
            </div>
          </dl>

          <div className="timeline-card__badges">
            {badges.map((badge) => (
              <span key={`${badge.label}-${badge.className}`} className={badge.className}>
                {badge.label}
              </span>
            ))}
          </div>

          <div className="detail-action-row inventory-future-actions">
            <button className="secondary-button" type="button" onClick={openEntry}>
              <ArrowUp size={18} />
              Registrar compra
            </button>
            <button className="secondary-button" type="button" onClick={openExit}>
              <ArrowDown size={18} />
              Registrar salida
            </button>
          </div>
          <p className="panel-note">
            Las entradas y salidas actualizan el stock de este item en tiempo real.
          </p>
        </article>

        <article className="panel">
          <div className="section-heading">
            <p className="eyebrow">Precios</p>
            <h2>Configuración comercial</h2>
          </div>
          <dl className="detail-grid">
            <div>
              <dt>Margen de ganancia</dt>
              <dd>{item.profit_margin_percentage}%</dd>
            </div>
            <div>
              <dt>Precio de venta calculado</dt>
              <dd>{formatInventoryCurrency(item.sale_price_ars)}</dd>
            </div>
            <div>
              <dt>Redondear precio</dt>
              <dd>{item.round_sale_price ? "Sí" : "No"}</dd>
            </div>
            <div>
              <dt>Proveedor habitual</dt>
              <dd>{item.supplier || "No indicado"}</dd>
            </div>
          </dl>
        </article>
      </section>

      <section className="panel">
        <div className="section-heading">
          <p className="eyebrow">Producto</p>
          <h2>Detalles del item</h2>
        </div>
        <dl className="detail-grid">
          <div>
            <dt>Categoría</dt>
            <dd>{getInventoryCategoryLabel(item.category)}</dd>
          </div>
          <div>
            <dt>Subcategoría</dt>
            <dd>{item.subcategory || "No indicada"}</dd>
          </div>
          <div>
            <dt>Unidad</dt>
            <dd>{getInventoryUnitLabel(item.unit)}</dd>
          </div>
          <div>
            <dt>Proveedor</dt>
            <dd>{item.supplier || "No indicado"}</dd>
          </div>
          <div>
            <dt>Lote</dt>
            <dd>{item.lot_number || "No indicado"}</dd>
          </div>
          <div>
            <dt>Fecha de vencimiento</dt>
            <dd>{formatInventoryDate(item.expiration_date)}</dd>
          </div>
          <div className="detail-grid__full">
            <dt>Notas</dt>
            <dd>{item.notes || "Sin notas registradas."}</dd>
          </div>
        </dl>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Movimientos</p>
            <h2>Historial de stock</h2>
          </div>
          <div className="inventory-movement-filters" role="tablist" aria-label="Filtrar movimientos">
            {inventoryMovementFilterOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`secondary-button secondary-button--compact${
                  movementFilter === option.value ? " secondary-button--active" : ""
                }`}
                onClick={() => {
                  setMovementFilter(option.value);
                  void loadMovements(1, option.value);
                }}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {movementState.errorMessage ? (
          <div className="error-state">
            <p>{movementState.errorMessage}</p>
            <button
              className="secondary-button"
              type="button"
              onClick={() => void loadMovements(movementState.page, movementFilter)}
            >
              Reintentar
            </button>
          </div>
        ) : null}

        {movementState.isLoading ? (
          <div className="loading-card" aria-label="Cargando movimientos de inventario" />
        ) : null}

        {!movementState.isLoading && !movementState.errorMessage && movementState.data.length === 0 ? (
          <div className="empty-state">No hay movimientos registrados.</div>
        ) : null}

        {!movementState.isLoading && movementState.data.length > 0 ? (
          <>
            <div className="inventory-movement-list">
              {movementState.data.map((movement) => {
                const amountLabel = getInventoryMovementAmountLabel(movement);
                const actor =
                  movement.created_by_user_name ||
                  movement.created_by_user_email ||
                  "Usuario de la clínica";

                return (
                  <article key={movement.id} className="inventory-movement-card">
                    <span
                      className={`inventory-movement-card__icon inventory-movement-card__icon--${movement.movement_type}`}
                      aria-hidden="true"
                    >
                      {movement.movement_type === "entry" ? (
                        <ArrowUp size={18} />
                      ) : movement.movement_type === "exit" ? (
                        <ArrowDown size={18} />
                      ) : (
                        <Package size={18} />
                      )}
                    </span>

                    <div className="inventory-movement-card__body">
                      <div className="inventory-movement-card__top">
                        <div>
                          <strong>
                            {formatInventorySignedQuantity(
                              movement.quantity,
                              item.unit,
                              movement.movement_type,
                            )}
                          </strong>
                          <p>{getInventoryMovementTypeLabel(movement.movement_type)}</p>
                        </div>
                        <span className="badge badge--blue">
                          {formatInventoryDateTime(movement.created_at)}
                        </span>
                      </div>

                      <div className="inventory-movement-card__meta">
                        {movement.movement_type === "exit" && movement.reason ? (
                          <span>Motivo: {getInventoryExitReasonLabel(movement.reason)}</span>
                        ) : null}
                        {movement.movement_type === "entry" && movement.supplier ? (
                          <span>Proveedor: {movement.supplier}</span>
                        ) : null}
                        {amountLabel ? <span>Monto: {amountLabel}</span> : null}
                        <span>Registrado por: {actor}</span>
                      </div>

                      {movement.notes ? (
                        <p className="inventory-movement-card__notes">{movement.notes}</p>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </div>

            <div className="inventory-pagination">
              <button
                className="secondary-button"
                type="button"
                disabled={movementState.page <= 1}
                onClick={() => void loadMovements(movementState.page - 1, movementFilter)}
              >
                Anterior
              </button>
              <span>
                Página {movementState.page} de {movementState.totalPages}
              </span>
              <button
                className="secondary-button"
                type="button"
                disabled={movementState.page >= movementState.totalPages}
                onClick={() => void loadMovements(movementState.page + 1, movementFilter)}
              >
                Siguiente
              </button>
            </div>
          </>
        ) : null}
      </section>

      {isEditOpen ? (
        <div className="modal-backdrop" role="presentation" onClick={closeEdit}>
          <section
            className="bottom-sheet inventory-edit-sheet"
            role="dialog"
            aria-modal="true"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="bottom-sheet__header">
              <div>
                <p className="eyebrow">Editar</p>
                <h2>Actualizar item</h2>
              </div>
              <button className="icon-button" type="button" onClick={closeEdit}>
                <X size={18} />
              </button>
            </div>

            <InventoryItemForm
              title="Editar item"
              subtitle="Actualizar configuración de inventario"
              formState={formState}
              onChange={setFormState}
              onSubmit={handleSave}
              onCancel={closeEdit}
              isSubmitting={state.isSaving}
              submitLabel="Guardar cambios"
              flowMessage={state.flowMessage}
              manualSalePriceOverride={manualSalePriceOverride}
              onManualSalePriceOverrideChange={setManualSalePriceOverride}
              isEdit
            />
          </section>
        </div>
      ) : null}

      {isEntryOpen ? (
        <div className="modal-backdrop" role="presentation" onClick={closeEntry}>
          <section
            className="bottom-sheet inventory-movement-sheet"
            role="dialog"
            aria-modal="true"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="bottom-sheet__header">
              <div>
                <p className="eyebrow">Inventario</p>
                <h2>Registrar compra (entrada)</h2>
              </div>
              <button className="icon-button" type="button" onClick={closeEntry}>
                <X size={18} />
              </button>
            </div>

            <form className="entity-form inventory-movement-form" onSubmit={handleEntrySubmit}>
              <label className="field">
                <span>Cantidad *</span>
                <input
                  inputMode="decimal"
                  type="number"
                  min="0"
                  step="0.01"
                  value={entryFormState.quantity}
                  onChange={(event) =>
                    setEntryFormState((current) => ({
                      ...current,
                      quantity: event.target.value,
                    }))
                  }
                />
                <small>{getInventoryUnitLabel(item.unit)}</small>
              </label>

              <label className="field">
                <span>Costo total</span>
                <input
                  inputMode="decimal"
                  type="number"
                  min="0"
                  step="0.01"
                  value={entryFormState.total_cost_ars}
                  onChange={(event) =>
                    setEntryFormState((current) => ({
                      ...current,
                      total_cost_ars: event.target.value,
                    }))
                  }
                  placeholder="ARS 0"
                />
              </label>

              <label className="field">
                <span>Costo unitario</span>
                <input
                  inputMode="decimal"
                  type="number"
                  min="0"
                  step="0.01"
                  value={entryFormState.unit_cost_ars}
                  onChange={(event) =>
                    setEntryFormState((current) => ({
                      ...current,
                      unit_cost_ars: event.target.value,
                    }))
                  }
                  placeholder="ARS 0"
                />
              </label>

              {entryUnitCostPreview !== null ? (
                <div className="clinical-section inventory-inline-note">
                  <strong>Costo unitario estimado</strong>
                  <span>{formatInventoryCurrency(String(entryUnitCostPreview))}</span>
                </div>
              ) : null}

              <label className="field">
                <span>Proveedor</span>
                <input
                  value={entryFormState.supplier}
                  onChange={(event) =>
                    setEntryFormState((current) => ({
                      ...current,
                      supplier: event.target.value,
                    }))
                  }
                  placeholder="Distribuidora o laboratorio"
                />
              </label>

              <label className="field">
                <span>Notas</span>
                <textarea
                  rows={4}
                  value={entryFormState.notes}
                  onChange={(event) =>
                    setEntryFormState((current) => ({
                      ...current,
                      notes: event.target.value,
                    }))
                  }
                  placeholder="Observaciones de la compra"
                />
              </label>

              {state.entryMessage ? <div className="error-state">{state.entryMessage}</div> : null}

              <div className="modal-actions">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={closeEntry}
                  disabled={state.isEntrySaving}
                >
                  Cancelar
                </button>
                <button className="primary-button" type="submit" disabled={state.isEntrySaving}>
                  <Save size={18} />
                  {state.isEntrySaving ? "Registrando..." : "Registrar entrada"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}

      {isExitOpen ? (
        <div className="modal-backdrop" role="presentation" onClick={closeExit}>
          <section
            className="bottom-sheet inventory-movement-sheet"
            role="dialog"
            aria-modal="true"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="bottom-sheet__header">
              <div>
                <p className="eyebrow">Inventario</p>
                <h2>Registrar salida</h2>
              </div>
              <button className="icon-button" type="button" onClick={closeExit}>
                <X size={18} />
              </button>
            </div>

            <form className="entity-form inventory-movement-form" onSubmit={handleExitSubmit}>
              <label className="field">
                <span>Cantidad *</span>
                <input
                  inputMode="decimal"
                  type="number"
                  min="0"
                  step="0.01"
                  value={exitFormState.quantity}
                  onChange={(event) =>
                    setExitFormState((current) => ({
                      ...current,
                      quantity: event.target.value,
                    }))
                  }
                />
                <small>
                  Disponible: {formatInventoryQuantity(item.current_stock, item.unit)}
                </small>
              </label>

              <label className="field">
                <span>Motivo *</span>
                <select
                  value={exitFormState.reason}
                  onChange={(event) =>
                    setExitFormState((current) => ({
                      ...current,
                      reason: event.target.value as InventoryExitFormState["reason"],
                    }))
                  }
                >
                  {inventoryExitReasonOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Precio unitario de venta</span>
                <input
                  inputMode="decimal"
                  type="number"
                  min="0"
                  step="0.01"
                  value={exitFormState.unit_sale_price_ars}
                  onChange={(event) =>
                    setExitFormState((current) => ({
                      ...current,
                      unit_sale_price_ars: event.target.value,
                    }))
                  }
                  placeholder="ARS 0"
                />
              </label>

              <label className="field">
                <span>Notas</span>
                <textarea
                  rows={4}
                  value={exitFormState.notes}
                  onChange={(event) =>
                    setExitFormState((current) => ({
                      ...current,
                      notes: event.target.value,
                    }))
                  }
                  placeholder="Detalle de la salida"
                />
              </label>

              {state.exitMessage ? <div className="error-state">{state.exitMessage}</div> : null}

              <div className="modal-actions">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={closeExit}
                  disabled={state.isExitSaving}
                >
                  Cancelar
                </button>
                <button className="primary-button" type="submit" disabled={state.isExitSaving}>
                  <Save size={18} />
                  {state.isExitSaving ? "Registrando..." : "Registrar salida"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}

      {isDeleteOpen ? (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => !state.isDeleting && setIsDeleteOpen(false)}
        >
          <section
            className="bottom-sheet"
            role="dialog"
            aria-modal="true"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="bottom-sheet__header">
              <div>
                <p className="eyebrow">Desactivar</p>
                <h2>Desactivar item</h2>
              </div>
              <button
                className="icon-button"
                type="button"
                onClick={() => !state.isDeleting && setIsDeleteOpen(false)}
              >
                <X size={18} />
              </button>
            </div>

            <div className="danger-callout">
              <strong>Esta acción desactivará el item del inventario.</strong>
              <span>El historial se conservará.</span>
            </div>

            <form className="entity-form" onSubmit={handleDelete}>
              <label className="field">
                <span>Escribe ELIMINAR para confirmar</span>
                <input
                  value={deleteConfirmation}
                  onChange={(event) => setDeleteConfirmation(event.target.value)}
                  placeholder="ELIMINAR"
                />
              </label>

              {state.deleteMessage ? <div className="error-state">{state.deleteMessage}</div> : null}

              <div className="modal-actions">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => setIsDeleteOpen(false)}
                  disabled={state.isDeleting}
                >
                  Cancelar
                </button>
                <button
                  className="danger-button"
                  type="submit"
                  disabled={state.isDeleting || deleteConfirmation !== "ELIMINAR"}
                >
                  {state.isDeleting ? "Desactivando..." : "Confirmar desactivación"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </div>
  );
}

"use client";

import { ArrowDown, ArrowUp, Package, RotateCcw, Save, X } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  formatInventoryDateTime,
  formatInventoryQuantity,
  formatInventorySignedQuantity,
  getInventoryExitReasonLabel,
  getInventoryMovementDirection,
  getInventoryMovementTypeLabel,
} from "@/features/inventory/components/inventory-helpers";
import { getApiErrorMessage } from "@/lib/api";
import { getInventoryMovement, reverseInventoryMovement } from "@/services/inventory";
import type { InventoryMovementDetail as InventoryMovementDetailType, InventoryUnit } from "@/types/api";

type DetailState = {
  isLoading: boolean;
  isSaving: boolean;
  movement: InventoryMovementDetailType | null;
  errorMessage: string | null;
  successMessage: string | null;
  reverseMessage: string | null;
};

type InventoryMovementDetailProps = {
  movementId: string;
};

const initialState: DetailState = {
  isLoading: true,
  isSaving: false,
  movement: null,
  errorMessage: null,
  successMessage: null,
  reverseMessage: null,
};

export function InventoryMovementDetail({ movementId }: InventoryMovementDetailProps) {
  const [state, setState] = useState<DetailState>(initialState);
  const [isReverseOpen, setIsReverseOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");

  const loadMovement = useCallback(async () => {
    setState((current) => ({ ...current, isLoading: true, errorMessage: null }));
    try {
      const response = await getInventoryMovement(movementId);
      setState((current) => ({
        ...current,
        isLoading: false,
        movement: response.data,
        errorMessage: null,
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        isLoading: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }, [movementId]);

  useEffect(() => {
    void loadMovement();
  }, [loadMovement]);

  const movement = state.movement;
  const direction = useMemo(
    () => (movement ? getInventoryMovementDirection(movement.movement_type) : 0),
    [movement],
  );

  function openReverse() {
    setReason("");
    setNotes("");
    setIsReverseOpen(true);
    setState((current) => ({ ...current, reverseMessage: null, successMessage: null }));
  }

  async function handleReverse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!movement) {
      return;
    }
    if (!reason.trim()) {
      setState((current) => ({ ...current, reverseMessage: "Ingresa el motivo de la reversa." }));
      return;
    }
    setState((current) => ({ ...current, isSaving: true, reverseMessage: null }));
    try {
      await reverseInventoryMovement(movement.id, {
        reason: reason.trim(),
        notes: notes.trim() || null,
      });
      await loadMovement();
      setState((current) => ({
        ...current,
        isSaving: false,
        successMessage: "Movimiento revertido correctamente.",
      }));
      setIsReverseOpen(false);
    } catch (error) {
      setState((current) => ({
        ...current,
        isSaving: false,
        reverseMessage: getApiErrorMessage(error),
      }));
    }
  }

  if (state.isLoading && !movement) {
    return <div className="loading-card" aria-label="Cargando movimiento de inventario" />;
  }

  if (state.errorMessage && !movement) {
    return <div className="error-state">{state.errorMessage}</div>;
  }

  if (!movement) {
    return <div className="empty-state">Movimiento no encontrado.</div>;
  }

  const unit = (movement.unit || "unit") as InventoryUnit;
  const actor =
    movement.created_by_user_name || movement.created_by_user_email || "Usuario de la clínica";
  const productName = movement.inventory_item_name || "Producto de inventario";
  const productCode = movement.inventory_item_internal_code || "Sin código";

  return (
    <div className="page-stack inventory-detail-page">
      <section className="detail-hero inventory-detail-hero">
        <Link className="back-link" href="/inventory/movements">
          Volver a movimientos
        </Link>
        <div className="detail-hero__main">
          <span className="inventory-form-hero__icon" aria-hidden="true">
            {direction > 0 ? <ArrowUp size={28} /> : direction < 0 ? <ArrowDown size={28} /> : <Package size={28} />}
          </span>
          <div>
            <h1>{getInventoryMovementTypeLabel(movement.movement_type)}</h1>
            <p>
              {productName} · {productCode}
            </p>
          </div>
        </div>
        <div className="detail-hero__actions">
          <Link className="secondary-button" href={`/inventory/${movement.inventory_item_id}`}>
            Ver producto
          </Link>
          {movement.can_be_reversed ? (
            <button className="primary-button" type="button" onClick={openReverse}>
              <RotateCcw size={18} />
              Revertir
            </button>
          ) : null}
        </div>
      </section>

      {state.successMessage ? <div className="success-state">{state.successMessage}</div> : null}

      <section className="summary-grid">
        <article className="panel">
          <div className="section-heading">
            <p className="eyebrow">Movimiento</p>
            <h2>Stock y cantidad</h2>
          </div>
          <dl className="detail-grid">
            <div>
              <dt>Cantidad</dt>
              <dd>{formatInventorySignedQuantity(movement.quantity, unit, movement.movement_type)}</dd>
            </div>
            <div>
              <dt>Stock antes</dt>
              <dd>{movement.stock_before ? formatInventoryQuantity(movement.stock_before, unit) : "Histórico"}</dd>
            </div>
            <div>
              <dt>Stock después</dt>
              <dd>{movement.stock_after ? formatInventoryQuantity(movement.stock_after, unit) : "Histórico"}</dd>
            </div>
            <div>
              <dt>Unidad</dt>
              <dd>{unit}</dd>
            </div>
          </dl>
        </article>

        <article className="panel">
          <div className="section-heading">
            <p className="eyebrow">Trazabilidad</p>
            <h2>Origen y reversa</h2>
          </div>
          <dl className="detail-grid">
            <div>
              <dt>Fecha</dt>
              <dd>{formatInventoryDateTime(movement.created_at)}</dd>
            </div>
            <div>
              <dt>Registrado por</dt>
              <dd>{actor}</dd>
            </div>
            <div>
              <dt>Origen</dt>
              <dd>{[movement.source_type, movement.source_id].filter(Boolean).join(" · ") || "Manual"}</dd>
            </div>
            <div>
              <dt>Operación</dt>
              <dd>{movement.operation_id || "Histórica"}</dd>
            </div>
            <div>
              <dt>Estado</dt>
              <dd>{getReversalStatusLabel(movement.reversal_status)}</dd>
            </div>
            <div>
              <dt>Reversibilidad</dt>
              <dd>
                {movement.can_be_reversed
                  ? "Disponible"
                  : getReversalBlockLabel(movement.reversal_block_reason)}
              </dd>
            </div>
          </dl>
        </article>
      </section>

      <section className="panel">
        <div className="section-heading">
          <p className="eyebrow">Detalle</p>
          <h2>Notas y relaciones</h2>
        </div>
        <dl className="detail-grid">
          <div>
            <dt>Motivo</dt>
            <dd>{movement.reason ? getInventoryExitReasonLabel(movement.reason) : "Sin motivo"}</dd>
          </div>
          <div>
            <dt>Notas</dt>
            <dd>{movement.notes || "Sin notas"}</dd>
          </div>
          <div>
            <dt>Movimiento revertido</dt>
            <dd>
              {movement.reverses_movement_id ? (
                <Link href={`/inventory/movements/${movement.reverses_movement_id}`}>
                  {movement.reverses_movement_id}
                </Link>
              ) : (
                "No aplica"
              )}
            </dd>
          </div>
          <div>
            <dt>Revertido por</dt>
            <dd>
              {movement.reversed_by_movement_id ? (
                <Link href={`/inventory/movements/${movement.reversed_by_movement_id}`}>
                  {movement.reversed_by_movement_id}
                </Link>
              ) : (
                "No aplica"
              )}
            </dd>
          </div>
        </dl>
      </section>

      {isReverseOpen ? (
        <div className="modal-backdrop" role="presentation" onClick={() => !state.isSaving && setIsReverseOpen(false)}>
          <section
            className="bottom-sheet"
            role="dialog"
            aria-modal="true"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="bottom-sheet__header">
              <div>
                <p className="eyebrow">Reversa</p>
                <h2>Revertir movimiento</h2>
              </div>
              <button className="icon-button" type="button" onClick={() => setIsReverseOpen(false)}>
                <X size={18} />
              </button>
            </div>
            <form className="entity-form" onSubmit={handleReverse} noValidate>
              <label className="field">
                <span>Motivo *</span>
                <input
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  maxLength={50}
                  required
                />
              </label>
              <label className="field">
                <span>Notas</span>
                <textarea rows={4} value={notes} onChange={(event) => setNotes(event.target.value)} />
              </label>
              {state.reverseMessage ? <div className="error-state">{state.reverseMessage}</div> : null}
              <div className="modal-actions">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => setIsReverseOpen(false)}
                  disabled={state.isSaving}
                >
                  Cancelar
                </button>
                <button className="primary-button" type="submit" disabled={state.isSaving}>
                  <Save size={18} />
                  {state.isSaving ? "Revirtiendo..." : "Confirmar reversa"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </div>
  );
}

function getReversalStatusLabel(status: InventoryMovementDetailType["reversal_status"]) {
  if (status === "reversed") {
    return "Revertido";
  }
  if (status === "reversal") {
    return "Reversa";
  }
  return "Activo";
}

function getReversalBlockLabel(reason: string | null) {
  if (reason === "movement_already_reversed") {
    return "Movimiento ya revertido";
  }
  if (reason === "reversal_movements_cannot_be_reversed") {
    return "Las reversas no se revierten";
  }
  if (reason === "insufficient_stock_for_reversal") {
    return "Stock insuficiente para revertir";
  }
  if (reason === "movement_type_not_reversible") {
    return "Tipo histórico no reversible";
  }
  return "No disponible";
}

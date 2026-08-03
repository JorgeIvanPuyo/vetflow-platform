"use client";

import { ArrowLeft, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  formatInventoryDateTime,
} from "@/features/inventory/components/inventory-helpers";
import {
  formatUserName,
  labelBulkOperation,
  labelBulkStatus,
} from "@/features/inventory/components/inventory-bulk-operations-screen";
import { getApiErrorMessage } from "@/lib/api";
import {
  getInventoryBulkOperation,
  reverseInventoryBulkOperation,
} from "@/services/inventory";
import type { InventoryBulkOperation } from "@/types/api";

type Props = {
  operationId: string;
};

export function InventoryBulkOperationDetail({ operationId }: Props) {
  const [operation, setOperation] = useState<InventoryBulkOperation | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [isReversing, setIsReversing] = useState(false);

  const load = useCallback(async () => {
    setErrorMessage(null);
    try {
      const response = await getInventoryBulkOperation(operationId);
      setOperation(response.data);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    }
  }, [operationId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleReverse() {
    if (!reason.trim()) {
      setErrorMessage("Ingresa un motivo para revertir.");
      return;
    }
    setIsReversing(true);
    setErrorMessage(null);
    try {
      const response = await reverseInventoryBulkOperation(operationId, reason);
      setOperation(response.data);
      setReason("");
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsReversing(false);
    }
  }

  return (
    <div className="page-stack inventory-page">
      <section className="screen-heading list-page__header">
        <div>
          <Link className="back-link" href="/inventory/bulk-operations">
            <ArrowLeft size={18} />
            Operaciones
          </Link>
          <h1>{operation ? labelBulkOperation(operation.operation_type) : "Operación grupal"}</h1>
          <p>{operation ? `${labelBulkStatus(operation.status)} · ${operation.affected_count} afectados` : "Cargando..."}</p>
        </div>
      </section>
      {errorMessage ? <section className="error-state">{errorMessage}</section> : null}
      {operation ? (
        <>
          <section className="inventory-summary-grid">
            <article className="inventory-summary-card">
              <span className="inventory-summary-card__label">Seleccionados</span>
              <strong>{operation.selected_count}</strong>
              <small>{operation.selection_mode}</small>
            </article>
            <article className="inventory-summary-card inventory-summary-card--warning">
              <span className="inventory-summary-card__label">Sin cambio</span>
              <strong>{operation.unchanged_count}</strong>
              <small>Filas omitidas</small>
            </article>
            <article className="inventory-summary-card inventory-summary-card--danger-soft">
              <span className="inventory-summary-card__label">Conflictos</span>
              <strong>{operation.conflict_count}</strong>
              <small>Revisión requerida</small>
            </article>
          </section>
          <section className="panel inventory-bulk-traceability" aria-label="Trazabilidad de operación grupal">
            <div>
              <h2>Trazabilidad</h2>
              <p>{operation.id}</p>
            </div>
            <dl className="inventory-bulk-traceability__grid">
              <div>
                <dt>Ejecutada por</dt>
                <dd>{formatUserName(operation.created_by_user_name, operation.created_by_user_email)}</dd>
              </div>
              <div>
                <dt>Creada el</dt>
                <dd>{formatInventoryDateTime(operation.created_at)}</dd>
              </div>
              <div>
                <dt>Confirmada el</dt>
                <dd>{formatInventoryDateTime(operation.confirmed_at)}</dd>
              </div>
              <div>
                <dt>Estado</dt>
                <dd>{labelBulkStatus(operation.status)}</dd>
              </div>
              <div>
                <dt>Tipo</dt>
                <dd>{labelBulkOperation(operation.operation_type)}</dd>
              </div>
              <div>
                <dt>Revertida por</dt>
                <dd>
                  {operation.reversed_at
                    ? formatUserName(operation.reversed_by_user_name, operation.reversed_by_user_email)
                    : "Sin reversión"}
                </dd>
              </div>
              <div>
                <dt>Revertida el</dt>
                <dd>{formatInventoryDateTime(operation.reversed_at)}</dd>
              </div>
              <div>
                <dt>Motivo</dt>
                <dd>{operation.reversal_reason || "Sin reversión"}</dd>
              </div>
            </dl>
          </section>
          <section className="panel inventory-bulk-sheet">
            <label className="field">
              <span>Motivo de reversión</span>
              <input value={reason} onChange={(event) => setReason(event.target.value)} />
            </label>
            <button
              className="secondary-button"
              disabled={isReversing || !["confirmed", "partially_reversed"].includes(operation.status)}
              type="button"
              onClick={handleReverse}
            >
              <RotateCcw size={18} />
              Revertir cambios
            </button>
            {operation.reversed_at ? (
              <p className="panel-note">
                Revertida por {formatUserName(operation.reversed_by_user_name, operation.reversed_by_user_email)} el{" "}
                {formatInventoryDateTime(operation.reversed_at)}. {operation.reversed_count} filas revertidas,
                {" "}{operation.conflict_count} conflictos.
              </p>
            ) : null}
          </section>
          <section className="inventory-table-card" aria-label="Detalle de operación grupal">
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
                  {operation.items.map((row) => (
                    <tr key={row.id} className="inventory-table__row--static">
                      <td>{row.inventory_item_name ?? row.inventory_item_id}</td>
                      <td>{row.field_name}</td>
                      <td>{formatValue(row.old_value_json)}</td>
                      <td>{formatValue(row.new_value_json)}</td>
                      <td>{row.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}

function formatValue(value: Record<string, unknown> | null) {
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

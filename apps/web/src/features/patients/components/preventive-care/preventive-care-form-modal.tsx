"use client";

import { X } from "lucide-react";
import type { FormEvent } from "react";

import type { PreventiveCareType } from "@/types/api";

import {
  PreventiveCareFormState,
  preventiveCareTypeOptions,
} from "./preventive-care-form";

type PreventiveCareFormModalProps = {
  mode: "create" | "edit";
  formState: PreventiveCareFormState;
  isSubmitting: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onUpdateForm: (nextState: PreventiveCareFormState) => void;
};

export function PreventiveCareFormModal({
  mode,
  formState,
  isSubmitting,
  error,
  onClose,
  onSubmit,
  onUpdateForm,
}: PreventiveCareFormModalProps) {
  const title = mode === "edit" ? "Editar vacuna o desparasitación" : "Agregar vacuna o desparasitación";
  const submitLabel = mode === "edit" ? "Guardar cambios" : "Guardar";

  return (
    <div className="modal-backdrop" role="presentation">
      <section aria-labelledby="preventive-care-title" aria-modal="true" className="bottom-sheet" role="dialog">
        <div className="bottom-sheet__header">
          <div>
            <p className="eyebrow">Prevención</p>
            <h2 id="preventive-care-title">{title}</h2>
          </div>
          <button
            aria-label="Cancelar"
            className="icon-button"
            disabled={isSubmitting}
            onClick={onClose}
            type="button"
          >
            <X aria-hidden="true" size={20} />
          </button>
        </div>

        {error ? <div className="error-state">{error}</div> : null}

        <form className="entity-form" onSubmit={onSubmit}>
          <div className="form-grid">
            <label className="field">
              <span>Nombre</span>
              <input
                required
                value={formState.name}
                onChange={(event) => onUpdateForm({ ...formState, name: event.target.value })}
              />
            </label>
            <label className="field">
              <span>Tipo</span>
              <select
                value={formState.care_type}
                onChange={(event) =>
                  onUpdateForm({ ...formState, care_type: event.target.value as PreventiveCareType })
                }
              >
                {preventiveCareTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Fecha</span>
              <input
                required
                type="datetime-local"
                value={formState.applied_at}
                onChange={(event) => onUpdateForm({ ...formState, applied_at: event.target.value })}
              />
            </label>
            <label className="field">
              <span>Próxima dosis</span>
              <input
                type="datetime-local"
                value={formState.next_due_at}
                onChange={(event) => onUpdateForm({ ...formState, next_due_at: event.target.value })}
              />
            </label>
          </div>
          <label className="field">
            <span>Lote</span>
            <input
              value={formState.lot_number}
              onChange={(event) => onUpdateForm({ ...formState, lot_number: event.target.value })}
            />
          </label>
          <label className="field">
            <span>Notas</span>
            <textarea
              rows={3}
              value={formState.notes}
              onChange={(event) => onUpdateForm({ ...formState, notes: event.target.value })}
            />
          </label>
          <div className="modal-actions">
            <button className="secondary-button" disabled={isSubmitting} onClick={onClose} type="button">
              Cancelar
            </button>
            <button className="primary-button" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Guardando..." : submitLabel}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

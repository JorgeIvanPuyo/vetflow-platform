"use client";

import { X } from "lucide-react";

import type { PreventiveCare } from "@/types/api";

import { getPreventiveCareTypeLabel } from "./preventive-care-form";

type PreventiveCareDeleteDialogProps = {
  record: PreventiveCare;
  isDeleting: boolean;
  error: string | null;
  onConfirm: () => void;
  onClose: () => void;
};

export function PreventiveCareDeleteDialog({
  record,
  isDeleting,
  error,
  onConfirm,
  onClose,
}: PreventiveCareDeleteDialogProps) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section aria-labelledby="delete-preventive-title" aria-modal="true" className="bottom-sheet" role="dialog">
        <div className="bottom-sheet__header">
          <div>
            <p className="eyebrow">Acción irreversible</p>
            <h2 id="delete-preventive-title">Eliminar registro preventivo</h2>
          </div>
          <button
            aria-label="Cancelar"
            className="icon-button"
            disabled={isDeleting}
            onClick={onClose}
            type="button"
          >
            <X aria-hidden="true" size={20} />
          </button>
        </div>

        <div className="danger-callout" role="alert">
          <strong>
            {record.name} · {getPreventiveCareTypeLabel(record.care_type)}
          </strong>
          <span>
            Esta acción eliminará el registro de la historia clínica del paciente. Esta acción no se
            puede deshacer.
          </span>
        </div>

        {error ? <div className="error-state">{error}</div> : null}

        <div className="modal-actions">
          <button className="secondary-button" disabled={isDeleting} onClick={onClose} type="button">
            Cancelar
          </button>
          <button className="danger-button" disabled={isDeleting} onClick={onConfirm} type="button">
            {isDeleting ? "Eliminando..." : "Eliminar"}
          </button>
        </div>
      </section>
    </div>
  );
}

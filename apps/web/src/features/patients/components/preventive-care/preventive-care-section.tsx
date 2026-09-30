"use client";

import { canPerformClinicalActions } from "@/lib/permissions";

import { useCurrentUser } from "@/features/auth/current-user-context";

import { Edit, Plus, Syringe, Trash2 } from "lucide-react";

import { formatDateTime } from "@/lib/datetime";
import { getTraceableUserName } from "@/lib/user-traceability";
import type { PreventiveCare } from "@/types/api";

import { getPreventiveCareTypeLabel } from "./preventive-care-form";

type PreventiveCareSectionProps = {
  records: PreventiveCare[];
  onAdd: () => void;
  onEdit: (record: PreventiveCare) => void;
  onDelete: (record: PreventiveCare) => void;
};

export function PreventiveCareSection({
  records,
  onAdd,
  onEdit,
  onDelete,
}: PreventiveCareSectionProps) {
  const { role } = useCurrentUser();
  const isClinicalReadOnly = !canPerformClinicalActions(role);
  return (
    <section className="panel patient-detail-section">
      <div className="section-heading section-heading--row">
        <div>
          <p className="eyebrow">Prevención</p>
          <h2>Vacunas y desparasitación</h2>
          <p>Registros preventivos persistentes del paciente.</p>
        </div>
        <button disabled={isClinicalReadOnly} className="primary-button" type="button" onClick={onAdd}>
          <Plus aria-hidden="true" size={18} /> Agregar
        </button>
      </div>

      {records.length === 0 ? (
        <div className="empty-state">No hay vacunas o desparasitaciones registradas.</div>
      ) : (
        <div className="record-card-list">
          {records.map((record) => (
            <article className="record-card record-card--with-actions" key={record.id}>
              <span className="icon-bubble"><Syringe size={20} /></span>
              <div>
                <h3>{record.name}</h3>
                <p>{getPreventiveCareTypeLabel(record.care_type)} · Aplicado {formatDateTime(record.applied_at)}</p>
                {record.next_due_at ? <p>Próxima dosis: {formatDateTime(record.next_due_at)}</p> : null}
                {record.lot_number ? <p>Lote: {record.lot_number}</p> : null}
                {record.notes ? <p>{record.notes}</p> : null}
                {getTraceableUserName(record, "created_by") ? (
                  <p className="traceability-meta traceability-meta--compact">
                    <strong>Registrado por:</strong>{" "}
                    {getTraceableUserName(record, "created_by")}
                  </p>
                ) : null}
              </div>
              <div className="record-card__icon-actions">
                <button disabled={isClinicalReadOnly}
                  aria-label={`Editar ${record.name}`}
                  className="icon-button"
                  onClick={() => onEdit(record)}
                  title="Editar"
                  type="button"
                >
                  <Edit aria-hidden="true" size={16} />
                </button>
                <button disabled={isClinicalReadOnly}
                  aria-label={`Eliminar ${record.name}`}
                  className="icon-button icon-button--danger"
                  onClick={() => onDelete(record)}
                  title="Eliminar"
                  type="button"
                >
                  <Trash2 aria-hidden="true" size={16} />
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

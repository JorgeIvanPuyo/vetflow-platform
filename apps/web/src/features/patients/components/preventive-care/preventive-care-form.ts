import { toDateTimeLocalValue } from "@/lib/datetime";
import type {
  CreatePreventiveCarePayload,
  PreventiveCare,
  PreventiveCareType,
} from "@/types/api";

export type PreventiveCareFormState = {
  name: string;
  care_type: PreventiveCareType;
  applied_at: string;
  next_due_at: string;
  lot_number: string;
  notes: string;
};

export const preventiveCareTypeOptions: Array<{ value: PreventiveCareType; label: string }> = [
  { value: "vaccine", label: "Vacuna" },
  { value: "deworming", label: "Desparasitación" },
  { value: "other", label: "Otro" },
];

export function getPreventiveCareTypeLabel(type: PreventiveCareType) {
  const labels: Record<PreventiveCareType, string> = {
    vaccine: "Vacuna",
    deworming: "Desparasitación",
    other: "Otro",
  };
  return labels[type];
}

/** Estado inicial del formulario para crear un registro (fecha = ahora). */
export function createInitialPreventiveCareFormState(): PreventiveCareFormState {
  return {
    name: "",
    care_type: "vaccine",
    applied_at: toDateTimeLocalValue(new Date()),
    next_due_at: "",
    lot_number: "",
    notes: "",
  };
}

/** Precarga el formulario con los datos de un registro existente (para editar). */
export function toPreventiveCareFormState(record: PreventiveCare): PreventiveCareFormState {
  return {
    name: record.name,
    care_type: record.care_type,
    applied_at: toDateTimeLocalValue(record.applied_at),
    next_due_at: record.next_due_at ? toDateTimeLocalValue(record.next_due_at) : "",
    lot_number: record.lot_number ?? "",
    notes: record.notes ?? "",
  };
}

/** Construye el payload de API a partir del estado del formulario. */
export function toPreventiveCarePayload(
  formState: PreventiveCareFormState,
): CreatePreventiveCarePayload {
  return {
    name: formState.name.trim(),
    care_type: formState.care_type,
    applied_at: new Date(formState.applied_at).toISOString(),
    next_due_at: formState.next_due_at ? new Date(formState.next_due_at).toISOString() : null,
    lot_number: formState.lot_number.trim() || null,
    notes: formState.notes.trim() || null,
  };
}

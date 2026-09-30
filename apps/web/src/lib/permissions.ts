import type { AppRole } from "@/types/api";

export function canOperateClinic(role: AppRole | null): boolean {
  return role === "clinic_admin" || role === "medico_veterinario" ||
    role === "contador" || role === "secretaria";
}

export function canPerformClinicalActions(role: AppRole | null): boolean {
  return role === "medico_veterinario";
}

export function canDeleteClinicalHistory(role: AppRole | null): boolean {
  return canPerformClinicalActions(role) || role === "superadmin";
}

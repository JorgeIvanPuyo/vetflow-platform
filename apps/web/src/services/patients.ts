import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  ApiListResponse,
  ClinicalHistory,
  CreatePatientPayload,
  Patient,
  UpdatePatientPayload,
} from "@/types/api";

type GetPatientsOptions = {
  ownerId?: string;
};

export function getPatients(options: GetPatientsOptions = {}) {
  const params = new URLSearchParams();

  if (options.ownerId) {
    params.set("owner_id", options.ownerId);
  }

  const query = params.toString();
  return api.get<ApiListResponse<Patient>>(
    query ? `/api/v1/patients?${query}` : "/api/v1/patients",
  );
}

export function getPatient(patientId: string) {
  return api.get<ApiItemResponse<Patient>>(`/api/v1/patients/${patientId}`);
}

export function getPatientClinicalHistory(patientId: string) {
  return api.get<ApiItemResponse<ClinicalHistory>>(
    `/api/v1/patients/${patientId}/clinical-history`,
  );
}

export function createPatient(payload: CreatePatientPayload) {
  return api.post<ApiItemResponse<Patient>>("/api/v1/patients", payload);
}

export function updatePatient(patientId: string, payload: UpdatePatientPayload) {
  return api.patch<ApiItemResponse<Patient>>(`/api/v1/patients/${patientId}`, payload);
}

export function deletePatient(patientId: string) {
  return api.delete<void>(`/api/v1/patients/${patientId}`);
}

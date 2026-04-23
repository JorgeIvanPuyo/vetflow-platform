import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  ApiListResponse,
  CreatePatientPayload,
  Patient,
} from "@/types/api";

export function getPatients() {
  return api.get<ApiListResponse<Patient>>("/api/v1/patients");
}

export function getPatient(patientId: string) {
  return api.get<ApiItemResponse<Patient>>(`/api/v1/patients/${patientId}`);
}

export function createPatient(payload: CreatePatientPayload) {
  return api.post<ApiItemResponse<Patient>>("/api/v1/patients", payload);
}

import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  ApiListResponse,
  CreatePreventiveCarePayload,
  PreventiveCare,
  UpdatePreventiveCarePayload,
} from "@/types/api";

export function getPatientPreventiveCare(patientId: string) {
  return api.get<ApiListResponse<PreventiveCare>>(
    `/api/v1/patients/${patientId}/preventive-care`,
  );
}

export function createPreventiveCare(
  patientId: string,
  payload: CreatePreventiveCarePayload,
) {
  return api.post<ApiItemResponse<PreventiveCare>>(
    `/api/v1/patients/${patientId}/preventive-care`,
    payload,
  );
}

export function getPreventiveCare(recordId: string) {
  return api.get<ApiItemResponse<PreventiveCare>>(
    `/api/v1/preventive-care/${recordId}`,
  );
}

export function updatePreventiveCare(
  recordId: string,
  payload: UpdatePreventiveCarePayload,
) {
  return api.patch<ApiItemResponse<PreventiveCare>>(
    `/api/v1/preventive-care/${recordId}`,
    payload,
  );
}

export function deletePreventiveCare(recordId: string) {
  return api.delete<void>(`/api/v1/preventive-care/${recordId}`);
}

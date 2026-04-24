import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  ApiListResponse,
  Consultation,
  CreateConsultationPayload,
  UpdateConsultationPayload,
} from "@/types/api";

export function getPatientConsultations(patientId: string) {
  return api.get<ApiListResponse<Consultation>>(
    `/api/v1/patients/${patientId}/consultations`,
  );
}

export function createConsultation(payload: CreateConsultationPayload) {
  return api.post<ApiItemResponse<Consultation>>("/api/v1/consultations", payload);
}

export function getConsultation(consultationId: string) {
  return api.get<ApiItemResponse<Consultation>>(
    `/api/v1/consultations/${consultationId}`,
  );
}

export function updateConsultation(
  consultationId: string,
  payload: UpdateConsultationPayload,
) {
  return api.patch<ApiItemResponse<Consultation>>(
    `/api/v1/consultations/${consultationId}`,
    payload,
  );
}

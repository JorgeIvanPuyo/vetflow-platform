import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  ApiListResponse,
  Consultation,
  ConsultationAiSummaryResponse,
  ConsultationMedication,
  ConsultationStudyRequest,
  CreateConsultationPayload,
  CreateMedicationPayload,
  CreateStudyRequestPayload,
  StepUpdatePayload,
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

export function createFollowUpConsultation(consultationId: string) {
  return api.post<ApiItemResponse<Consultation>>(
    `/api/v1/consultations/${consultationId}/follow-up`,
    {},
  );
}

export function getConsultation(consultationId: string) {
  return api.get<ApiItemResponse<Consultation>>(
    `/api/v1/consultations/${consultationId}`,
  );
}

export function generateConsultationAiSummary(consultationId: string) {
  return api.post<ConsultationAiSummaryResponse>(
    `/api/v1/consultations/${consultationId}/ai-summary`,
    {},
    { retryTransient: false },
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

export function deleteConsultation(consultationId: string) {
  return api.delete<void>(`/api/v1/consultations/${consultationId}`);
}

export function updateConsultationStep(
  consultationId: string,
  payload: StepUpdatePayload,
) {
  return api.patch<ApiItemResponse<Consultation>>(
    `/api/v1/consultations/${consultationId}/step`,
    payload,
  );
}

export function createConsultationMedication(
  consultationId: string,
  payload: CreateMedicationPayload,
) {
  return api.post<ApiItemResponse<ConsultationMedication>>(
    `/api/v1/consultations/${consultationId}/medications`,
    payload,
  );
}

export function deleteConsultationMedication(medicationId: string) {
  return api.delete<void>(`/api/v1/consultation-medications/${medicationId}`);
}

export function createConsultationStudyRequest(
  consultationId: string,
  payload: CreateStudyRequestPayload,
) {
  return api.post<ApiItemResponse<ConsultationStudyRequest>>(
    `/api/v1/consultations/${consultationId}/study-requests`,
    payload,
  );
}

export function deleteConsultationStudyRequest(studyRequestId: string) {
  return api.delete<void>(
    `/api/v1/consultation-study-requests/${studyRequestId}`,
  );
}

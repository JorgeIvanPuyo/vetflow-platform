import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  ApiListResponse,
  CreateExamPayload,
  Exam,
  UpdateExamPayload,
} from "@/types/api";

export function createExam(payload: CreateExamPayload) {
  return api.post<ApiItemResponse<Exam>>("/api/v1/exams", payload);
}

export function getExam(examId: string) {
  return api.get<ApiItemResponse<Exam>>(`/api/v1/exams/${examId}`);
}

export function updateExam(examId: string, payload: UpdateExamPayload) {
  return api.patch<ApiItemResponse<Exam>>(`/api/v1/exams/${examId}`, payload);
}

export function getPatientExams(patientId: string) {
  return api.get<ApiListResponse<Exam>>(`/api/v1/patients/${patientId}/exams`);
}

export function getConsultationExams(consultationId: string) {
  return api.get<ApiListResponse<Exam>>(
    `/api/v1/consultations/${consultationId}/exams`,
  );
}

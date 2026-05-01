import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  ApiListResponse,
  CreatePatientFileReferencePayload,
  FileDownloadUrlResponse,
  PatientFileReference,
  UpdatePatientFileReferencePayload,
} from "@/types/api";

export function getPatientFileReferences(patientId: string) {
  return api.get<ApiListResponse<PatientFileReference>>(
    `/api/v1/patients/${patientId}/file-references`,
  );
}

export function createPatientFileReference(
  patientId: string,
  payload: CreatePatientFileReferencePayload,
) {
  return api.post<ApiItemResponse<PatientFileReference>>(
    `/api/v1/patients/${patientId}/file-references`,
    payload,
  );
}

export function uploadPatientFile(patientId: string, formData: FormData) {
  return api.postFormData<ApiItemResponse<PatientFileReference>>(
    `/api/v1/patients/${patientId}/files/upload`,
    formData,
  );
}

export function getPatientFileReference(fileReferenceId: string) {
  return api.get<ApiItemResponse<PatientFileReference>>(
    `/api/v1/file-references/${fileReferenceId}`,
  );
}

export function updatePatientFileReference(
  fileReferenceId: string,
  payload: UpdatePatientFileReferencePayload,
) {
  return api.patch<ApiItemResponse<PatientFileReference>>(
    `/api/v1/file-references/${fileReferenceId}`,
    payload,
  );
}

export function deletePatientFileReference(fileReferenceId: string) {
  return api.delete<void>(`/api/v1/file-references/${fileReferenceId}`);
}

export function getFileReferenceDownloadUrl(fileReferenceId: string) {
  return api.get<ApiItemResponse<FileDownloadUrlResponse>>(
    `/api/v1/file-references/${fileReferenceId}/download-url`,
  );
}

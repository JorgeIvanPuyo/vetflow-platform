import { api } from "@/lib/api";
import type { ClinicalHistoryPdfExportPayload } from "@/types/api";

export function exportClinicalHistoryPdf(
  patientId: string,
  payload: ClinicalHistoryPdfExportPayload,
) {
  return api.postBlob(
    `/api/v1/patients/${patientId}/clinical-history/export-pdf`,
    payload,
  );
}

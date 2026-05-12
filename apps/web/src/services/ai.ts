import { api } from "@/lib/api";
import type {
  GenerateConsultationSummaryRequest,
  GenerateConsultationSummaryResponse,
  RewriteClinicalNoteRequest,
  RewriteClinicalNoteResponse,
} from "@/types/api";

export function rewriteClinicalNote(payload: RewriteClinicalNoteRequest) {
  return api.post<RewriteClinicalNoteResponse>(
    "/api/v1/ai/rewrite-clinical-note",
    payload,
    { retryTransient: false },
  );
}

export function generateConsultationSummary(
  payload: GenerateConsultationSummaryRequest,
) {
  return api.post<GenerateConsultationSummaryResponse>(
    "/api/v1/ai/generate-consultation-summary",
    payload,
    { retryTransient: false },
  );
}

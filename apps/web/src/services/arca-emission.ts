import { api } from "@/lib/api";
import type { ApiItemResponse } from "@/types/api";
import type { FiscalBusinessPayload, FiscalEmission, FiscalEmissionReadiness, FiscalEmissions } from "@/types/arca-emission";

export function getFiscalEmissions(saleId: string) {
  return api.get<ApiItemResponse<FiscalEmissions>>(`/api/v1/sales/${saleId}/fiscal-emissions`);
}
export function prepareFiscalEmission(saleId: string, proposalId: string, fiscalData: FiscalBusinessPayload, idempotencyKey: string, supersedesId?: string | null) {
  return api.post<ApiItemResponse<FiscalEmission>>(`/api/v1/sales/${saleId}/fiscal-emissions`, { proposal_id: proposalId, fiscal_data: fiscalData, confirm_fiscal_identity: true, ...(supersedesId ? { supersedes_id: supersedesId } : {}) }, { retryTransient: false, idempotencyKey });
}
export function issueFiscalEmission(saleId: string, emissionId: string) {
  return api.post<ApiItemResponse<FiscalEmission>>(`/api/v1/sales/${saleId}/fiscal-emissions/${emissionId}/issue`, { confirm: true }, { retryTransient: false });
}
export function reconcileFiscalEmission(saleId: string, emissionId: string, retrySameRequest = false) {
  return api.post<ApiItemResponse<FiscalEmission>>(`/api/v1/sales/${saleId}/fiscal-emissions/${emissionId}/reconcile`, retrySameRequest ? { retry_same_request: true, confirm: true } : {}, { retryTransient: false });
}
export function regenerateFiscalEmission(saleId: string, emissionId: string) {
  return api.post<ApiItemResponse<FiscalEmission>>(`/api/v1/sales/${saleId}/fiscal-emissions/${emissionId}/regenerate`, {}, { retryTransient: false });
}
export function getFiscalEmissionFile(saleId: string, emissionId: string, versionId?: string) {
  const query = versionId ? `?version_id=${encodeURIComponent(versionId)}` : "";
  return api.getBlob(`/api/v1/sales/${saleId}/fiscal-emissions/${emissionId}/file${query}`);
}
export function getFiscalEmissionReadiness(seriesId: string) {
  return api.get<ApiItemResponse<FiscalEmissionReadiness>>(`/api/v1/fiscal/emission-readiness?series_id=${encodeURIComponent(seriesId)}`);
}
export function validateFiscalEmissionReadiness(seriesId: string) {
  return api.post<ApiItemResponse<FiscalEmissionReadiness>>("/api/v1/fiscal/emission-readiness/validate", { series_id: seriesId }, { retryTransient: false });
}

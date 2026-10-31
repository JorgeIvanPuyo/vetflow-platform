import { api } from "@/lib/api";
import type { ApiItemResponse } from "@/types/api";
import type { FiscalConfiguration, FiscalPolicy, FiscalPolicyInput, FiscalProposal, FiscalProposalInput, FiscalReview, FiscalSeries, FiscalSeriesInput } from "@/types/fiscal";

export function getFiscalConfiguration() {
  return api.get<ApiItemResponse<FiscalConfiguration>>("/api/v1/fiscal/configuration");
}
export function updateFiscalPolicy(payload: FiscalPolicyInput) {
  return api.patch<ApiItemResponse<FiscalPolicy>>("/api/v1/fiscal/configuration/policy", payload);
}
export function createFiscalSeries(payload: FiscalSeriesInput) {
  return api.post<ApiItemResponse<FiscalSeries>>("/api/v1/fiscal/configuration/series", payload, { retryTransient: false });
}
export function updateFiscalSeries(id: string, payload: Partial<FiscalSeriesInput>) {
  return api.patch<ApiItemResponse<FiscalSeries>>(`/api/v1/fiscal/configuration/series/${id}`, payload);
}

export function getSaleFiscalReview(saleId: string) {
  return api.get<ApiItemResponse<FiscalReview>>(`/api/v1/sales/${saleId}/fiscal-review`);
}
export function generateFiscalProposals(saleId: string, payload: FiscalProposalInput) {
  return api.post<ApiItemResponse<FiscalProposal[]>>(`/api/v1/sales/${saleId}/fiscal-proposals`, payload, { retryTransient: false });
}
export function updateFiscalProposal(saleId: string, proposalId: string, payload: FiscalProposalInput) {
  return api.patch<ApiItemResponse<FiscalProposal>>(`/api/v1/sales/${saleId}/fiscal-proposals/${proposalId}`, payload);
}
export function approveFiscalProposal(saleId: string, proposal: Pick<FiscalProposal, "id" | "content_hash">, idempotencyKey: string) {
  return api.post<ApiItemResponse<FiscalProposal>>(`/api/v1/sales/${saleId}/fiscal-proposals/${proposal.id}/approve`, { content_hash: proposal.content_hash, confirm_fiscal_identity: true }, { retryTransient: false, idempotencyKey });
}
export function cancelFiscalProposal(saleId: string, proposalId: string, reason: string) {
  return api.post<ApiItemResponse<FiscalProposal>>(`/api/v1/sales/${saleId}/fiscal-proposals/${proposalId}/cancel`, { reason }, { retryTransient: false });
}

export function allocateManualFiscalDocument(saleId: string, documentId: string, paymentIds: string[], idempotencyKey: string) {
  return api.post<ApiItemResponse<FiscalReview>>(`/api/v1/sales/${saleId}/fiscal-documents/${documentId}/allocate`, { payment_ids: paymentIds, confirm_fiscal_identity: true }, { retryTransient: false, idempotencyKey });
}

import { api } from "@/lib/api";
import type { ApiItemResponse, FiscalIssuer, FiscalIssuerWritePayload, PurchaseCreatorOption, Sale, SaleFiscalDocument, SaleListFilters, SaleSummary, SaleWritePayload } from "@/types/api";

export type SaleListResponse = { data: SaleSummary[]; meta: { page: number; page_size: number; total: number; total_pages: number } };

export function getSales(filters: SaleListFilters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== "") params.set(key, String(value)); });
  const query = params.toString();
  return api.get<SaleListResponse>(`/api/v1/sales${query ? `?${query}` : ""}`);
}

export function getSale(id: string) { return api.get<ApiItemResponse<Sale>>(`/api/v1/sales/${id}`); }
export function createSale(payload: SaleWritePayload) { return api.post<ApiItemResponse<Sale>>("/api/v1/sales", payload); }
export function updateSale(id: string, payload: SaleWritePayload) { return api.patch<ApiItemResponse<Sale>>(`/api/v1/sales/${id}`, payload); }
export function cancelSale(id: string, reason: string) { return api.post<ApiItemResponse<Sale>>(`/api/v1/sales/${id}/cancel`, { reason }, { retryTransient: false }); }
export function confirmSale(id: string) { return api.post<ApiItemResponse<Sale>>(`/api/v1/sales/${id}/confirm`, { confirm: true }, { retryTransient: false }); }
export function reverseSale(id: string, reason: string) { return api.post<ApiItemResponse<Sale>>(`/api/v1/sales/${id}/reverse`, { reason }, { retryTransient: false }); }
export function getSaleFilterOptions() { return api.get<{ data: { creators: PurchaseCreatorOption[] }; meta: Record<string, never> }>("/api/v1/sales/filter-options"); }

export function getFiscalIssuers(activeOnly = false) {
  return api.get<{ data: FiscalIssuer[]; meta: { total: number } }>(`/api/v1/fiscal-issuers${activeOnly ? "?active_only=true" : ""}`);
}
export function createFiscalIssuer(payload: FiscalIssuerWritePayload) { return api.post<ApiItemResponse<FiscalIssuer>>("/api/v1/fiscal-issuers", payload, { retryTransient: false }); }
export function updateFiscalIssuer(id: string, payload: Partial<FiscalIssuerWritePayload>) { return api.patch<ApiItemResponse<FiscalIssuer>>(`/api/v1/fiscal-issuers/${id}`, payload); }

export type SaleFiscalDocumentForm = {
  fiscal_issuer_id: string;
  document_type: string;
  document_code: string;
  document_number: string;
  issue_date: string;
  file?: File | null;
};

function fiscalDocumentFormData(payload: SaleFiscalDocumentForm) {
  const formData = new FormData();
  formData.set("fiscal_issuer_id", payload.fiscal_issuer_id);
  formData.set("document_type", payload.document_type);
  formData.set("document_code", payload.document_code);
  formData.set("document_number", payload.document_number);
  formData.set("issue_date", payload.issue_date);
  if (payload.file) formData.set("file", payload.file);
  return formData;
}

export function createSaleFiscalDocument(saleId: string, payload: SaleFiscalDocumentForm) {
  return api.postFormData<ApiItemResponse<SaleFiscalDocument>>(`/api/v1/sales/${saleId}/fiscal-document`, fiscalDocumentFormData(payload), { retryTransient: false });
}
export function updateSaleFiscalDocument(saleId: string, payload: SaleFiscalDocumentForm) {
  return api.patchFormData<ApiItemResponse<SaleFiscalDocument>>(`/api/v1/sales/${saleId}/fiscal-document`, fiscalDocumentFormData(payload));
}
export function getSaleFiscalDocumentFile(saleId: string, download = false) {
  return api.getBlob(`/api/v1/sales/${saleId}/fiscal-document/file${download ? "?download=true" : ""}`);
}

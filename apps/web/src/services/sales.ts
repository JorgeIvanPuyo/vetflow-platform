import { api } from "@/lib/api";
import type { ApiItemResponse, PurchaseCreatorOption, Sale, SaleListFilters, SaleSummary, SaleWritePayload } from "@/types/api";

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

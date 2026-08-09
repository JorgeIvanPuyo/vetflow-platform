import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  Purchase,
  PurchaseListFilters,
  PurchaseSummary,
  PurchaseWritePayload,
} from "@/types/api";


export type PurchaseListResponse = {
  data: PurchaseSummary[];
  meta: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
};

export function getPurchases(filters: PurchaseListFilters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  });
  const query = params.toString();
  return api.get<PurchaseListResponse>(
    query ? `/api/v1/purchases?${query}` : "/api/v1/purchases",
  );
}

export function getPurchase(purchaseId: string) {
  return api.get<ApiItemResponse<Purchase>>(`/api/v1/purchases/${purchaseId}`);
}

export function createPurchase(payload: PurchaseWritePayload) {
  return api.post<ApiItemResponse<Purchase>>("/api/v1/purchases", payload);
}

export function updatePurchase(purchaseId: string, payload: PurchaseWritePayload) {
  return api.patch<ApiItemResponse<Purchase>>(`/api/v1/purchases/${purchaseId}`, payload);
}

export function cancelPurchase(purchaseId: string, reason: string) {
  return api.post<ApiItemResponse<Purchase>>(
    `/api/v1/purchases/${purchaseId}/cancel`,
    { reason },
    { retryTransient: false },
  );
}

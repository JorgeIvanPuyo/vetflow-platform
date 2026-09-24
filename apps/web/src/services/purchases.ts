import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  Purchase,
  PurchaseAttachment,
  PurchaseCreatorOption,
  PurchaseDashboard,
  PurchaseDashboardFilters,
  PurchaseListFilters,
  PurchaseListSummary,
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
    summary: PurchaseListSummary;
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

export function receivePurchase(purchaseId: string) {
  return api.post<ApiItemResponse<Purchase>>(
    `/api/v1/purchases/${purchaseId}/receive`,
    { confirm: true },
    { retryTransient: false },
  );
}

export function reversePurchaseReceipt(purchaseId: string, reason: string) {
  return api.post<ApiItemResponse<Purchase>>(
    `/api/v1/purchases/${purchaseId}/reverse-receipt`,
    { reason },
    { retryTransient: false },
  );
}

export function uploadPurchaseAttachment(purchaseId: string, file: File) {
  const formData = new FormData();
  formData.set("file", file);
  return api.postFormData<
    ApiItemResponse<PurchaseAttachment> & {
      meta: { attachment_status: "attached"; idempotent: boolean };
    }
  >(`/api/v1/purchases/${purchaseId}/attachment`, formData, {
    retryTransient: false,
  });
}

export function getPurchaseAttachment(purchaseId: string, download = false) {
  return api.getBlob(
    `/api/v1/purchases/${purchaseId}/attachment${download ? "?download=true" : ""}`,
  );
}

export function getPurchaseDashboard(filters: PurchaseDashboardFilters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  const query = params.toString();
  return api.get<ApiItemResponse<PurchaseDashboard>>(
    `/api/v1/purchases/dashboard${query ? `?${query}` : ""}`,
  );
}

export function getPurchaseFilterOptions() {
  return api.get<{
    data: { creators: PurchaseCreatorOption[] };
    meta: Record<string, never>;
  }>("/api/v1/purchases/filter-options");
}

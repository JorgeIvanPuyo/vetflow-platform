import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  PurchaseAttachment,
  PurchaseReturn,
  PurchaseReturnSummary,
  PurchaseReturnWritePayload,
} from "@/types/api";

export function createPurchaseReturn(purchaseId: string, payload: PurchaseReturnWritePayload) {
  return api.post<ApiItemResponse<PurchaseReturn>>(`/api/v1/purchases/${purchaseId}/returns`, payload);
}

export function getPurchaseReturn(returnId: string) {
  return api.get<ApiItemResponse<PurchaseReturn>>(`/api/v1/purchase-returns/${returnId}`);
}

export function updatePurchaseReturn(returnId: string, payload: PurchaseReturnWritePayload) {
  return api.patch<ApiItemResponse<PurchaseReturn>>(`/api/v1/purchase-returns/${returnId}`, payload);
}

export function confirmPurchaseReturn(returnId: string) {
  return api.post<ApiItemResponse<PurchaseReturn>>(
    `/api/v1/purchase-returns/${returnId}/confirm`,
    { confirm: true },
    { retryTransient: false },
  );
}

export function cancelPurchaseReturn(returnId: string, reason: string) {
  return api.post<ApiItemResponse<PurchaseReturn>>(
    `/api/v1/purchase-returns/${returnId}/cancel`,
    { reason },
    { retryTransient: false },
  );
}

export function uploadPurchaseReturnAttachment(returnId: string, file: File) {
  const formData = new FormData();
  formData.set("file", file);
  return api.postFormData<ApiItemResponse<PurchaseAttachment>>(
    `/api/v1/purchase-returns/${returnId}/attachment`,
    formData,
    { retryTransient: false },
  );
}

export function getPurchaseReturnAttachment(returnId: string, download = false) {
  return api.getBlob(`/api/v1/purchase-returns/${returnId}/attachment${download ? "?download=true" : ""}`);
}

export type PurchaseReturnListResponse = {
  data: PurchaseReturnSummary[];
  meta: { page: number; page_size: number; total: number; total_pages: number };
};

export function getPurchaseReturns(purchaseId: string) {
  return api.get<PurchaseReturnListResponse>(`/api/v1/purchase-returns?purchase_id=${purchaseId}`);
}

import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  Supplier,
  SupplierListFilters,
  SupplierSummary,
  SupplierWritePayload,
} from "@/types/api";


export type SupplierListResponse = {
  data: SupplierSummary[];
  meta: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
};

export function getSuppliers(filters: SupplierListFilters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  });
  const query = params.toString();
  return api.get<SupplierListResponse>(
    query ? `/api/v1/suppliers?${query}` : "/api/v1/suppliers",
  );
}

export function getSupplier(supplierId: string) {
  return api.get<ApiItemResponse<Supplier>>(`/api/v1/suppliers/${supplierId}`);
}

export function createSupplier(payload: SupplierWritePayload) {
  return api.post<ApiItemResponse<Supplier>>("/api/v1/suppliers", payload);
}

export function updateSupplier(
  supplierId: string,
  payload: Partial<SupplierWritePayload> & { is_active?: boolean },
) {
  return api.patch<ApiItemResponse<Supplier>>(`/api/v1/suppliers/${supplierId}`, payload);
}

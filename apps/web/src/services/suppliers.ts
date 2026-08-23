import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  CreateSupplierPayload,
  Supplier,
  UpdateSupplierPayload,
} from "@/types/api";

type SupplierFilters = {
  include_inactive?: boolean;
};

export function getSuppliers(filters: SupplierFilters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined) {
      params.set(key, String(value));
    }
  });
  const query = params.toString();
  return api.get<{ data: Supplier[]; meta: Record<string, never> }>(
    query ? `/api/v1/suppliers?${query}` : "/api/v1/suppliers",
  );
}

export function createSupplier(payload: CreateSupplierPayload) {
  return api.post<ApiItemResponse<Supplier>>("/api/v1/suppliers", payload);
}

export function updateSupplier(supplierId: string, payload: UpdateSupplierPayload) {
  return api.patch<ApiItemResponse<Supplier>>(
    `/api/v1/suppliers/${supplierId}`,
    payload,
  );
}

export function activateSupplier(supplierId: string) {
  return api.post<ApiItemResponse<Supplier>>(
    `/api/v1/suppliers/${supplierId}/activate`,
    {},
  );
}

export function deactivateSupplier(supplierId: string) {
  return api.post<ApiItemResponse<Supplier>>(
    `/api/v1/suppliers/${supplierId}/deactivate`,
    {},
  );
}

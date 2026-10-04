import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  ApiListResponse,
  CreateOwnerPayload,
  Owner,
  OwnerReceivablesActivityResponse,
  OwnerReceivablesResponse,
  UpdateOwnerPayload,
} from "@/types/api";

type GetOwnersOptions = {
  search?: string;
  phone?: string;
  page?: number;
  pageSize?: number;
  sortBy?: "created_at" | "full_name";
};

export function getOwners(options: GetOwnersOptions = {}) {
  const params = new URLSearchParams();
  if (options.sortBy) {
    params.set("sort_by", options.sortBy);
  }

  if (options.search) {
    params.set("search", options.search);
  }
  if (options.phone) {
    params.set("phone", options.phone);
  }
  if (options.page !== undefined) {
    params.set("page", String(options.page));
  }
  if (options.pageSize !== undefined) {
    params.set("page_size", String(options.pageSize));
  }

  const query = params.toString();
  return api.get<ApiListResponse<Owner>>(
    query ? `/api/v1/owners?${query}` : "/api/v1/owners",
  );
}

export function getOwner(ownerId: string) {
  return api.get<ApiItemResponse<Owner>>(`/api/v1/owners/${ownerId}`);
}

export function getOwnerReceivables(ownerId: string, { page = 1, pageSize = 20, dateFrom, dateTo, patientId }: { page?: number; pageSize?: number; dateFrom?: string; dateTo?: string; patientId?: string } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  if (patientId) params.set("patient_id", patientId);
  return api.get<OwnerReceivablesResponse>(`/api/v1/owners/${ownerId}/receivables?${params}`);
}

export function getOwnerReceivablesActivity(ownerId: string, { page = 1, pageSize = 20 }: { page?: number; pageSize?: number } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  return api.get<OwnerReceivablesActivityResponse>(`/api/v1/owners/${ownerId}/receivables/activity?${params}`);
}

export function createOwner(payload: CreateOwnerPayload) {
  return api.post<ApiItemResponse<Owner>>("/api/v1/owners", payload);
}

export function updateOwner(ownerId: string, payload: UpdateOwnerPayload) {
  return api.patch<ApiItemResponse<Owner>>(`/api/v1/owners/${ownerId}`, payload);
}

export function deleteOwner(ownerId: string) {
  return api.delete<void>(`/api/v1/owners/${ownerId}`);
}

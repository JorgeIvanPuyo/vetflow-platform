import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  ApiListResponse,
  CreateOwnerPayload,
  Owner,
  UpdateOwnerPayload,
} from "@/types/api";

type GetOwnersOptions = {
  search?: string;
  phone?: string;
  page?: number;
  pageSize?: number;
};

export function getOwners(options: GetOwnersOptions = {}) {
  const params = new URLSearchParams();

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

export function createOwner(payload: CreateOwnerPayload) {
  return api.post<ApiItemResponse<Owner>>("/api/v1/owners", payload);
}

export function updateOwner(ownerId: string, payload: UpdateOwnerPayload) {
  return api.patch<ApiItemResponse<Owner>>(`/api/v1/owners/${ownerId}`, payload);
}

export function deleteOwner(ownerId: string) {
  return api.delete<void>(`/api/v1/owners/${ownerId}`);
}

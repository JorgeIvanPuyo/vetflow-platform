import { api } from "@/lib/api";
import type {
  AdminUser,
  ApiItemResponse,
  ApiListResponse,
  InviteUserPayload,
  InviteUserResult,
  ListUsersFilters,
  TenantOption,
} from "@/types/api";

export function listUsers(filters: ListUsersFilters = {}) {
  const params = new URLSearchParams();
  if (filters.tenant_id) {
    params.set("tenant_id", filters.tenant_id);
  }
  if (typeof filters.is_active === "boolean") {
    params.set("is_active", String(filters.is_active));
  }
  if (filters.search && filters.search.trim()) {
    params.set("search", filters.search.trim());
  }

  const query = params.toString();
  return api.get<ApiListResponse<AdminUser>>(
    `/api/v1/admin/users${query ? `?${query}` : ""}`,
  );
}

export function inviteUser(payload: InviteUserPayload) {
  return api.post<ApiItemResponse<InviteUserResult>>(
    "/api/v1/admin/users/invite",
    payload,
  );
}

export function listTenants() {
  return api.get<{ data: TenantOption[]; meta: Record<string, never> }>(
    "/api/v1/admin/tenants",
  );
}

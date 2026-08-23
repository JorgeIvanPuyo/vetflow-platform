import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  ClinicService,
  CreateClinicServicePayload,
  UpdateClinicServicePayload,
} from "@/types/api";

type ServiceFilters = {
  include_inactive?: boolean;
  bookable_only?: boolean;
};

export function getServices(filters: ServiceFilters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined) {
      params.set(key, String(value));
    }
  });
  const query = params.toString();
  return api.get<{ data: ClinicService[]; meta: Record<string, never> }>(
    query ? `/api/v1/services?${query}` : "/api/v1/services",
  );
}

export function createService(payload: CreateClinicServicePayload) {
  return api.post<ApiItemResponse<ClinicService>>("/api/v1/services", payload);
}

export function updateService(
  serviceId: string,
  payload: UpdateClinicServicePayload,
) {
  return api.patch<ApiItemResponse<ClinicService>>(
    `/api/v1/services/${serviceId}`,
    payload,
  );
}

export function activateService(serviceId: string) {
  return api.post<ApiItemResponse<ClinicService>>(
    `/api/v1/services/${serviceId}/activate`,
    {},
  );
}

export function deactivateService(serviceId: string) {
  return api.post<ApiItemResponse<ClinicService>>(
    `/api/v1/services/${serviceId}/deactivate`,
    {},
  );
}

export function reorderServices(items: Array<{ id: string; sort_order: number }>) {
  return api.patch<{ data: ClinicService[]; meta: Record<string, never> }>(
    "/api/v1/services/reorder",
    { items },
  );
}

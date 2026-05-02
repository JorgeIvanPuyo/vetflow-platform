import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  ApiListResponse,
  CreateFollowUpPayload,
  FollowUp,
  FollowUpFilters,
  UpdateFollowUpPayload,
} from "@/types/api";

export function getFollowUps(filters: FollowUpFilters = {}) {
  const params = new URLSearchParams();

  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });

  const query = params.toString();
  return api.get<ApiListResponse<FollowUp>>(
    query ? `/api/v1/follow-ups?${query}` : "/api/v1/follow-ups",
  );
}

export function getFollowUp(followUpId: string) {
  return api.get<ApiItemResponse<FollowUp>>(`/api/v1/follow-ups/${followUpId}`);
}

export function createFollowUp(payload: CreateFollowUpPayload) {
  return api.post<ApiItemResponse<FollowUp>>("/api/v1/follow-ups", payload);
}

export function updateFollowUp(
  followUpId: string,
  payload: UpdateFollowUpPayload,
) {
  return api.patch<ApiItemResponse<FollowUp>>(
    `/api/v1/follow-ups/${followUpId}`,
    payload,
  );
}

export function completeFollowUp(followUpId: string) {
  return api.post<ApiItemResponse<FollowUp>>(
    `/api/v1/follow-ups/${followUpId}/complete`,
    {},
  );
}

export function cancelFollowUp(followUpId: string, notes?: string) {
  return api.post<ApiItemResponse<FollowUp>>(
    `/api/v1/follow-ups/${followUpId}/cancel`,
    notes ? { notes } : {},
  );
}

export function deleteFollowUp(followUpId: string) {
  return api.delete<void>(`/api/v1/follow-ups/${followUpId}`);
}

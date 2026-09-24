import { api } from "@/lib/api";
import type { ApiItemResponse, CurrentUser } from "@/types/api";

export function getCurrentUser(signal?: AbortSignal) {
  return api.get<ApiItemResponse<CurrentUser>>("/api/v1/auth/me", { signal, retryTransient: false });
}

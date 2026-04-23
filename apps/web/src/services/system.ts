import { api } from "@/lib/api";
import type { HealthResponse } from "@/types/api";

export function getBackendHealth() {
  return api.get<HealthResponse>("/health");
}

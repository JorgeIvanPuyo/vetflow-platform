import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  DashboardSummary,
  DashboardSummaryFilters,
} from "@/types/api";

export function getDashboardSummary(filters: DashboardSummaryFilters = {}) {
  const params = new URLSearchParams();

  Object.entries(filters).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }

    params.set(key, typeof value === "boolean" ? String(value) : value);
  });

  const query = params.toString();
  return api.get<ApiItemResponse<DashboardSummary>>(
    query ? `/api/v1/dashboard/summary?${query}` : "/api/v1/dashboard/summary",
  );
}

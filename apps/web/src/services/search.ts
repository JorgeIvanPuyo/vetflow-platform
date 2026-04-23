import { api } from "@/lib/api";
import type { SearchResponse } from "@/types/api";

export function searchGlobal(query: string) {
  const params = new URLSearchParams({ q: query });
  return api.get<SearchResponse>(`/api/v1/search?${params.toString()}`);
}

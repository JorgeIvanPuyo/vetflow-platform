import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  CatalogItem,
  CatalogType,
  CreateCatalogItemPayload,
  UpdateCatalogItemPayload,
} from "@/types/api";

type CatalogItemFilters = {
  include_inactive?: boolean;
};

export function getCatalogItems(
  catalogType: CatalogType,
  filters: CatalogItemFilters = {},
) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined) {
      params.set(key, String(value));
    }
  });
  const query = params.toString();
  const basePath = `/api/v1/clinic/catalogs/${catalogType}`;
  return api.get<{ data: CatalogItem[]; meta: Record<string, never> }>(
    query ? `${basePath}?${query}` : basePath,
  );
}

export function createCatalogItem(
  catalogType: CatalogType,
  payload: CreateCatalogItemPayload,
) {
  return api.post<ApiItemResponse<CatalogItem>>(
    `/api/v1/clinic/catalogs/${catalogType}`,
    payload,
  );
}

export function updateCatalogItem(
  catalogType: CatalogType,
  itemId: string,
  payload: UpdateCatalogItemPayload,
) {
  return api.patch<ApiItemResponse<CatalogItem>>(
    `/api/v1/clinic/catalogs/${catalogType}/${itemId}`,
    payload,
  );
}

export function activateCatalogItem(catalogType: CatalogType, itemId: string) {
  return api.post<ApiItemResponse<CatalogItem>>(
    `/api/v1/clinic/catalogs/${catalogType}/${itemId}/activate`,
    {},
  );
}

export function deactivateCatalogItem(catalogType: CatalogType, itemId: string) {
  return api.post<ApiItemResponse<CatalogItem>>(
    `/api/v1/clinic/catalogs/${catalogType}/${itemId}/deactivate`,
    {},
  );
}

export function restoreCatalogDefaults(catalogType: CatalogType) {
  return api.post<{ data: CatalogItem[]; meta: Record<string, never> }>(
    `/api/v1/clinic/catalogs/${catalogType}/restore-defaults`,
    {},
  );
}

export function reorderCatalogItems(
  catalogType: CatalogType,
  items: Array<{ id: string; sort_order: number }>,
) {
  return api.patch<{ data: CatalogItem[]; meta: Record<string, never> }>(
    `/api/v1/clinic/catalogs/${catalogType}/reorder`,
    { items },
  );
}

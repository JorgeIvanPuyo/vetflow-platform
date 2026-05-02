import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  CreateInventoryEntryPayload,
  CreateInventoryExitPayload,
  InventoryItem,
  InventoryListFilters,
  InventoryMovement,
  InventoryMovementsFilters,
  InventorySummary,
  CreateInventoryItemPayload,
  UpdateInventoryItemPayload,
} from "@/types/api";

type InventoryListResponse = {
  data: InventoryItem[];
  meta: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
};

type InventoryMovementListResponse = {
  data: InventoryMovement[];
  meta: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
};

export function getInventorySummary() {
  return api.get<ApiItemResponse<InventorySummary>>("/api/v1/inventory/summary");
}

export function getInventoryItems(filters: InventoryListFilters = {}) {
  const params = new URLSearchParams();

  Object.entries(filters).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }

    params.set(key, String(value));
  });

  const query = params.toString();
  return api.get<InventoryListResponse>(
    query ? `/api/v1/inventory/items?${query}` : "/api/v1/inventory/items",
  );
}

export function getInventoryItem(itemId: string) {
  return api.get<ApiItemResponse<InventoryItem>>(`/api/v1/inventory/items/${itemId}`);
}

export function createInventoryItem(payload: CreateInventoryItemPayload) {
  return api.post<ApiItemResponse<InventoryItem>>("/api/v1/inventory/items", payload);
}

export function updateInventoryItem(
  itemId: string,
  payload: UpdateInventoryItemPayload,
) {
  return api.patch<ApiItemResponse<InventoryItem>>(
    `/api/v1/inventory/items/${itemId}`,
    payload,
  );
}

export function deleteInventoryItem(itemId: string) {
  return api.delete<void>(`/api/v1/inventory/items/${itemId}`);
}

export function createInventoryEntry(
  itemId: string,
  payload: CreateInventoryEntryPayload,
) {
  return api.post<ApiItemResponse<InventoryMovement>>(
    `/api/v1/inventory/items/${itemId}/movements/entry`,
    payload,
  );
}

export function createInventoryExit(
  itemId: string,
  payload: CreateInventoryExitPayload,
) {
  return api.post<ApiItemResponse<InventoryMovement>>(
    `/api/v1/inventory/items/${itemId}/movements/exit`,
    payload,
  );
}

export function getInventoryMovements(
  itemId: string,
  filters: InventoryMovementsFilters = {},
) {
  const params = new URLSearchParams();

  Object.entries(filters).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }

    params.set(key, String(value));
  });

  const query = params.toString();

  return api.get<InventoryMovementListResponse>(
    query
      ? `/api/v1/inventory/items/${itemId}/movements?${query}`
      : `/api/v1/inventory/items/${itemId}/movements`,
  );
}

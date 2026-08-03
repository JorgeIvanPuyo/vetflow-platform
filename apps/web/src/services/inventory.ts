import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  CreateInventoryEntryPayload,
  CreateInventoryExitPayload,
  InventoryBulkOperation,
  InventoryBulkOperationListItem,
  InventoryBulkOperationPreviewPayload,
  InventoryExportPayload,
  InventoryImport,
  InventoryImportConfirmPayload,
  InventoryImportListItem,
  InventoryImportMode,
  InventoryFilterOptions,
  InventoryItem,
  InventoryMovementDetail,
  InventoryListFilters,
  InventoryMovement,
  InventoryMovementsFilters,
  InventorySummary,
  CreateInventoryItemPayload,
  ReverseInventoryMovementPayload,
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

type InventoryImportListResponse = {
  data: InventoryImportListItem[];
  meta: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
};

type InventoryBulkOperationListResponse = {
  data: InventoryBulkOperationListItem[];
  meta: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
};

type InventoryBulkOperationResponse = ApiItemResponse<InventoryBulkOperation> & {
  meta: {
    page?: number;
    page_size?: number;
    total?: number;
    total_pages?: number;
  };
};

export function getInventorySummary() {
  return api.get<ApiItemResponse<InventorySummary>>("/api/v1/inventory/summary");
}

export function getInventoryFilterOptions() {
  return api.get<ApiItemResponse<InventoryFilterOptions>>("/api/v1/inventory/filter-options");
}

export function getInventoryItems(filters: InventoryListFilters = {}) {
  const params = new URLSearchParams();

  Object.entries(filters).forEach(([key, value]) => {
    if (value === undefined || value === null) {
      return;
    }

    params.set(key, String(value));
  });

  const query = params.toString();
  return api.get<InventoryListResponse>(
    query ? `/api/v1/inventory/items?${query}` : "/api/v1/inventory/items",
  );
}

export function searchInventoryMedications(q: string) {
  return getInventoryItems({
    q: q.trim() || undefined,
    category: "medication",
    status: "active",
    page: 1,
    page_size: 10,
    sort_by: "name",
    sort_order: "asc",
  });
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
    if (value === undefined || value === null) {
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

export function getInventoryMovementList(filters: InventoryMovementsFilters = {}) {
  const params = new URLSearchParams();

  Object.entries(filters).forEach(([key, value]) => {
    if (value === undefined || value === null) {
      return;
    }

    params.set(key, String(value));
  });

  const query = params.toString();
  return api.get<InventoryMovementListResponse>(
    query ? `/api/v1/inventory/movements?${query}` : "/api/v1/inventory/movements",
  );
}

export function getInventoryMovement(movementId: string) {
  return api.get<ApiItemResponse<InventoryMovementDetail>>(
    `/api/v1/inventory/movements/${movementId}`,
  );
}

export function reverseInventoryMovement(
  movementId: string,
  payload: ReverseInventoryMovementPayload,
) {
  return api.post<ApiItemResponse<InventoryMovement>>(
    `/api/v1/inventory/movements/${movementId}/reverse`,
    payload,
  );
}

export function downloadInventoryImportTemplate() {
  return api.getBlob("/api/v1/inventory/import/template");
}

export function previewInventoryImport(file: File, mode: InventoryImportMode) {
  const formData = new FormData();
  formData.set("mode", mode);
  formData.set("file", file);

  return api.postFormData<ApiItemResponse<InventoryImport>>(
    "/api/v1/inventory/import/preview",
    formData,
  );
}

export function getInventoryImport(importId: string) {
  return api.get<ApiItemResponse<InventoryImport>>(`/api/v1/inventory/import/${importId}`);
}

export function confirmInventoryImport(
  importId: string,
  payload: InventoryImportConfirmPayload,
) {
  return api.post<ApiItemResponse<InventoryImport>>(
    `/api/v1/inventory/import/${importId}/confirm`,
    payload,
    { retryTransient: false },
  );
}

export function getInventoryImportResult(importId: string) {
  return api.get<ApiItemResponse<InventoryImport>>(
    `/api/v1/inventory/import/${importId}/result`,
  );
}

export function getInventoryImports(page = 1, pageSize = 10) {
  return api.get<InventoryImportListResponse>(
    `/api/v1/inventory/imports?page=${page}&page_size=${pageSize}`,
  );
}

export function exportInventory(payload: InventoryExportPayload) {
  return api.postBlob("/api/v1/inventory/export", payload);
}

export function previewInventoryBulkOperation(payload: InventoryBulkOperationPreviewPayload) {
  return api.post<InventoryBulkOperationResponse>(
    "/api/v1/inventory/bulk-operations/preview",
    payload,
  );
}

export function confirmInventoryBulkOperation(operationId: string) {
  return api.post<InventoryBulkOperationResponse>(
    `/api/v1/inventory/bulk-operations/${operationId}/confirm`,
    { confirm: true },
    { retryTransient: false },
  );
}

export function reverseInventoryBulkOperation(operationId: string, reason: string) {
  return api.post<InventoryBulkOperationResponse>(
    `/api/v1/inventory/bulk-operations/${operationId}/reverse`,
    { reason },
    { retryTransient: false },
  );
}

export function getInventoryBulkOperation(operationId: string, page = 1, pageSize = 100) {
  return api.get<InventoryBulkOperationResponse>(
    `/api/v1/inventory/bulk-operations/${operationId}?page=${page}&page_size=${pageSize}`,
  );
}

export function getInventoryBulkOperations(page = 1, pageSize = 10) {
  return api.get<InventoryBulkOperationListResponse>(
    `/api/v1/inventory/bulk-operations?page=${page}&page_size=${pageSize}`,
  );
}

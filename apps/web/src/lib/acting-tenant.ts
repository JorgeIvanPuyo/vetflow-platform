import { setActingTenantId } from "@/lib/api";

const STORAGE_KEY = "vetflow:acting-tenant-id";

export function getStoredActingTenantId(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(STORAGE_KEY);
}

/** Applies whatever tenant override is in storage to every API request. Call this
 * synchronously during the first render of the authenticated app, before any
 * data-fetching effect can fire. */
export function applyStoredActingTenant(): void {
  setActingTenantId(getStoredActingTenantId());
}

export function setStoredActingTenantId(tenantId: string | null): void {
  if (typeof window === "undefined") {
    return;
  }
  if (tenantId) {
    window.localStorage.setItem(STORAGE_KEY, tenantId);
  } else {
    window.localStorage.removeItem(STORAGE_KEY);
  }
  setActingTenantId(tenantId);
}

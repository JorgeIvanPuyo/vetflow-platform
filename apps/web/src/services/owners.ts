import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  ApiListResponse,
  CreateOwnerPayload,
  Owner,
} from "@/types/api";

export function getOwners() {
  return api.get<ApiListResponse<Owner>>("/api/v1/owners");
}

export function getOwner(ownerId: string) {
  return api.get<ApiItemResponse<Owner>>(`/api/v1/owners/${ownerId}`);
}

export function createOwner(payload: CreateOwnerPayload) {
  return api.post<ApiItemResponse<Owner>>("/api/v1/owners", payload);
}

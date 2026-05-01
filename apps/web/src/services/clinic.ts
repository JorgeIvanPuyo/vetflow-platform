import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  ClinicProfile,
  ClinicTeamMember,
  UpdateClinicProfilePayload,
} from "@/types/api";

export function getClinicProfile() {
  return api.get<ApiItemResponse<ClinicProfile>>("/api/v1/clinic/profile");
}

export function updateClinicProfile(payload: UpdateClinicProfilePayload) {
  return api.patch<ApiItemResponse<ClinicProfile>>(
    "/api/v1/clinic/profile",
    payload,
  );
}

export function getClinicTeam() {
  return api.get<{ data: ClinicTeamMember[]; meta: Record<string, never> }>(
    "/api/v1/clinic/team",
  );
}

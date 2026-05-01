import { api } from "@/lib/api";
import type {
  ApiItemResponse,
  ApiListResponse,
  Appointment,
  AppointmentFilters,
  CreateAppointmentPayload,
  UpdateAppointmentPayload,
} from "@/types/api";

export function getAppointments(filters: AppointmentFilters = {}) {
  const params = new URLSearchParams();

  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });

  const query = params.toString();
  return api.get<ApiListResponse<Appointment>>(
    query ? `/api/v1/appointments?${query}` : "/api/v1/appointments",
  );
}

export function getAppointment(appointmentId: string) {
  return api.get<ApiItemResponse<Appointment>>(
    `/api/v1/appointments/${appointmentId}`,
  );
}

export function createAppointment(payload: CreateAppointmentPayload) {
  return api.post<ApiItemResponse<Appointment>>("/api/v1/appointments", payload);
}

export function updateAppointment(
  appointmentId: string,
  payload: UpdateAppointmentPayload,
) {
  return api.patch<ApiItemResponse<Appointment>>(
    `/api/v1/appointments/${appointmentId}`,
    payload,
  );
}

export function deleteAppointment(appointmentId: string) {
  return api.delete<void>(`/api/v1/appointments/${appointmentId}`);
}

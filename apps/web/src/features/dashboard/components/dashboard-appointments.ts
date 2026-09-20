import { getDayRange, toDateInputValue } from "@/features/agenda/components/agenda-helpers";
import type { AppointmentFilters, DashboardAppointmentItem } from "@/types/api";

export function buildDashboardAppointmentFilters(
  assignedUserId: string,
  now = new Date(),
): AppointmentFilters {
  return {
    date_from: getDayRange(toDateInputValue(now)).date_from,
    status: "scheduled",
    ...(assignedUserId && assignedUserId !== "all" ? { assigned_user_id: assignedUserId } : {}),
  };
}

export function selectDashboardAppointments(
  appointments: DashboardAppointmentItem[],
  now = new Date(),
) {
  const today = toDateInputValue(now);
  const pending = appointments
    .filter((appointment) => appointment.status === "scheduled")
    .sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime());

  // Use the same local calendar day as Agenda, not a rolling 24-hour window.
  return {
    today: pending.filter((appointment) => toDateInputValue(new Date(appointment.start_at)) === today).slice(0, 4),
    next: pending.find((appointment) => toDateInputValue(new Date(appointment.start_at)) > today),
  };
}

import type { Appointment, AppointmentStatus, AppointmentType } from "@/types/api";

export const appointmentTypeOptions: Array<{
  value: AppointmentType;
  label: string;
}> = [
  { value: "consultation", label: "Consulta" },
  { value: "follow_up", label: "Control" },
  { value: "vaccine", label: "Vacuna" },
  { value: "deworming", label: "Desparasitación" },
  { value: "exam", label: "Examen" },
  { value: "other", label: "Otro" },
];

export const appointmentStatusOptions: Array<{
  value: AppointmentStatus;
  label: string;
}> = [
  { value: "scheduled", label: "Programado" },
  { value: "completed", label: "Completado" },
  { value: "cancelled", label: "Cancelado" },
  { value: "no_show", label: "No asistió" },
];

export type AppointmentFormState = {
  title: string;
  patient_id: string;
  owner_id: string;
  assigned_user_id: string;
  appointment_type: AppointmentType;
  status: AppointmentStatus;
  date: string;
  start_time: string;
  end_time: string;
  reason: string;
  notes: string;
};

export function getInitialAppointmentFormState(
  date = new Date(),
): AppointmentFormState {
  const nextStart = new Date(date);
  nextStart.setMinutes(0, 0, 0);
  nextStart.setHours(nextStart.getHours() + 1);

  const nextEnd = new Date(nextStart);
  nextEnd.setMinutes(nextEnd.getMinutes() + 30);

  return {
    title: "",
    patient_id: "",
    owner_id: "",
    assigned_user_id: "",
    appointment_type: "consultation",
    status: "scheduled",
    date: toDateInputValue(nextStart),
    start_time: toTimeInputValue(nextStart),
    end_time: toTimeInputValue(nextEnd),
    reason: "",
    notes: "",
  };
}

export function getAppointmentTypeLabel(type: AppointmentType) {
  return appointmentTypeOptions.find((option) => option.value === type)?.label ?? "Otro";
}

export function getAppointmentStatusLabel(status: AppointmentStatus) {
  return (
    appointmentStatusOptions.find((option) => option.value === status)?.label ??
    "Programado"
  );
}

export function getStatusBadgeClass(status: AppointmentStatus) {
  if (status === "completed") {
    return "badge badge--success";
  }
  if (status === "cancelled") {
    return "badge badge--danger";
  }
  if (status === "no_show") {
    return "badge badge--warning";
  }
  return "badge badge--blue";
}

export function getTypeBadgeClass(type: AppointmentType) {
  if (type === "vaccine" || type === "deworming") {
    return "badge badge--success";
  }
  if (type === "exam") {
    return "badge badge--blue";
  }
  if (type === "other") {
    return "badge badge--warning";
  }
  return "badge";
}

export function toDateInputValue(date: Date) {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function toTimeInputValue(date: Date) {
  return `${date.getHours()}`.padStart(2, "0") + `:${date.getMinutes()}`.padStart(2, "0");
}

export function getDayRange(dateValue: string) {
  const date = parseDateInput(dateValue);
  const start = new Date(date);
  start.setHours(0, 0, 0, 0);

  const end = new Date(date);
  end.setHours(23, 59, 59, 999);

  return {
    date_from: start.toISOString(),
    date_to: end.toISOString(),
  };
}

export function parseDateInput(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function buildAppointmentDateTime(date: string, time: string) {
  const [year, month, day] = date.split("-").map(Number);
  const [hours, minutes] = time.split(":").map(Number);
  return new Date(year, month - 1, day, hours, minutes, 0, 0);
}

export function formatDateLabel(value: string) {
  return new Intl.DateTimeFormat("es", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(parseDateInput(value));
}

export function formatAppointmentDate(value: string) {
  return new Intl.DateTimeFormat("es", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(value));
}

export function formatAppointmentTime(value: string) {
  return new Intl.DateTimeFormat("es", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function formatAppointmentTimeRange(appointment: Appointment) {
  return `${formatAppointmentTime(appointment.start_at)} - ${formatAppointmentTime(appointment.end_at)}`;
}

export function getAppointmentUserName(
  name?: string | null,
  email?: string | null,
) {
  return name?.trim() || email?.trim() || null;
}

export function appointmentToFormState(appointment: Appointment): AppointmentFormState {
  const startAt = new Date(appointment.start_at);
  const endAt = new Date(appointment.end_at);

  return {
    title: appointment.title,
    patient_id: appointment.patient_id ?? "",
    owner_id: appointment.owner_id ?? "",
    assigned_user_id: appointment.assigned_user_id ?? "",
    appointment_type: appointment.appointment_type,
    status: appointment.status,
    date: toDateInputValue(startAt),
    start_time: toTimeInputValue(startAt),
    end_time: toTimeInputValue(endAt),
    reason: appointment.reason ?? "",
    notes: appointment.notes ?? "",
  };
}

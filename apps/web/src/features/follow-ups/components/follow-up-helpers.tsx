import { AlarmClockCheck, ClipboardCheck, FlaskConical, Syringe } from "lucide-react";
import type { ReactNode } from "react";

import type {
  ClinicTeamMember,
  CreateFollowUpPayload,
  FollowUp,
  FollowUpStatus,
  FollowUpType,
  Patient,
  UpdateFollowUpPayload,
} from "@/types/api";

export const followUpTypeOptions: Array<{
  value: FollowUpType;
  label: string;
  defaultTitle: string;
}> = [
  {
    value: "consultation_control",
    label: "Control",
    defaultTitle: "Próximo control",
  },
  { value: "vaccine", label: "Vacuna", defaultTitle: "Próxima vacuna" },
  {
    value: "deworming",
    label: "Desparasitación",
    defaultTitle: "Próxima desparasitación",
  },
  {
    value: "exam_review",
    label: "Revisión de examen",
    defaultTitle: "Revisión de examen",
  },
  { value: "other", label: "Otro", defaultTitle: "Seguimiento clínico" },
];

export const followUpStatusOptions: Array<{
  value: FollowUpStatus;
  label: string;
}> = [
  { value: "pending", label: "Pendiente" },
  { value: "scheduled", label: "Programado" },
  { value: "completed", label: "Completado" },
  { value: "cancelled", label: "Cancelado" },
  { value: "overdue", label: "Vencido" },
];

export const followUpDurationOptions = [15, 30, 45, 60];

export type FollowUpFormState = {
  patient_id: string;
  owner_id: string;
  assigned_user_id: string;
  follow_up_type: FollowUpType;
  title: string;
  date: string;
  time: string;
  description: string;
  notes: string;
  create_appointment: boolean;
  appointment_duration_minutes: number;
  status: FollowUpStatus;
};

export function getInitialFollowUpFormState(date = new Date()): FollowUpFormState {
  const nextDueAt = new Date(date);
  nextDueAt.setMinutes(0, 0, 0);
  nextDueAt.setHours(nextDueAt.getHours() + 1);

  return {
    patient_id: "",
    owner_id: "",
    assigned_user_id: "",
    follow_up_type: "consultation_control",
    title: getDefaultFollowUpTitle("consultation_control"),
    date: toDateInputValue(nextDueAt),
    time: toTimeInputValue(nextDueAt),
    description: "",
    notes: "",
    create_appointment: true,
    appointment_duration_minutes: 30,
    status: "pending",
  };
}

export function getDefaultFollowUpTitle(type: FollowUpType) {
  return (
    followUpTypeOptions.find((option) => option.value === type)?.defaultTitle ??
    "Seguimiento clínico"
  );
}

export function getFollowUpTypeLabel(type: FollowUpType) {
  return followUpTypeOptions.find((option) => option.value === type)?.label ?? "Otro";
}

export function getFollowUpStatusLabel(status: FollowUpStatus) {
  return (
    followUpStatusOptions.find((option) => option.value === status)?.label ?? "Pendiente"
  );
}

export function getFollowUpStatusBadgeClass(status: FollowUpStatus) {
  if (status === "completed") {
    return "badge badge--success";
  }
  if (status === "cancelled") {
    return "badge badge--danger";
  }
  if (status === "overdue") {
    return "badge badge--warning";
  }
  if (status === "scheduled") {
    return "badge badge--blue";
  }
  return "badge";
}

export function getFollowUpTypeBadgeClass(type: FollowUpType) {
  if (type === "vaccine" || type === "deworming") {
    return "badge badge--success";
  }
  if (type === "exam_review") {
    return "badge badge--blue";
  }
  if (type === "other") {
    return "badge badge--warning";
  }
  return "badge";
}

export function getFollowUpIcon(type: FollowUpType): ReactNode {
  if (type === "vaccine" || type === "deworming") {
    return <Syringe size={18} />;
  }
  if (type === "exam_review") {
    return <FlaskConical size={18} />;
  }
  if (type === "other") {
    return <ClipboardCheck size={18} />;
  }
  return <AlarmClockCheck size={18} />;
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

export function parseDateInput(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function buildFollowUpDateTime(date: string, time: string) {
  const [year, month, day] = date.split("-").map(Number);
  const [hours, minutes] = time.split(":").map(Number);
  return new Date(year, month - 1, day, hours, minutes, 0, 0);
}

export function buildFollowUpPayload(formState: FollowUpFormState): CreateFollowUpPayload {
  return {
    patient_id: formState.patient_id,
    owner_id: formState.owner_id || null,
    assigned_user_id: formState.assigned_user_id || null,
    title: formState.title.trim(),
    description: formState.description.trim() || null,
    follow_up_type: formState.follow_up_type,
    due_at: buildFollowUpDateTime(formState.date, formState.time).toISOString(),
    notes: formState.notes.trim() || null,
    create_appointment: formState.create_appointment,
    appointment_duration_minutes: formState.create_appointment
      ? formState.appointment_duration_minutes
      : undefined,
  };
}

export function buildFollowUpUpdatePayload(
  formState: FollowUpFormState,
): UpdateFollowUpPayload {
  return {
    assigned_user_id: formState.assigned_user_id || null,
    title: formState.title.trim(),
    description: formState.description.trim() || null,
    follow_up_type: formState.follow_up_type,
    due_at: buildFollowUpDateTime(formState.date, formState.time).toISOString(),
    notes: formState.notes.trim() || null,
    status: formState.status,
  };
}

export function validateFollowUpForm(
  formState: FollowUpFormState,
  options: {
    teamRequired?: boolean;
  } = {},
) {
  if (!formState.patient_id) {
    return "Selecciona un paciente para programar el seguimiento.";
  }
  if (!formState.title.trim()) {
    return "Escribe un título para el seguimiento.";
  }
  if (!formState.date || !formState.time) {
    return "Selecciona la fecha y hora del seguimiento.";
  }
  if (options.teamRequired && !formState.assigned_user_id) {
    return "Selecciona un veterinario asignado.";
  }
  if (formState.create_appointment && !followUpDurationOptions.includes(formState.appointment_duration_minutes)) {
    return "Selecciona una duración válida para el turno asociado.";
  }
  return null;
}

export function followUpToFormState(followUp: FollowUp): FollowUpFormState {
  const dueAt = new Date(followUp.due_at);

  return {
    patient_id: followUp.patient_id,
    owner_id: followUp.owner_id ?? "",
    assigned_user_id: followUp.assigned_user_id ?? "",
    follow_up_type: followUp.follow_up_type,
    title: followUp.title,
    date: toDateInputValue(dueAt),
    time: toTimeInputValue(dueAt),
    description: followUp.description ?? "",
    notes: followUp.notes ?? "",
    create_appointment: Boolean(followUp.appointment_id),
    appointment_duration_minutes: 30,
    status: followUp.status,
  };
}

export function getFollowUpUserName(
  name?: string | null,
  email?: string | null,
) {
  return name?.trim() || email?.trim() || null;
}

export function getDefaultAssignedUserId(
  team: ClinicTeamMember[],
  email?: string | null,
) {
  if (!email) {
    return "";
  }

  const normalizedEmail = email.trim().toLowerCase();
  return (
    team.find((member) => member.email.trim().toLowerCase() === normalizedEmail)?.id ?? ""
  );
}

export function getPatientOwnerId(
  patients: Patient[],
  patientId: string,
  fallbackOwnerId = "",
) {
  return patients.find((patient) => patient.id === patientId)?.owner_id ?? fallbackOwnerId;
}

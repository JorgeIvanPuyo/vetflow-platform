import {
  AlarmClockCheck,
  CalendarDays,
  ClipboardCheck,
  FileText,
  ShieldAlert,
  Syringe,
} from "lucide-react";
import type { ReactNode } from "react";

import {
  getAppointmentStatusLabel,
  getAppointmentTypeLabel,
  getStatusBadgeClass,
} from "@/features/agenda/components/agenda-helpers";
import {
  getFollowUpStatusBadgeClass,
  getFollowUpStatusLabel,
  getFollowUpTypeBadgeClass,
  getFollowUpTypeLabel,
} from "@/features/follow-ups/components/follow-up-helpers";
import type {
  AppointmentStatus,
  AppointmentType,
  ConsultationStatus,
  DashboardSummaryFilters,
  FollowUpStatus,
  FollowUpType,
  PreventiveCareType,
} from "@/types/api";

export type DashboardQuickPeriod = "today" | "next_7_days" | "last_7_days";

export const dashboardQuickPeriods: Array<{
  value: DashboardQuickPeriod;
  label: string;
}> = [
  { value: "today", label: "Hoy" },
  { value: "next_7_days", label: "Próximos 7 días" },
  { value: "last_7_days", label: "Últimos 7 días" },
];

export function buildDashboardSummaryFilters(
  period: DashboardQuickPeriod,
  assignedUserId: string,
): DashboardSummaryFilters {
  const filters: DashboardSummaryFilters = {};

  if (assignedUserId && assignedUserId !== "all") {
    filters.assigned_user_id = assignedUserId;
  }

  if (period === "today") {
    return filters;
  }

  const now = new Date();
  const rangeStart = new Date(now);
  const rangeEnd = new Date(now);

  if (period === "next_7_days") {
    rangeStart.setHours(0, 0, 0, 0);
    rangeEnd.setDate(rangeEnd.getDate() + 6);
    rangeEnd.setHours(23, 59, 59, 999);
  }

  if (period === "last_7_days") {
    rangeStart.setDate(rangeStart.getDate() - 6);
    rangeStart.setHours(0, 0, 0, 0);
    rangeEnd.setHours(23, 59, 59, 999);
  }

  return {
    ...filters,
    date_from: rangeStart.toISOString(),
    date_to: rangeEnd.toISOString(),
  };
}

export function formatDashboardDateTime(value: string) {
  return new Intl.DateTimeFormat("es", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function formatDashboardDate(value: string) {
  return new Intl.DateTimeFormat("es", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

export function formatDashboardTime(value: string) {
  return new Intl.DateTimeFormat("es", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function getDashboardUserLabel(
  name?: string | null,
  email?: string | null,
) {
  return name?.trim() || email?.trim() || null;
}

export function getDashboardAppointmentTypeLabel(type: AppointmentType) {
  return getAppointmentTypeLabel(type);
}

export function getDashboardAppointmentStatusLabel(status: AppointmentStatus) {
  return getAppointmentStatusLabel(status);
}

export function getDashboardAppointmentStatusClass(status: AppointmentStatus) {
  return getStatusBadgeClass(status);
}

export function getDashboardFollowUpStatusLabel(status: FollowUpStatus) {
  return getFollowUpStatusLabel(status);
}

export function getDashboardFollowUpStatusClass(status: FollowUpStatus) {
  return getFollowUpStatusBadgeClass(status);
}

export function getDashboardFollowUpTypeLabel(type: FollowUpType) {
  return getFollowUpTypeLabel(type);
}

export function getDashboardFollowUpTypeClass(type: FollowUpType) {
  return getFollowUpTypeBadgeClass(type);
}

export function getConsultationStatusLabel(status: ConsultationStatus) {
  return status === "completed" ? "Completada" : "Borrador";
}

export function getConsultationStatusClass(status: ConsultationStatus) {
  return status === "completed" ? "badge badge--success" : "badge badge--warning";
}

export function getPreventiveCareLabel(type: PreventiveCareType) {
  if (type === "vaccine") {
    return "Vacuna";
  }
  if (type === "deworming") {
    return "Desparasitación";
  }
  return "Preventivo";
}

export function getPreventiveCareBadgeClass(type: PreventiveCareType) {
  if (type === "other") {
    return "badge badge--blue";
  }
  return "badge badge--success";
}

export function getDashboardFileTypeLabel(type: string) {
  if (type === "laboratory") {
    return "Laboratorio";
  }
  if (type === "radiography") {
    return "Radiografía";
  }
  if (type === "ultrasound") {
    return "Ecografía";
  }
  if (type === "clinical_photo") {
    return "Foto clínica";
  }
  if (type === "document") {
    return "Documento";
  }
  return "Archivo";
}

export function getDashboardCardLabel(
  period: DashboardQuickPeriod,
  defaultLabel: string,
  periodLabel = "del período",
) {
  return period === "today" ? defaultLabel : periodLabel;
}

export function getDashboardCardHelper(
  period: DashboardQuickPeriod,
  todayHelper: string,
  periodHelper: string,
) {
  return period === "today" ? todayHelper : periodHelper;
}

export function getKpiIcon(name: string): ReactNode {
  if (name === "appointments") {
    return <CalendarDays size={22} />;
  }
  if (name === "upcoming_follow_ups") {
    return <AlarmClockCheck size={22} />;
  }
  if (name === "overdue_follow_ups") {
    return <ShieldAlert size={22} />;
  }
  if (name === "consultations") {
    return <ClipboardCheck size={22} />;
  }
  if (name === "preventive_care") {
    return <Syringe size={22} />;
  }
  return <FileText size={22} />;
}

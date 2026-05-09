"use client";

import {
  ArrowRight,
  RefreshCw,
  Stethoscope,
} from "lucide-react";
import Link from "next/link";
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  buildDashboardSummaryFilters,
  dashboardQuickPeriods,
  DashboardQuickPeriod,
  formatDashboardDate,
  formatDashboardDateTime,
  formatDashboardTime,
  getConsultationStatusClass,
  getConsultationStatusLabel,
  getDashboardAppointmentStatusClass,
  getDashboardAppointmentStatusLabel,
  getDashboardAppointmentTypeLabel,
  getDashboardCardHelper,
  getDashboardCardLabel,
  getDashboardFollowUpStatusClass,
  getDashboardFollowUpStatusLabel,
  getDashboardFollowUpTypeClass,
  getDashboardFollowUpTypeLabel,
  getDashboardFileTypeLabel,
  getKpiIcon,
  getPreventiveCareBadgeClass,
  getPreventiveCareLabel,
} from "@/features/dashboard/components/dashboard-helpers";
import { getApiErrorMessage } from "@/lib/api";
import { getClinicTeam } from "@/services/clinic";
import { getDashboardSummary } from "@/services/dashboard";
import type {
  ClinicTeamMember,
  DashboardAppointmentItem,
  DashboardConsultationItem,
  DashboardFileItem,
  DashboardFollowUpItem,
  DashboardPreventiveCareItem,
  DashboardSummary,
  DashboardVeterinarianActivityItem,
} from "@/types/api";

type DashboardState = {
  isLoading: boolean;
  isRefreshing: boolean;
  summary: DashboardSummary | null;
  team: ClinicTeamMember[];
  errorMessage: string | null;
};

type DashboardKpiTone = "blue" | "success" | "warning" | "danger";

const initialState: DashboardState = {
  isLoading: true,
  isRefreshing: false,
  summary: null,
  team: [],
  errorMessage: null,
};

export function DashboardHome() {
  const [state, setState] = useState<DashboardState>(initialState);
  const [periodFilter, setPeriodFilter] = useState<DashboardQuickPeriod>("today");
  const [assignedUserId, setAssignedUserId] = useState("all");
  const hasLoadedRef = useRef(false);

  const requestFilters = useMemo(
    () => buildDashboardSummaryFilters(periodFilter, assignedUserId),
    [assignedUserId, periodFilter],
  );

  const criticalFollowUps = useMemo(() => {
    const overdue = state.summary?.overdue_follow_ups ?? [];
    const upcoming = state.summary?.upcoming_follow_ups ?? [];

    return [...overdue.slice(0, 3), ...upcoming.slice(0, Math.max(0, 5 - overdue.length))];
  }, [state.summary]);

  const loadDashboard = useCallback(async () => {
    const isFirstLoad = !hasLoadedRef.current;

    setState((current) => ({
      ...current,
      isLoading: isFirstLoad,
      isRefreshing: !isFirstLoad,
      errorMessage: null,
    }));

    try {
      const [summaryResult, teamResult] = await Promise.allSettled([
        getDashboardSummary(requestFilters),
        getClinicTeam(),
      ]);

      if (summaryResult.status === "rejected") {
        throw summaryResult.reason;
      }

      hasLoadedRef.current = true;
      setState((current) => ({
        ...current,
        isLoading: false,
        isRefreshing: false,
        summary: summaryResult.value.data,
        team:
          teamResult.status === "fulfilled" ? teamResult.value.data : current.team,
        errorMessage: null,
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        isLoading: false,
        isRefreshing: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }, [requestFilters]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const showVetFilter = state.team.length > 0;
  const summary = state.summary;

  return (
    <div className="page-stack dashboard-page">
      <DashboardHeader
        assignedUserId={assignedUserId}
        isLoading={state.isLoading}
        isRefreshing={state.isRefreshing}
        onAssignedUserChange={setAssignedUserId}
        onPeriodChange={setPeriodFilter}
        onRefresh={() => void loadDashboard()}
        periodFilter={periodFilter}
        showVetFilter={showVetFilter}
        team={state.team}
      />

      {state.isLoading && !summary ? (
        <section className="panel empty-state">
          <strong>Cargando resumen de la clínica...</strong>
          <span>Estamos trayendo turnos, seguimientos y actividad reciente.</span>
        </section>
      ) : null}

      {state.errorMessage && !summary ? (
        <section className="error-state">
          <strong>No pudimos cargar el dashboard.</strong> {state.errorMessage}
          <button className="secondary-button secondary-button--full" type="button" onClick={() => void loadDashboard()}>
            Reintentar
          </button>
        </section>
      ) : null}

      {summary ? (
        <>
          {state.errorMessage ? (
            <section className="error-state">
              <strong>Mostrando la última información disponible.</strong> {state.errorMessage}
            </section>
          ) : null}

          <div className="dashboard-priority-grid">
            <DashboardSection
              className="dashboard-section--appointments"
              title={getDashboardCardLabel(periodFilter, "Turnos de hoy", "Turnos del período")}
              subtitle="Primeros turnos registrados en agenda"
              actionHref="/agenda"
              actionLabel="Ver agenda"
            >
              {summary.appointments_today.length > 0 ? (
                <div className="dashboard-list">
                  {summary.appointments_today.slice(0, 5).map((appointment) => (
                    <DashboardAppointmentRow key={appointment.id} appointment={appointment} />
                  ))}
                </div>
              ) : (
                <DashboardEmptyMessage>
                  {periodFilter === "today"
                    ? "No hay turnos programados para hoy."
                    : "No hay turnos registrados para este período."}
                </DashboardEmptyMessage>
              )}
            </DashboardSection>

            <DashboardSection
              className="dashboard-section--critical"
              title="Seguimientos críticos"
              subtitle="Vencidos primero, luego próximos"
              actionHref="/follow-ups"
              actionLabel="Ver seguimientos"
            >
              {criticalFollowUps.length > 0 ? (
                <div className="dashboard-list">
                  {criticalFollowUps.map((followUp) => (
                    <DashboardFollowUpRow key={`${followUp.id}-${followUp.status}`} followUp={followUp} />
                  ))}
                </div>
              ) : (
                <DashboardEmptyMessage>
                  No hay seguimientos pendientes.
                </DashboardEmptyMessage>
              )}
            </DashboardSection>

            <DashboardSection
              className="dashboard-section--consultations"
              title="Consultas recientes"
              subtitle="Últimos registros clínicos"
            >
              {summary.recent_consultations.length > 0 ? (
                <div className="dashboard-list">
                  {summary.recent_consultations.slice(0, 5).map((consultation) => (
                    <DashboardConsultationRow key={consultation.id} consultation={consultation} />
                  ))}
                </div>
              ) : (
                <DashboardEmptyMessage>
                  No hay consultas recientes.
                </DashboardEmptyMessage>
              )}
            </DashboardSection>

            <DashboardSection
              className="dashboard-section--preventive"
              title="Próximas vacunas y desparasitaciones"
              subtitle="Preventivos con vencimiento cercano"
            >
              {summary.upcoming_preventive_care.length > 0 ? (
                <div className="dashboard-list">
                  {summary.upcoming_preventive_care.slice(0, 5).map((record) => (
                    <DashboardPreventiveCareRow key={record.id} record={record} />
                  ))}
                </div>
              ) : (
                <DashboardEmptyMessage>
                  No hay vacunas o desparasitaciones próximas.
                </DashboardEmptyMessage>
              )}
            </DashboardSection>
          </div>

          <DashboardKpiStrip
            items={[
              {
                href: "/agenda",
                icon: getKpiIcon("appointments"),
                label: getDashboardCardLabel(periodFilter, "Turnos hoy", "Turnos del período"),
                value: summary.cards.appointments_today,
                helper: getDashboardCardHelper(
                  periodFilter,
                  "Agenda programada para hoy",
                  "Turnos encontrados en el período seleccionado",
                ),
                tone: "blue",
              },
              {
                href: "/follow-ups",
                icon: getKpiIcon("upcoming_follow_ups"),
                label: "Seguimientos próximos",
                value: summary.cards.follow_ups_upcoming,
                helper: "Controles y recordatorios próximos",
                tone: "success",
              },
              {
                href: "/follow-ups",
                icon: getKpiIcon("overdue_follow_ups"),
                label: "Seguimientos vencidos",
                value: summary.cards.follow_ups_overdue,
                helper: "Casos que necesitan atención",
                tone: "warning",
              },
              {
                href: summary.recent_consultations[0]
                  ? `/consultations/${summary.recent_consultations[0].id}`
                  : "/patients",
                icon: getKpiIcon("consultations"),
                label: "Consultas recientes",
                value: summary.cards.consultations_recent,
                helper: "Actividad clínica registrada",
                tone: "success",
              },
              {
                href: summary.upcoming_preventive_care[0]
                  ? `/patients/${summary.upcoming_preventive_care[0].patient_id}`
                  : "/patients",
                icon: getKpiIcon("preventive_care"),
                label: "Vacunas próximas",
                value: summary.cards.preventive_care_upcoming,
                helper: "Próximas vacunas y desparasitaciones",
                tone: "blue",
              },
              {
                href: summary.recent_files[0]
                  ? `/patients/${summary.recent_files[0].patient_id}`
                  : "/patients",
                icon: getKpiIcon("files"),
                label: "Archivos recientes",
                value: summary.cards.files_recent,
                helper: "Documentos y estudios cargados",
                tone: "danger",
              },
            ]}
          />

          <div className="dashboard-secondary-grid">
            <DashboardSection
              title="Archivos recientes"
              subtitle="Documentos y resultados subidos a la historia clínica"
            >
              {summary.recent_files.length > 0 ? (
                <div className="dashboard-list">
                  {summary.recent_files.slice(0, 5).map((file) => (
                    <DashboardFileRow key={file.id} file={file} />
                  ))}
                </div>
              ) : (
                <DashboardEmptyMessage>
                  No hay archivos recientes.
                </DashboardEmptyMessage>
              )}
            </DashboardSection>

            <DashboardSection
              title="Actividad por veterinario"
              subtitle="Resumen de carga operativa del equipo"
            >
              {summary.activity_by_veterinarian.length > 0 ? (
                <div className="dashboard-activity-list">
                  {summary.activity_by_veterinarian.map((activity) => (
                    <DashboardActivityRow key={activity.user_id} activity={activity} />
                  ))}
                </div>
              ) : (
                <DashboardEmptyMessage>
                  No hay actividad registrada.
                </DashboardEmptyMessage>
              )}
            </DashboardSection>
          </div>
        </>
      ) : null}
    </div>
  );
}

function DashboardHeader({
  assignedUserId,
  isLoading,
  isRefreshing,
  onAssignedUserChange,
  onPeriodChange,
  onRefresh,
  periodFilter,
  showVetFilter,
  team,
}: {
  assignedUserId: string;
  isLoading: boolean;
  isRefreshing: boolean;
  onAssignedUserChange: (value: string) => void;
  onPeriodChange: (value: DashboardQuickPeriod) => void;
  onRefresh: () => void;
  periodFilter: DashboardQuickPeriod;
  showVetFilter: boolean;
  team: ClinicTeamMember[];
}) {
  return (
    <section className="screen-heading dashboard-hero">
      <div className="dashboard-heading-row">
        <div>
          <p className="eyebrow">Clínica</p>
          <h1>Dashboard</h1>
          <p>Operación clínica en tiempo real</p>
        </div>
        <button
          className="secondary-button dashboard-refresh-button"
          type="button"
          onClick={onRefresh}
          disabled={isLoading || isRefreshing}
        >
          <RefreshCw
            size={16}
            className={isRefreshing ? "dashboard-spin" : undefined}
          />
          <span>{isRefreshing ? "Actualizando..." : "Actualizar"}</span>
        </button>
      </div>

      <div className="dashboard-filters" aria-label="Filtros del dashboard">
        <div className="dashboard-period-filter">
          <span className="dashboard-filter-label">Periodo</span>
          <div className="tab-list" role="tablist" aria-label="Periodo del dashboard">
            {dashboardQuickPeriods.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`tab-pill${periodFilter === option.value ? " tab-pill--active" : ""}`}
                onClick={() => onPeriodChange(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {showVetFilter ? (
          <label className="compact-filter dashboard-vet-filter">
            <span className="dashboard-filter-label">Veterinario</span>
            <select
              value={assignedUserId}
              onChange={(event) => onAssignedUserChange(event.target.value)}
            >
              <option value="all">Todos</option>
              {team.map((member) => (
                <option key={member.id} value={member.id}>
                  {member.full_name}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>
    </section>
  );
}

function DashboardKpiStrip({
  items,
}: {
  items: Array<{
    href: string;
    icon: ReactNode;
    label: string;
    value: number;
    helper: string;
    tone: DashboardKpiTone;
  }>;
}) {
  return (
    <section className="dashboard-kpi-strip" aria-label="Indicadores principales">
      {items.map((item) => (
        <DashboardKpiCard key={`${item.href}-${item.label}`} {...item} />
      ))}
    </section>
  );
}

function DashboardKpiCard({
  href,
  icon,
  label,
  value,
  helper,
  tone,
}: {
  href: string;
  icon: ReactNode;
  label: string;
  value: number;
  helper: string;
  tone: DashboardKpiTone;
}) {
  return (
    <Link className={`kpi-card kpi-card--${tone} dashboard-kpi-link`} href={href}>
      <span className="kpi-card__icon">{icon}</span>
      <span className="kpi-card__value">{value}</span>
      <h2>{label}</h2>
      <p>{helper}</p>
    </Link>
  );
}

function DashboardSection({
  title,
  subtitle,
  actionHref,
  actionLabel,
  children,
  className,
}: {
  title: string;
  subtitle: string;
  actionHref?: string;
  actionLabel?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel dashboard-section${className ? ` ${className}` : ""}`}>
      <div className="section-heading section-heading--row">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        {actionHref && actionLabel ? (
          <Link className="dashboard-section-link" href={actionHref}>
            <span>{actionLabel}</span>
            <ArrowRight size={14} />
          </Link>
        ) : null}
      </div>
      {children}
    </section>
  );
}

function DashboardAppointmentRow({
  appointment,
}: {
  appointment: DashboardAppointmentItem;
}) {
  return (
    <Link className="dashboard-row" href={`/agenda/${appointment.id}`}>
      <div className="dashboard-row__main">
        <div className="dashboard-row__meta">
          <span className="dashboard-row__time">
            {formatDashboardTime(appointment.start_at)} - {formatDashboardTime(appointment.end_at)}
          </span>
          <span className={getDashboardAppointmentStatusClass(appointment.status)}>
            {getDashboardAppointmentStatusLabel(appointment.status)}
          </span>
        </div>
        <h3>{appointment.title}</h3>
        <p>
          {appointment.patient_name || "Paciente por confirmar"}
          {appointment.assigned_user_name ? ` · ${appointment.assigned_user_name}` : ""}
        </p>
      </div>
      <span className="dashboard-row__badge">
        {getDashboardAppointmentTypeLabel(appointment.appointment_type)}
      </span>
    </Link>
  );
}

function DashboardFollowUpRow({
  followUp,
}: {
  followUp: DashboardFollowUpItem;
}) {
  return (
    <Link className="dashboard-row" href={`/follow-ups/${followUp.id}`}>
      <div className="dashboard-row__main">
        <div className="dashboard-row__meta">
          <span className="dashboard-row__time">{formatDashboardDateTime(followUp.due_at)}</span>
          <span className={getDashboardFollowUpStatusClass(followUp.status)}>
            {getDashboardFollowUpStatusLabel(followUp.status)}
          </span>
        </div>
        <h3>{followUp.title}</h3>
        <p>
          {followUp.patient_name || "Paciente sin nombre"}
          {followUp.assigned_user_name ? ` · ${followUp.assigned_user_name}` : ""}
        </p>
      </div>
      <span className={getDashboardFollowUpTypeClass(followUp.follow_up_type)}>
        {getDashboardFollowUpTypeLabel(followUp.follow_up_type)}
      </span>
    </Link>
  );
}

function DashboardConsultationRow({
  consultation,
}: {
  consultation: DashboardConsultationItem;
}) {
  const veterinarian =
    consultation.attending_user_name || consultation.created_by_user_name || null;

  return (
    <Link className="dashboard-row" href={`/consultations/${consultation.id}`}>
      <div className="dashboard-row__main">
        <div className="dashboard-row__meta">
          <span className="dashboard-row__time">{formatDashboardDateTime(consultation.visit_date)}</span>
          <span className={getConsultationStatusClass(consultation.status)}>
            {getConsultationStatusLabel(consultation.status)}
          </span>
        </div>
        <h3>{consultation.patient_name || "Paciente sin nombre"}</h3>
        <p>
          {consultation.reason}
          {veterinarian ? ` · ${veterinarian}` : ""}
        </p>
      </div>
    </Link>
  );
}

function DashboardPreventiveCareRow({
  record,
}: {
  record: DashboardPreventiveCareItem;
}) {
  return (
    <Link className="dashboard-row" href={`/patients/${record.patient_id}`}>
      <div className="dashboard-row__main">
        <div className="dashboard-row__meta">
          <span className="dashboard-row__time">{formatDashboardDate(record.next_due_at)}</span>
          <span className={getPreventiveCareBadgeClass(record.care_type)}>
            {getPreventiveCareLabel(record.care_type)}
          </span>
        </div>
        <h3>{record.name}</h3>
        <p>
          {record.patient_name || "Paciente sin nombre"}
          {record.created_by_user_name ? ` · ${record.created_by_user_name}` : ""}
        </p>
      </div>
    </Link>
  );
}

function DashboardFileRow({
  file,
}: {
  file: DashboardFileItem;
}) {
  return (
    <Link className="dashboard-row" href={`/patients/${file.patient_id}`}>
      <div className="dashboard-row__main">
        <div className="dashboard-row__meta">
          <span className="dashboard-row__time">{formatDashboardDateTime(file.uploaded_at)}</span>
          <span className="badge badge--blue">{getDashboardFileTypeLabel(file.file_type)}</span>
        </div>
        <h3>{file.name}</h3>
        <p>
          {file.patient_name || "Paciente sin nombre"}
          {file.created_by_user_name ? ` · ${file.created_by_user_name}` : ""}
        </p>
      </div>
    </Link>
  );
}

function DashboardActivityRow({
  activity,
}: {
  activity: DashboardVeterinarianActivityItem;
}) {
  return (
    <article className="dashboard-activity-card">
      <div className="dashboard-activity-card__header">
        <span className="dashboard-activity-card__icon">
          <Stethoscope size={18} />
        </span>
        <div>
          <h3>{activity.full_name}</h3>
          <p>{activity.email}</p>
        </div>
      </div>

      <div className="dashboard-activity-card__stats">
        <div>
          <strong>{activity.appointments_today_count}</strong>
          <span>Turnos hoy</span>
        </div>
        <div>
          <strong>{activity.consultations_recent_count}</strong>
          <span>Consultas</span>
        </div>
        <div>
          <strong>{activity.follow_ups_pending_count}</strong>
          <span>Seguimientos</span>
        </div>
      </div>
    </article>
  );
}

function DashboardEmptyMessage({ children }: { children: ReactNode }) {
  return <div className="dashboard-empty">{children}</div>;
}

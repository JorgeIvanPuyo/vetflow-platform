import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { toDateInputValue } from "@/features/agenda/components/agenda-helpers";
import { selectDashboardAppointments } from "@/features/dashboard/components/dashboard-appointments";
import { formatDashboardDate, formatDashboardTime } from "@/features/dashboard/components/dashboard-helpers";
import type { DashboardAppointmentItem } from "@/types/api";

export function DashboardAppointmentsCard({
  appointments,
  now = new Date(),
}: {
  appointments: DashboardAppointmentItem[];
  now?: Date;
}) {
  const { today, next } = selectDashboardAppointments(appointments, now);
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const nextDateLabel = next && (
    toDateInputValue(new Date(next.start_at)) === toDateInputValue(tomorrow)
      ? "Mañana"
      : formatDashboardDate(next.start_at)
  );

  return (
    <section className="panel dashboard-section dashboard-section--appointments">
      <div className="section-heading section-heading--row">
        <div>
          <h2>Turnos</h2>
          <p>Hoy y próximos turnos</p>
        </div>
        <Link className="dashboard-section-link" href="/agenda">
          <span>Ver agenda</span>
          <ArrowRight aria-hidden="true" size={14} />
        </Link>
      </div>
      {today.length === 0 && !next ? (
        <p className="dashboard-empty">No hay turnos programados para hoy ni próximos.</p>
      ) : (
        <>
          <div className="dashboard-appointments-group">
            <h3>Hoy</h3>
            {today.length > 0 ? today.map((appointment) => (
              <AppointmentRow key={appointment.id} appointment={appointment} />
            )) : (
              <p className="dashboard-empty">No hay turnos programados para hoy.</p>
            )}
          </div>
          {today.length === 0 && next ? (
            <div className="dashboard-appointments-group">
              <h3>Próximo turno</h3>
              <AppointmentRow appointment={next} dateLabel={nextDateLabel || undefined} />
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}

function AppointmentRow({ appointment, dateLabel }: {
  appointment: DashboardAppointmentItem;
  dateLabel?: string;
}) {
  return (
    <Link className="dashboard-appointment" href={`/agenda/${appointment.id}`}>
      <time dateTime={appointment.start_at}>
        {dateLabel ? `${dateLabel} · ` : ""}{formatDashboardTime(appointment.start_at)}
      </time>
      <span className="dashboard-appointment__details">
        <strong>{appointment.title}</strong>
        <span>
          {appointment.patient_name || "Paciente por confirmar"}
          {appointment.owner_name ? ` · ${appointment.owner_name}` : ""}
          {appointment.assigned_user_name ? ` · ${appointment.assigned_user_name}` : ""}
        </span>
      </span>
    </Link>
  );
}

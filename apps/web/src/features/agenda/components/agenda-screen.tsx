"use client";

import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock,
  Plus,
  Stethoscope,
  X,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { getApiErrorMessage } from "@/lib/api";
import { useAuth } from "@/features/auth/auth-context";
import { createAppointment, getAppointments } from "@/services/appointments";
import { getClinicTeam } from "@/services/clinic";
import { getOwners } from "@/services/owners";
import { getPatients } from "@/services/patients";
import type {
  Appointment,
  AppointmentStatus,
  AppointmentType,
  ClinicTeamMember,
  CreateAppointmentPayload,
  Owner,
  Patient,
} from "@/types/api";

import {
  AppointmentFormState,
  appointmentStatusOptions,
  appointmentTypeOptions,
  buildAppointmentDateTime,
  formatAppointmentTimeRange,
  formatDateLabel,
  getAppointmentStatusLabel,
  getAppointmentTypeLabel,
  getAppointmentUserName,
  getDayRange,
  getInitialAppointmentFormState,
  getStatusBadgeClass,
  getTypeBadgeClass,
  parseDateInput,
  toDateInputValue,
} from "./agenda-helpers";

type AgendaState = {
  isLoading: boolean;
  isSubmitting: boolean;
  appointments: Appointment[];
  patients: Patient[];
  owners: Owner[];
  team: ClinicTeamMember[];
  errorMessage: string | null;
  flowMessage: string | null;
  successMessage: string | null;
};

const initialState: AgendaState = {
  isLoading: true,
  isSubmitting: false,
  appointments: [],
  patients: [],
  owners: [],
  team: [],
  errorMessage: null,
  flowMessage: null,
  successMessage: null,
};

export function AgendaScreen() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const requestedPatientId = searchParams.get("patient_id") ?? "";
  const [selectedDate, setSelectedDate] = useState(toDateInputValue(new Date()));
  const [statusFilter, setStatusFilter] = useState<AppointmentStatus | "all">("all");
  const [typeFilter, setTypeFilter] = useState<AppointmentType | "all">("all");
  const [vetFilter, setVetFilter] = useState<string>("all");
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [formState, setFormState] = useState<AppointmentFormState>(
    getInitialAppointmentFormState(),
  );
  const [state, setState] = useState<AgendaState>(initialState);

  const loadAgenda = useCallback(async (dateValue: string) => {
    setState((current) => ({
      ...current,
      isLoading: true,
      errorMessage: null,
    }));

    try {
      const [appointmentsResponse, patientsResponse, ownersResponse, teamResponse] =
        await Promise.all([
          getAppointments(getDayRange(dateValue)),
          getPatients(),
          getOwners(),
          getClinicTeam(),
        ]);

      setState((current) => ({
        ...current,
        isLoading: false,
        appointments: appointmentsResponse.data,
        patients: patientsResponse.data,
        owners: ownersResponse.data,
        team: teamResponse.data,
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        isLoading: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }, []);

  useEffect(() => {
    void loadAgenda(selectedDate);
  }, [loadAgenda, selectedDate]);

  useEffect(() => {
    if (!requestedPatientId || state.patients.length === 0) {
      return;
    }

    const patient = state.patients.find((item) => item.id === requestedPatientId);
    if (!patient) {
      return;
    }

    setFormState((current) => ({
      ...current,
      patient_id: patient.id,
      owner_id: patient.owner_id,
      date: selectedDate,
      assigned_user_id:
        current.assigned_user_id || getDefaultAssignedUserId(state.team, user?.email),
    }));
    setIsCreateOpen(true);
  }, [requestedPatientId, selectedDate, state.patients, state.team, user?.email]);

  function openCreateModal() {
    const nextFormState = getInitialAppointmentFormState(parseDateInput(selectedDate));
    setFormState({
      ...nextFormState,
      date: selectedDate,
      assigned_user_id: getDefaultAssignedUserId(state.team, user?.email),
    });
    setState((current) => ({
      ...current,
      flowMessage: null,
      successMessage: null,
    }));
    setIsCreateOpen(true);
  }

  function closeCreateModal() {
    setIsCreateOpen(false);
    setState((current) => ({
      ...current,
      isSubmitting: false,
      flowMessage: null,
    }));
  }

  function moveDay(delta: number) {
    const nextDate = parseDateInput(selectedDate);
    nextDate.setDate(nextDate.getDate() + delta);
    setSelectedDate(toDateInputValue(nextDate));
  }

  function handlePatientChange(patientId: string) {
    const patient = state.patients.find((item) => item.id === patientId);
    setFormState((current) => ({
      ...current,
      patient_id: patientId,
      owner_id: patient?.owner_id ?? current.owner_id,
    }));
  }

  async function handleCreateAppointment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const validationMessage = validateAppointmentForm(formState);
    if (validationMessage) {
      setState((current) => ({ ...current, flowMessage: validationMessage }));
      return;
    }

    const payload = buildAppointmentPayload(formState);

    setState((current) => ({
      ...current,
      isSubmitting: true,
      flowMessage: null,
      successMessage: null,
    }));

    try {
      await createAppointment(payload);
      setIsCreateOpen(false);
      setState((current) => ({
        ...current,
        isSubmitting: false,
        successMessage: "Turno creado correctamente.",
      }));
      await loadAgenda(selectedDate);
    } catch (error) {
      setState((current) => ({
        ...current,
        isSubmitting: false,
        flowMessage: getApiErrorMessage(error),
      }));
    }
  }

  const veterinarianOptions = useMemo(() => {
    if (state.team.length > 0) {
      return state.team.map((member) => ({ id: member.id, label: member.full_name }));
    }

    const options = new Map<string, string>();
    state.appointments.forEach((appointment) => {
      const label = getAppointmentUserName(
        appointment.assigned_user_name,
        appointment.assigned_user_email,
      );
      if (appointment.assigned_user_id && label) {
        options.set(appointment.assigned_user_id, label);
      }
    });
    return Array.from(options, ([id, label]) => ({ id, label }));
  }, [state.appointments, state.team]);

  const filteredAppointments = useMemo(() => {
    return state.appointments.filter((appointment) => {
      if (statusFilter !== "all" && appointment.status !== statusFilter) {
        return false;
      }
      if (typeFilter !== "all" && appointment.appointment_type !== typeFilter) {
        return false;
      }
      if (vetFilter !== "all" && appointment.assigned_user_id !== vetFilter) {
        return false;
      }
      return true;
    });
  }, [state.appointments, statusFilter, typeFilter, vetFilter]);

  return (
    <div className="page-stack agenda-layout">
      <section className="screen-heading screen-heading--with-action">
        <div>
          <p className="eyebrow">Clínica</p>
          <h1>Agenda</h1>
          <p>Turnos y citas de la clínica</p>
        </div>
        <button className="primary-button agenda-new-button" onClick={openCreateModal} type="button">
          <Plus aria-hidden="true" size={18} />
          <span>Nuevo turno</span>
        </button>
      </section>

      <section className="agenda-date-card" aria-label="Navegación por fecha">
        <button className="icon-button" onClick={() => moveDay(-1)} type="button" aria-label="Día anterior">
          <ChevronLeft aria-hidden="true" size={20} />
        </button>
        <div className="agenda-date-card__label">
          <CalendarDays aria-hidden="true" size={18} />
          <strong>{formatDateLabel(selectedDate)}</strong>
          <input
            aria-label="Seleccionar fecha"
            type="date"
            value={selectedDate}
            onChange={(event) => setSelectedDate(event.target.value)}
          />
        </div>
        <button className="icon-button" onClick={() => moveDay(1)} type="button" aria-label="Día siguiente">
          <ChevronRight aria-hidden="true" size={20} />
        </button>
        <button className="secondary-button" onClick={() => setSelectedDate(toDateInputValue(new Date()))} type="button">
          Hoy
        </button>
      </section>

      <section className="agenda-filters" aria-label="Filtros de agenda">
        {veterinarianOptions.length > 0 ? (
          <label className="field">
            <span>Veterinario</span>
            <select value={vetFilter} onChange={(event) => setVetFilter(event.target.value)}>
              <option value="all">Todos</option>
              {veterinarianOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <label className="field">
          <span>Estado</span>
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as AppointmentStatus | "all")}
          >
            <option value="all">Todos</option>
            {appointmentStatusOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Tipo</span>
          <select
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value as AppointmentType | "all")}
          >
            <option value="all">Todos</option>
            {appointmentTypeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </section>

      {state.successMessage ? <div className="success-state">{state.successMessage}</div> : null}
      {state.errorMessage ? <div className="error-state">{state.errorMessage}</div> : null}

      {state.isLoading ? <div className="loading-card" aria-label="Cargando agenda" /> : null}

      {!state.isLoading && !state.errorMessage && filteredAppointments.length === 0 ? (
        <div className="empty-state">
          <strong>No hay turnos programados para este día.</strong>
          <span>Crea un turno para agendar una consulta, control, vacuna o examen.</span>
        </div>
      ) : null}

      {!state.isLoading && !state.errorMessage && filteredAppointments.length > 0 ? (
        <section className="appointment-list" aria-label="Turnos del día">
          {filteredAppointments.map((appointment) => (
            <AppointmentCard appointment={appointment} key={appointment.id} />
          ))}
        </section>
      ) : null}

      {isCreateOpen ? (
        <AppointmentFormModal
          flowMessage={state.flowMessage}
          formState={formState}
          isSubmitting={state.isSubmitting}
          owners={state.owners}
          patients={state.patients}
          team={state.team}
          submitLabel="Crear turno"
          title="Nuevo turno"
          onClose={closeCreateModal}
          onPatientChange={handlePatientChange}
          onSubmit={handleCreateAppointment}
          onUpdateForm={setFormState}
        />
      ) : null}
    </div>
  );
}

function AppointmentCard({ appointment }: { appointment: Appointment }) {
  const assignedUser = getAppointmentUserName(
    appointment.assigned_user_name,
    appointment.assigned_user_email,
  );

  return (
    <Link className="appointment-card" href={`/agenda/${appointment.id}`}>
      <div className="appointment-card__time">
        <Clock aria-hidden="true" size={17} />
        <strong>{formatAppointmentTimeRange(appointment)}</strong>
      </div>
      <div className="appointment-card__body">
        <div className="appointment-card__title-row">
          <h2>{appointment.title}</h2>
          <span className={getTypeBadgeClass(appointment.appointment_type)}>
            {getAppointmentTypeLabel(appointment.appointment_type)}
          </span>
          <span className={getStatusBadgeClass(appointment.status)}>
            {getAppointmentStatusLabel(appointment.status)}
          </span>
        </div>
        {appointment.reason ? <p>{appointment.reason}</p> : null}
        <div className="appointment-card__meta">
          {appointment.patient_name ? <span>Paciente: {appointment.patient_name}</span> : null}
          {appointment.owner_name ? <span>Propietario: {appointment.owner_name}</span> : null}
          {assignedUser ? <span>Veterinario: {assignedUser}</span> : null}
        </div>
      </div>
      <ChevronRight aria-hidden="true" className="patient-card__chevron" size={20} />
    </Link>
  );
}

type AppointmentFormModalProps = {
  title: string;
  submitLabel: string;
  formState: AppointmentFormState;
  patients: Patient[];
  owners: Owner[];
  team: ClinicTeamMember[];
  isSubmitting: boolean;
  flowMessage: string | null;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onUpdateForm: (nextState: AppointmentFormState) => void;
  onPatientChange: (patientId: string) => void;
};

export function AppointmentFormModal({
  title,
  submitLabel,
  formState,
  patients,
  owners,
  team,
  isSubmitting,
  flowMessage,
  onClose,
  onSubmit,
  onUpdateForm,
  onPatientChange,
}: AppointmentFormModalProps) {
  const selectedOwner = owners.find((owner) => owner.id === formState.owner_id);

  return (
    <div className="modal-backdrop" role="presentation">
      <section aria-labelledby="appointment-form-title" aria-modal="true" className="bottom-sheet" role="dialog">
        <div className="bottom-sheet__header">
          <div>
            <p className="eyebrow">Agenda clínica</p>
            <h2 id="appointment-form-title">{title}</h2>
          </div>
          <button aria-label="Cancelar" className="icon-button" onClick={onClose} type="button">
            <X aria-hidden="true" size={20} />
          </button>
        </div>

        {flowMessage ? <div className="error-state">{flowMessage}</div> : null}

        <form className="entity-form" onSubmit={onSubmit}>
          <label className="field">
            <span>Título *</span>
            <input
              required
              placeholder="Ej. Control general"
              value={formState.title}
              onChange={(event) => onUpdateForm({ ...formState, title: event.target.value })}
            />
          </label>

          <label className="field">
            <span>Paciente</span>
            <select
              value={formState.patient_id}
              onChange={(event) => onPatientChange(event.target.value)}
            >
              <option value="">Sin paciente seleccionado</option>
              {patients.map((patient) => (
                <option key={patient.id} value={patient.id}>
                  {patient.name} · {patient.species}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Propietario</span>
            <select
              value={formState.owner_id}
              onChange={(event) => onUpdateForm({ ...formState, owner_id: event.target.value })}
            >
              <option value="">Sin propietario seleccionado</option>
              {owners.map((owner) => (
                <option key={owner.id} value={owner.id}>
                  {owner.full_name} · {owner.phone}
                </option>
              ))}
            </select>
          </label>

          {selectedOwner ? (
            <p className="panel-note">Propietario seleccionado: {selectedOwner.full_name}</p>
          ) : null}

          <label className="field">
            <span>Veterinario asignado *</span>
            <select
              required
              value={formState.assigned_user_id}
              onChange={(event) =>
                onUpdateForm({
                  ...formState,
                  assigned_user_id: event.target.value,
                })
              }
            >
              <option value="">Selecciona un veterinario</option>
              {team.map((member) => (
                <option key={member.id} value={member.id}>
                  {member.full_name}
                </option>
              ))}
            </select>
          </label>

          {team.length === 0 ? (
            <div className="clinical-section">
              <div className="agenda-assignment-note">
                <Stethoscope aria-hidden="true" size={18} />
                <span>No hay equipo activo disponible para asignar.</span>
              </div>
            </div>
          ) : null}

          <div className="form-grid">
            <label className="field">
              <span>Tipo *</span>
              <select
                required
                value={formState.appointment_type}
                onChange={(event) =>
                  onUpdateForm({
                    ...formState,
                    appointment_type: event.target.value as AppointmentType,
                  })
                }
              >
                {appointmentTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>Estado</span>
              <select
                value={formState.status}
                onChange={(event) =>
                  onUpdateForm({
                    ...formState,
                    status: event.target.value as AppointmentStatus,
                  })
                }
              >
                {appointmentStatusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>Fecha *</span>
              <input
                required
                type="date"
                value={formState.date}
                onChange={(event) => onUpdateForm({ ...formState, date: event.target.value })}
              />
            </label>

            <label className="field">
              <span>Hora inicio *</span>
              <input
                required
                type="time"
                value={formState.start_time}
                onChange={(event) =>
                  onUpdateForm({ ...formState, start_time: event.target.value })
                }
              />
            </label>

            <label className="field">
              <span>Hora fin *</span>
              <input
                required
                type="time"
                value={formState.end_time}
                onChange={(event) =>
                  onUpdateForm({ ...formState, end_time: event.target.value })
                }
              />
            </label>
          </div>

          <label className="field">
            <span>Motivo</span>
            <textarea
              rows={3}
              value={formState.reason}
              onChange={(event) => onUpdateForm({ ...formState, reason: event.target.value })}
            />
          </label>

          <label className="field">
            <span>Notas</span>
            <textarea
              rows={3}
              value={formState.notes}
              onChange={(event) => onUpdateForm({ ...formState, notes: event.target.value })}
            />
          </label>

          <div className="modal-actions">
            <button className="secondary-button" onClick={onClose} type="button">
              Cancelar
            </button>
            <button className="primary-button" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Guardando..." : submitLabel}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export function validateAppointmentForm(form: AppointmentFormState) {
  if (!form.title.trim()) {
    return "Escribe un título para el turno.";
  }
  if (!form.appointment_type || !form.date || !form.start_time || !form.end_time) {
    return "Completa tipo, fecha, hora de inicio y hora de fin.";
  }
  if (!form.assigned_user_id) {
    return "Selecciona el veterinario asignado para el turno.";
  }

  const startAt = buildAppointmentDateTime(form.date, form.start_time);
  const endAt = buildAppointmentDateTime(form.date, form.end_time);

  if (endAt <= startAt) {
    return "La hora de fin debe ser posterior a la hora de inicio.";
  }

  return null;
}

export function buildAppointmentPayload(
  form: AppointmentFormState,
): CreateAppointmentPayload {
  return {
    patient_id: form.patient_id || null,
    owner_id: form.owner_id || null,
    assigned_user_id: form.assigned_user_id,
    title: form.title.trim(),
    reason: form.reason.trim() || null,
    appointment_type: form.appointment_type,
    status: form.status,
    start_at: buildAppointmentDateTime(form.date, form.start_time).toISOString(),
    end_at: buildAppointmentDateTime(form.date, form.end_time).toISOString(),
    notes: form.notes.trim() || null,
  };
}

function getDefaultAssignedUserId(team: ClinicTeamMember[], email?: string | null) {
  if (!email) {
    return team[0]?.id ?? "";
  }

  return (
    team.find((member) => member.email.toLowerCase() === email.toLowerCase())?.id ??
    team[0]?.id ??
    ""
  );
}

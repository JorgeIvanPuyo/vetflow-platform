"use client";

import {
  CheckCircle2,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock,
  Plus,
  Stethoscope,
  Syringe,
  X,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { getApiErrorMessage } from "@/lib/api";
import { useAuth } from "@/features/auth/auth-context";
import { createAppointment, getAppointments } from "@/services/appointments";
import { getClinicTeam } from "@/services/clinic";
import {
  cancelFollowUp,
  completeFollowUp,
  createFollowUp,
  getFollowUps,
} from "@/services/follow-ups";
import { getOwners } from "@/services/owners";
import { getPatients } from "@/services/patients";
import type {
  Appointment,
  AppointmentStatus,
  AppointmentType,
  ClinicTeamMember,
  CreateAppointmentPayload,
  FollowUp,
  FollowUpStatus,
  FollowUpType,
  Owner,
  Patient,
} from "@/types/api";
import { FollowUpFormModal } from "@/features/follow-ups/components/follow-up-form-modal";
import {
  FollowUpFormState,
  buildFollowUpPayload,
  followUpStatusOptions,
  followUpTypeOptions,
  getDefaultAssignedUserId as getDefaultFollowUpAssignedUserId,
  getFollowUpUserName,
  getFollowUpIcon,
  getFollowUpStatusBadgeClass,
  getFollowUpStatusLabel,
  getFollowUpTypeBadgeClass,
  getFollowUpTypeLabel,
  getInitialFollowUpFormState,
  getPatientOwnerId,
  validateFollowUpForm,
} from "@/features/follow-ups/components/follow-up-helpers";

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

type AgendaTab = "appointments" | "follow_ups";

type AgendaState = {
  isLoading: boolean;
  isSubmitting: boolean;
  appointments: Appointment[];
  followUps: FollowUp[];
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
  followUps: [],
  patients: [],
  owners: [],
  team: [],
  errorMessage: null,
  flowMessage: null,
  successMessage: null,
};

export function AgendaScreen({
  initialTab = "appointments",
}: {
  initialTab?: AgendaTab;
}) {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const requestedPatientId = searchParams.get("patient_id") ?? "";
  const requestedTab = searchParams.get("tab");
  const [selectedDate, setSelectedDate] = useState(toDateInputValue(new Date()));
  const [activeTab, setActiveTab] = useState<AgendaTab>(
    requestedTab === "follow_ups" ? "follow_ups" : initialTab,
  );
  const [statusFilter, setStatusFilter] = useState<AppointmentStatus | "all">("all");
  const [typeFilter, setTypeFilter] = useState<AppointmentType | "all">("all");
  const [vetFilter, setVetFilter] = useState<string>("all");
  const [followUpStatusFilter, setFollowUpStatusFilter] = useState<FollowUpStatus | "all">(
    "all",
  );
  const [followUpTypeFilter, setFollowUpTypeFilter] = useState<FollowUpType | "all">(
    "all",
  );
  const [followUpVetFilter, setFollowUpVetFilter] = useState<string>("all");
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isFollowUpCreateOpen, setIsFollowUpCreateOpen] = useState(false);
  const [formState, setFormState] = useState<AppointmentFormState>(
    getInitialAppointmentFormState(),
  );
  const [followUpFormState, setFollowUpFormState] = useState<FollowUpFormState>(
    getInitialFollowUpFormState(),
  );
  const [followUpToCancel, setFollowUpToCancel] = useState<FollowUp | null>(null);
  const [followUpCancelNotes, setFollowUpCancelNotes] = useState("");
  const [state, setState] = useState<AgendaState>(initialState);

  const loadAgenda = useCallback(async (dateValue: string) => {
    setState((current) => ({
      ...current,
      isLoading: true,
      errorMessage: null,
    }));

    try {
      const [
        appointmentsResponse,
        followUpsResponse,
        patientsResponse,
        ownersResponse,
        teamResponse,
      ] =
        await Promise.all([
          getAppointments(getDayRange(dateValue)),
          getFollowUps(getDayRange(dateValue)),
          getPatients(),
          getOwners(),
          getClinicTeam(),
        ]);

      setState((current) => ({
        ...current,
        isLoading: false,
        appointments: appointmentsResponse.data,
        followUps: followUpsResponse.data,
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
    if (requestedTab === "follow_ups") {
      setActiveTab("follow_ups");
      return;
    }

    if (requestedTab === "appointments") {
      setActiveTab("appointments");
    }
  }, [requestedTab]);

  useEffect(() => {
    if (!requestedPatientId || state.patients.length === 0) {
      return;
    }

    const patient = state.patients.find((item) => item.id === requestedPatientId);
    if (!patient) {
      return;
    }

    if (requestedTab === "follow_ups") {
      setActiveTab("follow_ups");
      setFollowUpFormState((current) => ({
        ...current,
        patient_id: patient.id,
        owner_id: patient.owner_id,
        date: selectedDate,
        assigned_user_id:
          current.assigned_user_id ||
          getDefaultFollowUpAssignedUserId(state.team, user?.email) ||
          state.team[0]?.id ||
          "",
      }));
      setIsFollowUpCreateOpen(true);
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
  }, [
    requestedPatientId,
    requestedTab,
    selectedDate,
    state.patients,
    state.team,
    user?.email,
  ]);

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

  function openFollowUpModal() {
    const nextFormState = getInitialFollowUpFormState(parseDateInput(selectedDate));
    setFollowUpFormState({
      ...nextFormState,
      date: selectedDate,
      assigned_user_id:
        getDefaultFollowUpAssignedUserId(state.team, user?.email) || state.team[0]?.id || "",
    });
    setState((current) => ({
      ...current,
      flowMessage: null,
      successMessage: null,
    }));
    setIsFollowUpCreateOpen(true);
  }

  function closeCreateModal() {
    setIsCreateOpen(false);
    setState((current) => ({
      ...current,
      isSubmitting: false,
      flowMessage: null,
    }));
  }

  function closeFollowUpModal() {
    setIsFollowUpCreateOpen(false);
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

  function handleFollowUpPatientChange(patientId: string) {
    setFollowUpFormState((current) => ({
      ...current,
      patient_id: patientId,
      owner_id: getPatientOwnerId(state.patients, patientId, current.owner_id),
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

  async function handleCreateFollowUp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const validationMessage = validateFollowUpForm(followUpFormState, {
      teamRequired: state.team.length > 0,
    });
    if (validationMessage) {
      setState((current) => ({ ...current, flowMessage: validationMessage }));
      return;
    }

    setState((current) => ({
      ...current,
      isSubmitting: true,
      flowMessage: null,
      successMessage: null,
    }));

    try {
      await createFollowUp(buildFollowUpPayload(followUpFormState));
      setIsFollowUpCreateOpen(false);
      setState((current) => ({
        ...current,
        isSubmitting: false,
        successMessage: followUpFormState.create_appointment
          ? "Seguimiento y turno programados correctamente."
          : "Seguimiento programado correctamente.",
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

  async function handleCompleteFollowUp(followUp: FollowUp) {
    const confirmed = window.confirm("¿Marcar este seguimiento como completado?");
    if (!confirmed) {
      return;
    }

    setState((current) => ({
      ...current,
      isSubmitting: true,
      errorMessage: null,
      successMessage: null,
    }));

    try {
      await completeFollowUp(followUp.id);
      setState((current) => ({
        ...current,
        isSubmitting: false,
        successMessage: "Seguimiento completado correctamente.",
      }));
      await loadAgenda(selectedDate);
    } catch (error) {
      setState((current) => ({
        ...current,
        isSubmitting: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }

  function openCancelFollowUpModal(followUp: FollowUp) {
    setFollowUpToCancel(followUp);
    setFollowUpCancelNotes("");
    setState((current) => ({
      ...current,
      errorMessage: null,
      successMessage: null,
      flowMessage: null,
    }));
  }

  function closeCancelFollowUpModal() {
    if (state.isSubmitting) {
      return;
    }

    setFollowUpToCancel(null);
    setFollowUpCancelNotes("");
  }

  async function handleCancelFollowUp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!followUpToCancel) {
      return;
    }

    setState((current) => ({
      ...current,
      isSubmitting: true,
      flowMessage: null,
      successMessage: null,
    }));

    try {
      await cancelFollowUp(followUpToCancel.id, followUpCancelNotes.trim() || undefined);
      setFollowUpToCancel(null);
      setFollowUpCancelNotes("");
      setState((current) => ({
        ...current,
        isSubmitting: false,
        successMessage: "Seguimiento cancelado correctamente.",
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
    [...state.appointments, ...state.followUps].forEach((item) => {
      const label = getAppointmentUserName(
        item.assigned_user_name,
        item.assigned_user_email,
      );
      if (item.assigned_user_id && label) {
        options.set(item.assigned_user_id, label);
      }
    });
    return Array.from(options, ([id, label]) => ({ id, label }));
  }, [state.appointments, state.followUps, state.team]);

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

  const filteredFollowUps = useMemo(() => {
    return state.followUps.filter((followUp) => {
      if (followUpStatusFilter !== "all" && followUp.status !== followUpStatusFilter) {
        return false;
      }
      if (followUpTypeFilter !== "all" && followUp.follow_up_type !== followUpTypeFilter) {
        return false;
      }
      if (followUpVetFilter !== "all" && followUp.assigned_user_id !== followUpVetFilter) {
        return false;
      }
      return true;
    });
  }, [state.followUps, followUpStatusFilter, followUpTypeFilter, followUpVetFilter]);

  return (
    <div className="page-stack agenda-layout">
      <section className="screen-heading list-page__header">
        <div>
          <h1>Agenda</h1>
          <p>Turnos y seguimientos clínicos de la clínica</p>
        </div>
      </section>

      <button
        aria-label={activeTab === "appointments" ? "Nuevo turno" : "Nuevo seguimiento"}
        className="floating-add-button list-page__fab"
        onClick={activeTab === "appointments" ? openCreateModal : openFollowUpModal}
        type="button"
      >
        <Plus aria-hidden="true" size={24} />
      </button>

      <section className="panel tabbed-card">
        <div className="tab-list" aria-label="Secciones de agenda">
          <button
            aria-pressed={activeTab === "appointments"}
            className={activeTab === "appointments" ? "tab-pill tab-pill--active" : "tab-pill"}
            type="button"
            onClick={() => setActiveTab("appointments")}
          >
            Turnos
          </button>
          <button
            aria-pressed={activeTab === "follow_ups"}
            className={activeTab === "follow_ups" ? "tab-pill tab-pill--active" : "tab-pill"}
            type="button"
            onClick={() => setActiveTab("follow_ups")}
          >
            Seguimientos
          </button>
        </div>
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
          {activeTab === "appointments" ? (
            <select
              value={statusFilter}
              onChange={(event) =>
                setStatusFilter(event.target.value as AppointmentStatus | "all")
              }
            >
              <option value="all">Todos</option>
              {appointmentStatusOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          ) : (
            <select
              value={followUpStatusFilter}
              onChange={(event) =>
                setFollowUpStatusFilter(event.target.value as FollowUpStatus | "all")
              }
            >
              <option value="all">Todos</option>
              {followUpStatusOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          )}
        </label>
        <label className="field">
          <span>Tipo</span>
          {activeTab === "appointments" ? (
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
          ) : (
            <select
              value={followUpTypeFilter}
              onChange={(event) =>
                setFollowUpTypeFilter(event.target.value as FollowUpType | "all")
              }
            >
              <option value="all">Todos</option>
              {followUpTypeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          )}
        </label>
      </section>

      {state.successMessage ? <div className="success-state">{state.successMessage}</div> : null}
      {state.errorMessage ? <div className="error-state">{state.errorMessage}</div> : null}

      {state.isLoading ? <div className="loading-card" aria-label="Cargando agenda" /> : null}

      {!state.isLoading &&
      !state.errorMessage &&
      activeTab === "appointments" &&
      filteredAppointments.length === 0 ? (
        <div className="empty-state">
          <strong>No hay turnos programados para este día.</strong>
          <span>Crea un turno para agendar una consulta, control, vacuna o examen.</span>
        </div>
      ) : null}

      {!state.isLoading &&
      !state.errorMessage &&
      activeTab === "appointments" &&
      filteredAppointments.length > 0 ? (
        <section className="appointment-list" aria-label="Turnos del día">
          {filteredAppointments.map((appointment) => (
            <AppointmentCard appointment={appointment} key={appointment.id} />
          ))}
        </section>
      ) : null}

      {!state.isLoading &&
      !state.errorMessage &&
      activeTab === "follow_ups" &&
      filteredFollowUps.length === 0 ? (
        <div className="empty-state">
          <strong>No hay seguimientos programados para este día.</strong>
          <span>Programa controles, vacunas, desparasitaciones o revisiones clínicas.</span>
        </div>
      ) : null}

      {!state.isLoading &&
      !state.errorMessage &&
      activeTab === "follow_ups" &&
      filteredFollowUps.length > 0 ? (
        <section className="appointment-list" aria-label="Seguimientos del día">
          {filteredFollowUps.map((followUp) => (
            <FollowUpCard
              followUp={followUp}
              isBusy={state.isSubmitting}
              key={followUp.id}
              onCancel={openCancelFollowUpModal}
              onComplete={handleCompleteFollowUp}
            />
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

      {isFollowUpCreateOpen ? (
        <FollowUpFormModal
          flowMessage={state.flowMessage}
          formState={followUpFormState}
          isSubmitting={state.isSubmitting}
          owners={state.owners}
          patients={state.patients}
          submitLabel="Programar seguimiento"
          team={state.team}
          title="Nuevo seguimiento"
          onClose={closeFollowUpModal}
          onPatientChange={handleFollowUpPatientChange}
          onSubmit={handleCreateFollowUp}
          onUpdateForm={setFollowUpFormState}
        />
      ) : null}

      {followUpToCancel ? (
        <FollowUpCancelModal
          followUp={followUpToCancel}
          isSubmitting={state.isSubmitting}
          notes={followUpCancelNotes}
          onClose={closeCancelFollowUpModal}
          onNotesChange={setFollowUpCancelNotes}
          onSubmit={handleCancelFollowUp}
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

function FollowUpCard({
  followUp,
  isBusy,
  onComplete,
  onCancel,
}: {
  followUp: FollowUp;
  isBusy: boolean;
  onComplete: (followUp: FollowUp) => void;
  onCancel: (followUp: FollowUp) => void;
}) {
  const assignedUser = getFollowUpUserName(
    followUp.assigned_user_name,
    followUp.assigned_user_email,
  );

  return (
    <article className="appointment-card follow-up-card">
      <div className="appointment-card__time">
        <Clock aria-hidden="true" size={17} />
        <strong>{formatDateTimeCompact(followUp.due_at)}</strong>
      </div>
      <div className="appointment-card__body">
        <div className="appointment-card__title-row">
          <h2>{followUp.title}</h2>
          <span className={getFollowUpTypeBadgeClass(followUp.follow_up_type)}>
            {getFollowUpTypeLabel(followUp.follow_up_type)}
          </span>
          <span className={getFollowUpStatusBadgeClass(followUp.status)}>
            {getFollowUpStatusLabel(followUp.status)}
          </span>
        </div>
        {followUp.description ? <p>{followUp.description}</p> : null}
        <div className="appointment-card__meta">
          {followUp.patient_name ? <span>Paciente: {followUp.patient_name}</span> : null}
          {followUp.owner_name ? <span>Propietario: {followUp.owner_name}</span> : null}
          {assignedUser ? <span>Veterinario: {assignedUser}</span> : null}
          {followUp.appointment_id ? <span>Turno asociado en agenda</span> : null}
        </div>
        <div className="record-card__actions">
          <Link className="secondary-button" href={`/follow-ups/${followUp.id}`}>
            Ver
          </Link>
          <button
            className="secondary-button"
            disabled={
              isBusy ||
              followUp.status === "completed" ||
              followUp.status === "cancelled"
            }
            type="button"
            onClick={() => onComplete(followUp)}
          >
            <CheckCircle2 aria-hidden="true" size={16} />
            Completar
          </button>
          <button
            className="secondary-button secondary-button--danger"
            disabled={isBusy || followUp.status === "cancelled"}
            type="button"
            onClick={() => onCancel(followUp)}
          >
            <XCircle aria-hidden="true" size={16} />
            Cancelar
          </button>
        </div>
      </div>
      <span className="follow-up-card__icon" aria-hidden="true">
        {getFollowUpIcon(followUp.follow_up_type)}
      </span>
    </article>
  );
}

function FollowUpCancelModal({
  followUp,
  notes,
  isSubmitting,
  onClose,
  onNotesChange,
  onSubmit,
}: {
  followUp: FollowUp;
  notes: string;
  isSubmitting: boolean;
  onClose: () => void;
  onNotesChange: (notes: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section
        aria-labelledby="cancel-follow-up-title"
        aria-modal="true"
        className="bottom-sheet"
        role="dialog"
      >
        <div className="bottom-sheet__header">
          <div>
            <p className="eyebrow">Seguimiento clínico</p>
            <h2 id="cancel-follow-up-title">Cancelar seguimiento</h2>
          </div>
          <button
            aria-label="Cerrar"
            className="icon-button"
            disabled={isSubmitting}
            onClick={onClose}
            type="button"
          >
            <X aria-hidden="true" size={20} />
          </button>
        </div>

        <div className="clinical-section">
          <strong>{followUp.title}</strong>
          <p className="panel-note">Puedes dejar una nota opcional para documentar la cancelación.</p>
        </div>

        <form className="entity-form" onSubmit={onSubmit}>
          <label className="field">
            <span>Notas de cancelación</span>
            <textarea
              rows={4}
              value={notes}
              onChange={(event) => onNotesChange(event.target.value)}
            />
          </label>
          <div className="modal-actions">
            <button
              className="secondary-button"
              disabled={isSubmitting}
              onClick={onClose}
              type="button"
            >
              Volver
            </button>
            <button className="danger-button" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Guardando..." : "Cancelar seguimiento"}
            </button>
          </div>
        </form>
      </section>
    </div>
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

function formatDateTimeCompact(value: string) {
  return new Intl.DateTimeFormat("es", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

"use client";

import {
  ArrowLeft,
  CalendarDays,
  CheckCircle2,
  Edit,
  Trash2,
  UserRound,
  X,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { getApiErrorMessage } from "@/lib/api";
import {
  deleteAppointment,
  getAppointment,
  updateAppointment,
} from "@/services/appointments";
import { getClinicTeam } from "@/services/clinic";
import { getOwners } from "@/services/owners";
import { getPatients } from "@/services/patients";
import type {
  Appointment,
  AppointmentStatus,
  ClinicTeamMember,
  Owner,
  Patient,
  UpdateAppointmentPayload,
} from "@/types/api";

import {
  AppointmentFormModal,
  buildAppointmentPayload,
  validateAppointmentForm,
} from "./agenda-screen";
import {
  AppointmentFormState,
  appointmentToFormState,
  formatAppointmentDate,
  formatAppointmentTimeRange,
  getAppointmentStatusLabel,
  getAppointmentTypeLabel,
  getAppointmentUserName,
  getStatusBadgeClass,
  getTypeBadgeClass,
} from "./agenda-helpers";

type AppointmentDetailProps = {
  appointmentId: string;
};

type AppointmentDetailState = {
  isLoading: boolean;
  isSaving: boolean;
  isDeleting: boolean;
  appointment: Appointment | null;
  patients: Patient[];
  owners: Owner[];
  team: ClinicTeamMember[];
  errorMessage: string | null;
  successMessage: string | null;
  flowMessage: string | null;
};

const initialState: AppointmentDetailState = {
  isLoading: true,
  isSaving: false,
  isDeleting: false,
  appointment: null,
  patients: [],
  owners: [],
  team: [],
  errorMessage: null,
  successMessage: null,
  flowMessage: null,
};

export function AppointmentDetail({ appointmentId }: AppointmentDetailProps) {
  const router = useRouter();
  const [state, setState] = useState<AppointmentDetailState>(initialState);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [formState, setFormState] = useState<AppointmentFormState | null>(null);

  const loadDetail = useCallback(async () => {
    setState((current) => ({
      ...current,
      isLoading: true,
      errorMessage: null,
    }));

    try {
      const [appointmentResponse, patientsResponse, ownersResponse, teamResponse] =
        await Promise.all([
          getAppointment(appointmentId),
          getPatients(),
          getOwners(),
          getClinicTeam(),
        ]);

      setState((current) => ({
        ...current,
        isLoading: false,
        appointment: appointmentResponse.data,
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
  }, [appointmentId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  function openEditModal() {
    if (!state.appointment) {
      return;
    }
    setFormState(appointmentToFormState(state.appointment));
    setState((current) => ({ ...current, flowMessage: null, successMessage: null }));
    setIsEditOpen(true);
  }

  function closeEditModal() {
    setIsEditOpen(false);
    setFormState(null);
    setState((current) => ({
      ...current,
      isSaving: false,
      flowMessage: null,
    }));
  }

  function handlePatientChange(patientId: string) {
    if (!formState) {
      return;
    }
    const patient = state.patients.find((item) => item.id === patientId);
    setFormState({
      ...formState,
      patient_id: patientId,
      owner_id: patient?.owner_id ?? formState.owner_id,
    });
  }

  async function handleSaveAppointment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!formState) {
      return;
    }

    const validationMessage = validateAppointmentForm(formState);
    if (validationMessage) {
      setState((current) => ({ ...current, flowMessage: validationMessage }));
      return;
    }

    const payload: UpdateAppointmentPayload = buildAppointmentPayload(formState);

    setState((current) => ({
      ...current,
      isSaving: true,
      flowMessage: null,
      successMessage: null,
    }));

    try {
      const response = await updateAppointment(appointmentId, payload);
      setState((current) => ({
        ...current,
        isSaving: false,
        appointment: response.data,
        successMessage: "Turno actualizado correctamente.",
      }));
      setIsEditOpen(false);
      setFormState(null);
    } catch (error) {
      setState((current) => ({
        ...current,
        isSaving: false,
        flowMessage: getApiErrorMessage(error),
      }));
    }
  }

  async function handleStatusChange(status: AppointmentStatus) {
    setState((current) => ({
      ...current,
      isSaving: true,
      errorMessage: null,
      successMessage: null,
    }));

    try {
      const response = await updateAppointment(appointmentId, { status });
      setState((current) => ({
        ...current,
        isSaving: false,
        appointment: response.data,
        successMessage: "Estado del turno actualizado.",
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        isSaving: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }

  async function handleDeleteAppointment() {
    setState((current) => ({
      ...current,
      isDeleting: true,
      flowMessage: null,
    }));

    try {
      await deleteAppointment(appointmentId);
      router.push("/agenda");
    } catch (error) {
      setState((current) => ({
        ...current,
        isDeleting: false,
        flowMessage: getApiErrorMessage(error),
      }));
    }
  }

  const appointment = state.appointment;

  if (state.isLoading) {
    return <div className="loading-card" aria-label="Cargando turno" />;
  }

  if (state.errorMessage && !appointment) {
    return (
      <div className="page-stack">
        <Link className="back-link" href="/agenda">
          <ArrowLeft aria-hidden="true" size={17} /> Volver a agenda
        </Link>
        <div className="error-state">{state.errorMessage}</div>
      </div>
    );
  }

  if (!appointment) {
    return (
      <div className="page-stack">
        <Link className="back-link" href="/agenda">
          <ArrowLeft aria-hidden="true" size={17} /> Volver a agenda
        </Link>
        <div className="empty-state">No encontramos este turno.</div>
      </div>
    );
  }

  const assignedUser = getAppointmentUserName(
    appointment.assigned_user_name,
    appointment.assigned_user_email,
  );
  const createdBy = getAppointmentUserName(
    appointment.created_by_user_name,
    appointment.created_by_user_email,
  );

  return (
    <div className="page-stack appointment-detail-layout">
      <section className="detail-hero">
        <Link className="back-link" href="/agenda">
          <ArrowLeft aria-hidden="true" size={17} /> Volver a agenda
        </Link>
        <div className="detail-hero__main">
          <span className="pet-avatar pet-avatar--neutral" aria-hidden="true">
            <CalendarDays size={28} />
          </span>
          <div>
            <p className="eyebrow">Turno clínico</p>
            <h1>{appointment.title}</h1>
            <p>{formatAppointmentDate(appointment.start_at)}</p>
          </div>
        </div>
        <div className="detail-hero__actions">
          <span className={getStatusBadgeClass(appointment.status)}>
            {getAppointmentStatusLabel(appointment.status)}
          </span>
          <button className="secondary-button" onClick={openEditModal} type="button">
            <Edit aria-hidden="true" size={17} />
            Editar
          </button>
        </div>
      </section>

      {state.successMessage ? <div className="success-state">{state.successMessage}</div> : null}
      {state.errorMessage ? <div className="error-state">{state.errorMessage}</div> : null}

      <section className="panel patient-detail-section">
        <div className="section-heading section-heading--row">
          <div>
            <p className="eyebrow">Detalle</p>
            <h2>Información del turno</h2>
          </div>
          <span className={getTypeBadgeClass(appointment.appointment_type)}>
            {getAppointmentTypeLabel(appointment.appointment_type)}
          </span>
        </div>

        <dl className="detail-grid">
          <div>
            <dt>Fecha</dt>
            <dd>{formatAppointmentDate(appointment.start_at)}</dd>
          </div>
          <div>
            <dt>Hora</dt>
            <dd>{formatAppointmentTimeRange(appointment)}</dd>
          </div>
          <div>
            <dt>Tipo</dt>
            <dd>{getAppointmentTypeLabel(appointment.appointment_type)}</dd>
          </div>
          <div>
            <dt>Estado</dt>
            <dd>{getAppointmentStatusLabel(appointment.status)}</dd>
          </div>
          <div>
            <dt>Paciente</dt>
            <dd>{appointment.patient_name ?? "Sin paciente vinculado"}</dd>
          </div>
          <div>
            <dt>Propietario</dt>
            <dd>{appointment.owner_name ?? "Sin propietario vinculado"}</dd>
          </div>
          <div>
            <dt>Veterinario asignado</dt>
            <dd>{assignedUser ?? "Sin asignar"}</dd>
          </div>
          <div>
            <dt>Registrado por</dt>
            <dd>{createdBy ?? "No disponible"}</dd>
          </div>
        </dl>

        {appointment.reason ? (
          <div className="clinical-section">
            <strong>Motivo</strong>
            <p className="muted-text">{appointment.reason}</p>
          </div>
        ) : null}

        {appointment.notes ? (
          <div className="clinical-section">
            <strong>Notas</strong>
            <p className="muted-text">{appointment.notes}</p>
          </div>
        ) : null}
      </section>

      <section className="panel patient-detail-section">
        <div className="section-heading">
          <p className="eyebrow">Acciones</p>
          <h2>Gestionar turno</h2>
        </div>
        <div className="detail-action-row">
          {appointment.status === "scheduled" ? (
            <>
              <button
                className="secondary-button"
                disabled={state.isSaving}
                onClick={() => void handleStatusChange("completed")}
                type="button"
              >
                <CheckCircle2 aria-hidden="true" size={17} />
                Marcar completado
              </button>
              <button
                className="secondary-button"
                disabled={state.isSaving}
                onClick={() => void handleStatusChange("cancelled")}
                type="button"
              >
                <XCircle aria-hidden="true" size={17} />
                Cancelar turno
              </button>
              <button
                className="secondary-button"
                disabled={state.isSaving}
                onClick={() => void handleStatusChange("no_show")}
                type="button"
              >
                <UserRound aria-hidden="true" size={17} />
                No asistió
              </button>
            </>
          ) : (
            <p className="panel-note">Puedes editar el turno si necesitas ajustar la información registrada.</p>
          )}
          <button className="secondary-button" onClick={openEditModal} type="button">
            <Edit aria-hidden="true" size={17} />
            Editar
          </button>
          <button
            className="secondary-button secondary-button--danger"
            onClick={() => {
              setDeleteConfirmation("");
              setState((current) => ({ ...current, flowMessage: null }));
              setIsDeleteOpen(true);
            }}
            type="button"
          >
            <Trash2 aria-hidden="true" size={17} />
            Eliminar
          </button>
        </div>
      </section>

      {isEditOpen && formState ? (
        <AppointmentFormModal
          flowMessage={state.flowMessage}
          formState={formState}
          isSubmitting={state.isSaving}
          owners={state.owners}
          patients={state.patients}
          team={state.team}
          submitLabel="Guardar cambios"
          title="Editar turno"
          onClose={closeEditModal}
          onPatientChange={handlePatientChange}
          onSubmit={handleSaveAppointment}
          onUpdateForm={setFormState}
        />
      ) : null}

      {isDeleteOpen ? (
        <div className="modal-backdrop" role="presentation">
          <section aria-labelledby="delete-appointment-title" aria-modal="true" className="bottom-sheet" role="dialog">
            <div className="bottom-sheet__header">
              <div>
                <p className="eyebrow">Eliminar turno</p>
                <h2 id="delete-appointment-title">Confirmar eliminación</h2>
              </div>
              <button aria-label="Cancelar" className="icon-button" onClick={() => setIsDeleteOpen(false)} type="button">
                <X aria-hidden="true" size={20} />
              </button>
            </div>

            <div className="danger-callout">
              <strong>Esta acción eliminará el turno de la agenda.</strong>
              <span>Esta acción no se puede deshacer.</span>
            </div>

            {state.flowMessage ? <div className="error-state">{state.flowMessage}</div> : null}

            <label className="field">
              <span>Escribe ELIMINAR para confirmar</span>
              <input
                value={deleteConfirmation}
                onChange={(event) => setDeleteConfirmation(event.target.value)}
              />
            </label>

            <div className="modal-actions">
              <button className="secondary-button" onClick={() => setIsDeleteOpen(false)} type="button">
                Cancelar
              </button>
              <button
                className="danger-button"
                disabled={state.isDeleting || deleteConfirmation !== "ELIMINAR"}
                onClick={() => void handleDeleteAppointment()}
                type="button"
              >
                {state.isDeleting ? "Eliminando..." : "Confirmar eliminación"}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}

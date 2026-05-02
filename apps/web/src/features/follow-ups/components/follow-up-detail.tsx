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
import { FollowUpFormModal } from "@/features/follow-ups/components/follow-up-form-modal";
import {
  buildFollowUpUpdatePayload,
  FollowUpFormState,
  followUpToFormState,
  getFollowUpStatusBadgeClass,
  getFollowUpStatusLabel,
  getFollowUpTypeBadgeClass,
  getFollowUpTypeLabel,
  getPatientOwnerId,
  validateFollowUpForm,
} from "@/features/follow-ups/components/follow-up-helpers";
import { getClinicTeam } from "@/services/clinic";
import {
  cancelFollowUp,
  completeFollowUp,
  deleteFollowUp,
  getFollowUp,
  updateFollowUp,
} from "@/services/follow-ups";
import { getOwners } from "@/services/owners";
import { getPatients } from "@/services/patients";
import type { ClinicTeamMember, FollowUp, Owner, Patient } from "@/types/api";

type FollowUpDetailProps = {
  followUpId: string;
};

type FollowUpDetailState = {
  isLoading: boolean;
  isSaving: boolean;
  isDeleting: boolean;
  followUp: FollowUp | null;
  patients: Patient[];
  owners: Owner[];
  team: ClinicTeamMember[];
  errorMessage: string | null;
  successMessage: string | null;
  flowMessage: string | null;
};

const initialState: FollowUpDetailState = {
  isLoading: true,
  isSaving: false,
  isDeleting: false,
  followUp: null,
  patients: [],
  owners: [],
  team: [],
  errorMessage: null,
  successMessage: null,
  flowMessage: null,
};

export function FollowUpDetail({ followUpId }: FollowUpDetailProps) {
  const router = useRouter();
  const [state, setState] = useState<FollowUpDetailState>(initialState);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isCancelOpen, setIsCancelOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [formState, setFormState] = useState<FollowUpFormState | null>(null);
  const [cancelNotes, setCancelNotes] = useState("");
  const [deleteConfirmation, setDeleteConfirmation] = useState("");

  const loadDetail = useCallback(async () => {
    setState((current) => ({
      ...current,
      isLoading: true,
      errorMessage: null,
    }));

    try {
      const [followUpResponse, patientsResponse, ownersResponse, teamResponse] =
        await Promise.all([
          getFollowUp(followUpId),
          getPatients(),
          getOwners(),
          getClinicTeam(),
        ]);

      setState((current) => ({
        ...current,
        isLoading: false,
        followUp: followUpResponse.data,
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
  }, [followUpId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  function openEditModal() {
    if (!state.followUp) {
      return;
    }

    setFormState(followUpToFormState(state.followUp));
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

    setFormState({
      ...formState,
      patient_id: patientId,
      owner_id: getPatientOwnerId(state.patients, patientId, formState.owner_id),
    });
  }

  async function handleSaveFollowUp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!formState) {
      return;
    }

    const validationMessage = validateFollowUpForm(formState, {
      teamRequired: state.team.length > 0,
    });
    if (validationMessage) {
      setState((current) => ({ ...current, flowMessage: validationMessage }));
      return;
    }

    setState((current) => ({
      ...current,
      isSaving: true,
      flowMessage: null,
      successMessage: null,
    }));

    try {
      const response = await updateFollowUp(
        followUpId,
        buildFollowUpUpdatePayload(formState),
      );
      setState((current) => ({
        ...current,
        isSaving: false,
        followUp: response.data,
        successMessage: "Seguimiento actualizado correctamente.",
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

  async function handleCompleteFollowUp() {
    if (!window.confirm("¿Marcar este seguimiento como completado?")) {
      return;
    }

    setState((current) => ({
      ...current,
      isSaving: true,
      errorMessage: null,
      successMessage: null,
    }));

    try {
      const response = await completeFollowUp(followUpId);
      setState((current) => ({
        ...current,
        isSaving: false,
        followUp: response.data,
        successMessage: "Seguimiento completado correctamente.",
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        isSaving: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }

  async function handleCancelFollowUp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setState((current) => ({
      ...current,
      isSaving: true,
      flowMessage: null,
      successMessage: null,
    }));

    try {
      const response = await cancelFollowUp(followUpId, cancelNotes.trim() || undefined);
      setState((current) => ({
        ...current,
        isSaving: false,
        followUp: response.data,
        successMessage: "Seguimiento cancelado correctamente.",
      }));
      setIsCancelOpen(false);
      setCancelNotes("");
    } catch (error) {
      setState((current) => ({
        ...current,
        isSaving: false,
        flowMessage: getApiErrorMessage(error),
      }));
    }
  }

  async function handleDeleteFollowUp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (deleteConfirmation !== "ELIMINAR") {
      return;
    }

    setState((current) => ({
      ...current,
      isDeleting: true,
      flowMessage: null,
    }));

    try {
      await deleteFollowUp(followUpId);
      router.push("/follow-ups");
    } catch (error) {
      setState((current) => ({
        ...current,
        isDeleting: false,
        flowMessage: getApiErrorMessage(error),
      }));
    }
  }

  const followUp = state.followUp;

  if (state.isLoading) {
    return <div className="loading-card" aria-label="Cargando seguimiento" />;
  }

  if (state.errorMessage && !followUp) {
    return (
      <div className="page-stack">
        <Link className="back-link" href="/follow-ups">
          <ArrowLeft aria-hidden="true" size={17} /> Volver a seguimientos
        </Link>
        <div className="error-state">{state.errorMessage}</div>
      </div>
    );
  }

  if (!followUp) {
    return (
      <div className="page-stack">
        <Link className="back-link" href="/follow-ups">
          <ArrowLeft aria-hidden="true" size={17} /> Volver a seguimientos
        </Link>
        <div className="empty-state">Seguimiento no encontrado.</div>
      </div>
    );
  }

  const assignedUser = followUp.assigned_user_name || followUp.assigned_user_email;
  const createdBy = followUp.created_by_user_name || followUp.created_by_user_email;
  const patient = state.patients.find((item) => item.id === followUp.patient_id) ?? null;
  const owner = state.owners.find((item) => item.id === followUp.owner_id) ?? null;

  return (
    <div className="page-stack">
      <section className="detail-hero">
        <Link className="back-link" href="/follow-ups">
          <ArrowLeft aria-hidden="true" size={17} /> Volver a seguimientos
        </Link>
        <div className="detail-hero__main">
          <span className="icon-bubble">
            <CalendarDays aria-hidden="true" size={24} />
          </span>
          <div>
            <h1>{followUp.title}</h1>
            <p>{getFollowUpTypeLabel(followUp.follow_up_type)}</p>
          </div>
        </div>
        <div className="detail-hero__actions">
          <span className={getFollowUpStatusBadgeClass(followUp.status)}>
            {getFollowUpStatusLabel(followUp.status)}
          </span>
          <button className="secondary-button" type="button" onClick={openEditModal}>
            <Edit aria-hidden="true" size={18} /> Editar
          </button>
        </div>
      </section>

      {state.successMessage ? <div className="success-state">{state.successMessage}</div> : null}
      {state.errorMessage ? <div className="error-state">{state.errorMessage}</div> : null}

      <section className="panel patient-detail-section">
        <div className="section-heading section-heading--row">
          <div>
            <p className="eyebrow">Seguimiento</p>
            <h2>Detalle clínico</h2>
          </div>
          <span className={getFollowUpTypeBadgeClass(followUp.follow_up_type)}>
            {getFollowUpTypeLabel(followUp.follow_up_type)}
          </span>
        </div>

        <dl className="detail-grid">
          <div>
            <dt>Fecha y hora</dt>
            <dd>{formatDateTime(followUp.due_at)}</dd>
          </div>
          <div>
            <dt>Estado</dt>
            <dd>{getFollowUpStatusLabel(followUp.status)}</dd>
          </div>
          <div>
            <dt>Paciente</dt>
            <dd>{followUp.patient_name ?? patient?.name ?? "No indicado"}</dd>
          </div>
          <div>
            <dt>Propietario</dt>
            <dd>{followUp.owner_name ?? owner?.full_name ?? "No indicado"}</dd>
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

        {followUp.description ? (
          <div className="clinical-section">
            <strong>Descripción</strong>
            <p className="panel-note">{followUp.description}</p>
          </div>
        ) : null}

        {followUp.notes ? (
          <div className="clinical-section">
            <strong>Notas</strong>
            <p className="panel-note">{followUp.notes}</p>
          </div>
        ) : null}

        {followUp.appointment_id ? (
          <div className="clinical-section">
            <strong>Turno asociado</strong>
            <div className="detail-action-row">
              <Link className="secondary-button" href={`/agenda/${followUp.appointment_id}`}>
                <CalendarDays aria-hidden="true" size={18} /> Ver turno en agenda
              </Link>
            </div>
          </div>
        ) : null}

        <div className="detail-action-row">
          <button
            className="secondary-button"
            disabled={state.isSaving || followUp.status === "completed" || followUp.status === "cancelled"}
            type="button"
            onClick={() => void handleCompleteFollowUp()}
          >
            <CheckCircle2 aria-hidden="true" size={18} /> Completar
          </button>
          <button
            className="secondary-button secondary-button--danger"
            disabled={state.isSaving || followUp.status === "cancelled"}
            type="button"
            onClick={() => setIsCancelOpen(true)}
          >
            <XCircle aria-hidden="true" size={18} /> Cancelar
          </button>
          <button
            className="secondary-button secondary-button--danger"
            disabled={state.isDeleting}
            type="button"
            onClick={() => setIsDeleteOpen(true)}
          >
            <Trash2 aria-hidden="true" size={18} /> Eliminar
          </button>
        </div>
      </section>

      {isEditOpen && formState ? (
        <FollowUpFormModal
          flowMessage={state.flowMessage}
          formState={formState}
          isSubmitting={state.isSaving}
          ownerLocked
          owners={state.owners}
          patientLocked
          patients={state.patients}
          showAppointmentOptions={false}
          submitLabel="Guardar cambios"
          team={state.team}
          title="Editar seguimiento"
          onClose={closeEditModal}
          onPatientChange={handlePatientChange}
          onSubmit={handleSaveFollowUp}
          onUpdateForm={setFormState}
        />
      ) : null}

      {isCancelOpen ? (
        <div className="modal-backdrop" role="presentation">
          <section
            aria-labelledby="follow-up-cancel-title"
            aria-modal="true"
            className="bottom-sheet"
            role="dialog"
          >
            <div className="bottom-sheet__header">
              <div>
                <p className="eyebrow">Seguimiento clínico</p>
                <h2 id="follow-up-cancel-title">Cancelar seguimiento</h2>
              </div>
              <button
                aria-label="Cerrar"
                className="icon-button"
                disabled={state.isSaving}
                onClick={() => setIsCancelOpen(false)}
                type="button"
              >
                <X aria-hidden="true" size={20} />
              </button>
            </div>

            {state.flowMessage ? <div className="error-state">{state.flowMessage}</div> : null}

            <form className="entity-form" onSubmit={handleCancelFollowUp}>
              <label className="field">
                <span>Notas de cancelación</span>
                <textarea
                  rows={4}
                  value={cancelNotes}
                  onChange={(event) => setCancelNotes(event.target.value)}
                />
              </label>
              <div className="modal-actions">
                <button
                  className="secondary-button"
                  disabled={state.isSaving}
                  onClick={() => setIsCancelOpen(false)}
                  type="button"
                >
                  Volver
                </button>
                <button className="danger-button" disabled={state.isSaving} type="submit">
                  {state.isSaving ? "Guardando..." : "Cancelar seguimiento"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}

      {isDeleteOpen ? (
        <div className="modal-backdrop" role="presentation">
          <section
            aria-labelledby="follow-up-delete-title"
            aria-modal="true"
            className="bottom-sheet"
            role="dialog"
          >
            <div className="bottom-sheet__header">
              <div>
                <p className="eyebrow">Acción irreversible</p>
                <h2 id="follow-up-delete-title">Eliminar seguimiento</h2>
              </div>
              <button
                aria-label="Cerrar"
                className="icon-button"
                disabled={state.isDeleting}
                onClick={() => setIsDeleteOpen(false)}
                type="button"
              >
                <X aria-hidden="true" size={20} />
              </button>
            </div>

            {state.flowMessage ? <div className="error-state">{state.flowMessage}</div> : null}

            <div className="danger-callout" role="alert">
              <strong>{followUp.title}</strong>
              <span>
                Esta acción eliminará el seguimiento. No eliminará el turno asociado en la
                agenda.
              </span>
            </div>

            <form className="entity-form" onSubmit={handleDeleteFollowUp}>
              <label className="field">
                <span>Escribe ELIMINAR para confirmar</span>
                <input
                  autoComplete="off"
                  value={deleteConfirmation}
                  onChange={(event) => setDeleteConfirmation(event.target.value)}
                />
              </label>
              <div className="modal-actions">
                <button
                  className="secondary-button"
                  disabled={state.isDeleting}
                  onClick={() => setIsDeleteOpen(false)}
                  type="button"
                >
                  Cancelar
                </button>
                <button
                  className="danger-button"
                  disabled={deleteConfirmation !== "ELIMINAR" || state.isDeleting}
                  type="submit"
                >
                  {state.isDeleting ? "Eliminando..." : "Confirmar eliminación"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </div>
  );
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("es", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

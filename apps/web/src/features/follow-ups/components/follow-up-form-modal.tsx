"use client";

import { X } from "lucide-react";
import type { FormEvent } from "react";

import type { ClinicTeamMember, FollowUpStatus, FollowUpType, Owner, Patient } from "@/types/api";

import {
  FollowUpFormState,
  followUpDurationOptions,
  followUpStatusOptions,
  followUpTypeOptions,
  getFollowUpTypeLabel,
} from "./follow-up-helpers";

type FollowUpFormModalProps = {
  title: string;
  submitLabel: string;
  formState: FollowUpFormState;
  patients: Patient[];
  owners: Owner[];
  team: ClinicTeamMember[];
  isSubmitting: boolean;
  flowMessage: string | null;
  patientLocked?: boolean;
  ownerLocked?: boolean;
  showAppointmentOptions?: boolean;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onUpdateForm: (nextState: FollowUpFormState) => void;
  onPatientChange: (patientId: string) => void;
};

export function FollowUpFormModal({
  title,
  submitLabel,
  formState,
  patients,
  owners,
  team,
  isSubmitting,
  flowMessage,
  patientLocked = false,
  ownerLocked = false,
  showAppointmentOptions = true,
  onClose,
  onSubmit,
  onUpdateForm,
  onPatientChange,
}: FollowUpFormModalProps) {
  const selectedPatient = patients.find((patient) => patient.id === formState.patient_id);
  const selectedOwner = owners.find((owner) => owner.id === formState.owner_id);
  const teamRequired = team.length > 0;

  return (
    <div className="modal-backdrop" role="presentation">
      <section
        aria-labelledby="follow-up-form-title"
        aria-modal="true"
        className="bottom-sheet"
        role="dialog"
      >
        <div className="bottom-sheet__header">
          <div>
            <p className="eyebrow">Seguimiento clínico</p>
            <h2 id="follow-up-form-title">{title}</h2>
          </div>
          <button
            aria-label="Cancelar"
            className="icon-button"
            disabled={isSubmitting}
            onClick={onClose}
            type="button"
          >
            <X aria-hidden="true" size={20} />
          </button>
        </div>

        {flowMessage ? <div className="error-state">{flowMessage}</div> : null}

        <form className="entity-form" onSubmit={onSubmit}>
          <label className="field">
            <span>Paciente *</span>
            {patientLocked && selectedPatient ? (
              <input
                readOnly
                value={`${selectedPatient.name} · ${selectedPatient.species}`}
              />
            ) : (
              <select
                required
                value={formState.patient_id}
                onChange={(event) => onPatientChange(event.target.value)}
              >
                <option value="">Selecciona un paciente</option>
                {patients.map((patient) => (
                  <option key={patient.id} value={patient.id}>
                    {patient.name} · {patient.species}
                  </option>
                ))}
              </select>
            )}
          </label>

          <label className="field">
            <span>Propietario</span>
            {ownerLocked && selectedOwner ? (
              <input readOnly value={`${selectedOwner.full_name} · ${selectedOwner.phone}`} />
            ) : (
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
            )}
          </label>

          {selectedOwner ? (
            <p className="panel-note">Propietario seleccionado: {selectedOwner.full_name}</p>
          ) : null}

          <label className="field">
            <span>Veterinario asignado{teamRequired ? " *" : ""}</span>
            <select
              required={teamRequired}
              value={formState.assigned_user_id}
              onChange={(event) =>
                onUpdateForm({ ...formState, assigned_user_id: event.target.value })
              }
            >
              <option value="">{teamRequired ? "Selecciona un veterinario" : "Sin asignar"}</option>
              {team.map((member) => (
                <option key={member.id} value={member.id}>
                  {member.full_name}
                </option>
              ))}
            </select>
          </label>

          {team.length === 0 ? (
            <p className="panel-note">No hay equipo activo disponible para asignar.</p>
          ) : null}

          <div className="form-grid">
            <label className="field">
              <span>Tipo *</span>
              <select
                required
                value={formState.follow_up_type}
                onChange={(event) => {
                  const nextType = event.target.value as FollowUpType;
                  const nextTitle =
                    formState.title.trim() === "" ||
                    followUpTypeOptions.some(
                      (option) =>
                        option.defaultTitle === formState.title &&
                        option.value !== nextType,
                    )
                      ? followUpTypeOptions.find((option) => option.value === nextType)
                          ?.defaultTitle ?? formState.title
                      : formState.title;

                  onUpdateForm({
                    ...formState,
                    follow_up_type: nextType,
                    title: nextTitle,
                  });
                }}
              >
                {followUpTypeOptions.map((option) => (
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
                    status: event.target.value as FollowUpStatus,
                  })
                }
              >
                {followUpStatusOptions.map((option) => (
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
              <span>Hora *</span>
              <input
                required
                type="time"
                value={formState.time}
                onChange={(event) => onUpdateForm({ ...formState, time: event.target.value })}
              />
            </label>
          </div>

          <label className="field">
            <span>Título *</span>
            <input
              required
              placeholder={getFollowUpTypeLabel(formState.follow_up_type)}
              value={formState.title}
              onChange={(event) => onUpdateForm({ ...formState, title: event.target.value })}
            />
          </label>

          <label className="field">
            <span>Descripción</span>
            <textarea
              rows={3}
              value={formState.description}
              onChange={(event) =>
                onUpdateForm({ ...formState, description: event.target.value })
              }
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

          {showAppointmentOptions ? (
            <div className="clinical-toggle-card">
              <label className="checkbox-row">
                <input
                  checked={formState.create_appointment}
                  type="checkbox"
                  onChange={(event) =>
                    onUpdateForm({
                      ...formState,
                      create_appointment: event.target.checked,
                    })
                  }
                />
                <span>Crear turno en agenda</span>
              </label>

              {formState.create_appointment ? (
                <label className="field">
                  <span>Duración del turno</span>
                  <select
                    value={String(formState.appointment_duration_minutes)}
                    onChange={(event) =>
                      onUpdateForm({
                        ...formState,
                        appointment_duration_minutes: Number(event.target.value),
                      })
                    }
                  >
                    {followUpDurationOptions.map((minutes) => (
                      <option key={minutes} value={minutes}>
                        {minutes} min
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
            </div>
          ) : null}

          <div className="modal-actions">
            <button
              className="secondary-button"
              disabled={isSubmitting}
              onClick={onClose}
              type="button"
            >
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

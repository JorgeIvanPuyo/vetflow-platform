"use client";

import { Mail, Stethoscope, Users, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { useClinic } from "@/features/clinic/clinic-context";
import { getApiErrorMessage } from "@/lib/api";
import {
  getClinicProfile,
  getClinicTeam,
  updateClinicProfile,
} from "@/services/clinic";
import type {
  ClinicProfile,
  ClinicTeamMember,
  UpdateClinicProfilePayload,
} from "@/types/api";

type SettingsState = {
  isLoading: boolean;
  isSaving: boolean;
  profile: ClinicProfile | null;
  team: ClinicTeamMember[];
  errorMessage: string | null;
  successMessage: string | null;
  flowMessage: string | null;
};

type ClinicProfileFormState = {
  display_name: string;
  phone: string;
  email: string;
  address: string;
  notes: string;
  logo_url: string;
};

const initialState: SettingsState = {
  isLoading: true,
  isSaving: false,
  profile: null,
  team: [],
  errorMessage: null,
  successMessage: null,
  flowMessage: null,
};

const initialFormState: ClinicProfileFormState = {
  display_name: "",
  phone: "",
  email: "",
  address: "",
  notes: "",
  logo_url: "",
};

export function SettingsScreen() {
  const { refreshProfile } = useClinic();
  const [state, setState] = useState<SettingsState>(initialState);
  const [formState, setFormState] = useState<ClinicProfileFormState>(initialFormState);
  const [isTeamOpen, setIsTeamOpen] = useState(false);

  async function loadSettings() {
    setState((current) => ({
      ...current,
      isLoading: true,
      errorMessage: null,
    }));

    try {
      const [profileResponse, teamResponse] = await Promise.all([
        getClinicProfile(),
        getClinicTeam(),
      ]);
      const profile = profileResponse.data;
      setState((current) => ({
        ...current,
        isLoading: false,
        profile,
        team: teamResponse.data,
      }));
      setFormState(profileToFormState(profile));
    } catch (error) {
      setState((current) => ({
        ...current,
        isLoading: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }

  useEffect(() => {
    void loadSettings();
  }, []);

  function resetForm() {
    if (state.profile) {
      setFormState(profileToFormState(state.profile));
    }
    setState((current) => ({
      ...current,
      flowMessage: null,
      successMessage: null,
    }));
  }

  async function handleSaveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (formState.email.trim() && !isValidEmail(formState.email.trim())) {
      setState((current) => ({
        ...current,
        flowMessage: "Ingresa un email válido para la clínica.",
        successMessage: null,
      }));
      return;
    }

    setState((current) => ({
      ...current,
      isSaving: true,
      flowMessage: null,
      successMessage: null,
    }));

    try {
      const response = await updateClinicProfile(buildProfilePayload(formState));
      setState((current) => ({
        ...current,
        isSaving: false,
        profile: response.data,
        successMessage: "Perfil de clínica actualizado.",
      }));
      setFormState(profileToFormState(response.data));
      await refreshProfile();
    } catch (error) {
      setState((current) => ({
        ...current,
        isSaving: false,
        flowMessage: getApiErrorMessage(error),
      }));
    }
  }

  return (
    <div className="page-stack settings-layout">
      <section className="screen-heading">
        <p className="eyebrow">Clínica</p>
        <h1>Ajustes</h1>
        <p>Configuración de clínica</p>
      </section>

      {state.isLoading ? <div className="loading-card" aria-label="Cargando ajustes" /> : null}
      {state.errorMessage ? <div className="error-state">{state.errorMessage}</div> : null}
      {state.successMessage ? <div className="success-state">{state.successMessage}</div> : null}

      {!state.isLoading && state.profile ? (
        <>
          <section className="panel patient-detail-section">
            <div className="section-heading section-heading--row">
              <div>
                <p className="eyebrow">Perfil</p>
                <h2>Perfil de clínica</h2>
                <p>Datos visibles para documentos, agenda y futuras comunicaciones.</p>
              </div>
              <span className="brand__mark" aria-hidden="true">
                {state.profile.logo_url ? (
                  <>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img alt="" src={state.profile.logo_url} />
                  </>
                ) : (
                  <Stethoscope size={20} />
                )}
              </span>
            </div>

            {state.flowMessage ? <div className="error-state">{state.flowMessage}</div> : null}

            <form className="entity-form" onSubmit={handleSaveProfile}>
              <div className="form-grid">
                <label className="field">
                  <span>Nombre visible</span>
                  <input
                    value={formState.display_name}
                    placeholder={state.profile.name}
                    onChange={(event) =>
                      setFormState((current) => ({
                        ...current,
                        display_name: event.target.value,
                      }))
                    }
                  />
                </label>

                <label className="field">
                  <span>Teléfono</span>
                  <input
                    value={formState.phone}
                    onChange={(event) =>
                      setFormState((current) => ({
                        ...current,
                        phone: event.target.value,
                      }))
                    }
                  />
                </label>

                <label className="field">
                  <span>Email</span>
                  <input
                    inputMode="email"
                    value={formState.email}
                    onChange={(event) =>
                      setFormState((current) => ({
                        ...current,
                        email: event.target.value,
                      }))
                    }
                  />
                </label>

                <label className="field">
                  <span>Logo URL</span>
                  <input
                    value={formState.logo_url}
                    placeholder="https://..."
                    onChange={(event) =>
                      setFormState((current) => ({
                        ...current,
                        logo_url: event.target.value,
                      }))
                    }
                  />
                </label>
              </div>

              <label className="field">
                <span>Dirección</span>
                <textarea
                  rows={2}
                  value={formState.address}
                  onChange={(event) =>
                    setFormState((current) => ({
                      ...current,
                      address: event.target.value,
                    }))
                  }
                />
              </label>

              <label className="field">
                <span>Notas</span>
                <textarea
                  rows={3}
                  value={formState.notes}
                  onChange={(event) =>
                    setFormState((current) => ({
                      ...current,
                      notes: event.target.value,
                    }))
                  }
                />
              </label>

              <div className="modal-actions">
                <button className="secondary-button" onClick={resetForm} type="button">
                  Cancelar
                </button>
                <button className="primary-button" disabled={state.isSaving} type="submit">
                  {state.isSaving ? "Guardando..." : "Guardar cambios"}
                </button>
              </div>
            </form>
          </section>

          <section className="panel patient-detail-section">
            <div className="section-heading section-heading--row">
              <div>
                <p className="eyebrow">Equipo</p>
                <h2>Equipo de clínica</h2>
                <p>Veterinarios activos disponibles para asignar turnos.</p>
              </div>
              <button className="secondary-button" onClick={() => setIsTeamOpen(true)} type="button">
                <Users aria-hidden="true" size={18} />
                Ver equipo
              </button>
            </div>

            {state.team.length === 0 ? (
              <div className="empty-state">No hay integrantes registrados.</div>
            ) : (
              <div className="clinic-team-preview">
                {state.team.slice(0, 3).map((member) => (
                  <span className="badge badge--success" key={member.id}>
                    {member.full_name}
                  </span>
                ))}
                {state.team.length > 3 ? (
                  <span className="badge">+{state.team.length - 3}</span>
                ) : null}
              </div>
            )}
          </section>
        </>
      ) : null}

      {isTeamOpen ? (
        <div className="modal-backdrop" role="presentation">
          <section aria-labelledby="clinic-team-title" aria-modal="true" className="bottom-sheet" role="dialog">
            <div className="bottom-sheet__header">
              <div>
                <p className="eyebrow">Equipo</p>
                <h2 id="clinic-team-title">Equipo de clínica</h2>
              </div>
              <button aria-label="Cerrar" className="icon-button" onClick={() => setIsTeamOpen(false)} type="button">
                <X aria-hidden="true" size={20} />
              </button>
            </div>

            {state.team.length === 0 ? (
              <div className="empty-state">No hay integrantes registrados.</div>
            ) : (
              <section className="record-card-list" aria-label="Lista de veterinarios">
                {state.team.map((member) => (
                  <article className="record-card clinic-team-card" key={member.id}>
                    <span className="pet-avatar pet-avatar--neutral" aria-hidden="true">
                      <Users size={22} />
                    </span>
                    <div>
                      <div className="record-card__title-row">
                        <h3>{member.full_name}</h3>
                        <span className="badge badge--success">Activo</span>
                      </div>
                      <p>
                        <Mail aria-hidden="true" size={15} /> {member.email}
                      </p>
                    </div>
                  </article>
                ))}
              </section>
            )}
          </section>
        </div>
      ) : null}
    </div>
  );
}

function profileToFormState(profile: ClinicProfile): ClinicProfileFormState {
  return {
    display_name: profile.display_name ?? "",
    phone: profile.phone ?? "",
    email: profile.email ?? "",
    address: profile.address ?? "",
    notes: profile.notes ?? "",
    logo_url: profile.logo_url ?? "",
  };
}

function buildProfilePayload(
  formState: ClinicProfileFormState,
): UpdateClinicProfilePayload {
  return {
    display_name: normalizeNullable(formState.display_name),
    phone: normalizeNullable(formState.phone),
    email: normalizeNullable(formState.email),
    address: normalizeNullable(formState.address),
    notes: normalizeNullable(formState.notes),
    logo_url: normalizeNullable(formState.logo_url),
  };
}

function normalizeNullable(value: string) {
  const trimmed = value.trim();
  return trimmed || null;
}

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

"use client";

import { Image as ImageIcon, Mail, Trash2, Upload, Users, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { useClinic } from "@/features/clinic/clinic-context";
import { getApiErrorMessage } from "@/lib/api";
import {
  deleteClinicLogo,
  getClinicProfile,
  getClinicTeam,
  updateClinicProfile,
  uploadClinicLogo,
} from "@/services/clinic";
import type {
  ClinicProfile,
  ClinicTeamMember,
  UpdateClinicProfilePayload,
} from "@/types/api";

type SettingsState = {
  isLoading: boolean;
  isSaving: boolean;
  isLogoUploading: boolean;
  isLogoDeleting: boolean;
  profile: ClinicProfile | null;
  team: ClinicTeamMember[];
  errorMessage: string | null;
  successMessage: string | null;
  flowMessage: string | null;
  logoMessage: string | null;
};

type ClinicProfileFormState = {
  display_name: string;
  phone: string;
  email: string;
  address: string;
  notes: string;
};

const initialState: SettingsState = {
  isLoading: true,
  isSaving: false,
  isLogoUploading: false,
  isLogoDeleting: false,
  profile: null,
  team: [],
  errorMessage: null,
  successMessage: null,
  flowMessage: null,
  logoMessage: null,
};

const initialFormState: ClinicProfileFormState = {
  display_name: "",
  phone: "",
  email: "",
  address: "",
  notes: "",
};

const allowedLogoTypes = ["image/png", "image/jpeg", "image/webp"];
const maxLogoSizeBytes = 5 * 1024 * 1024;

export function SettingsScreen() {
  const { refreshProfile } = useClinic();
  const [state, setState] = useState<SettingsState>(initialState);
  const [formState, setFormState] = useState<ClinicProfileFormState>(initialFormState);
  const [selectedLogoFile, setSelectedLogoFile] = useState<File | null>(null);
  const [logoPreviewUrl, setLogoPreviewUrl] = useState<string | null>(null);
  const [isTeamOpen, setIsTeamOpen] = useState(false);
  const [isLogoDeleteOpen, setIsLogoDeleteOpen] = useState(false);

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

  useEffect(() => {
    if (!selectedLogoFile) {
      setLogoPreviewUrl(null);
      return;
    }

    const objectUrl = URL.createObjectURL(selectedLogoFile);
    setLogoPreviewUrl(objectUrl);

    return () => URL.revokeObjectURL(objectUrl);
  }, [selectedLogoFile]);

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

  function handleLogoSelection(file: File | null) {
    if (!file) {
      setSelectedLogoFile(null);
      setState((current) => ({ ...current, logoMessage: null }));
      return;
    }

    const validationMessage = validateLogoFile(file);
    if (validationMessage) {
      setSelectedLogoFile(null);
      setState((current) => ({ ...current, logoMessage: validationMessage }));
      return;
    }

    setSelectedLogoFile(file);
    setState((current) => ({ ...current, logoMessage: null, successMessage: null }));
  }

  async function handleUploadLogo() {
    if (!selectedLogoFile) {
      setState((current) => ({
        ...current,
        logoMessage: "Selecciona un archivo de logo para subir.",
      }));
      return;
    }

    setState((current) => ({
      ...current,
      isLogoUploading: true,
      logoMessage: null,
      successMessage: null,
    }));

    try {
      const response = await uploadClinicLogo(selectedLogoFile);
      setSelectedLogoFile(null);
      setState((current) => ({
        ...current,
        isLogoUploading: false,
        profile: response.data,
        successMessage: "Logo de clínica actualizado.",
      }));
      await refreshProfile();
    } catch (error) {
      setState((current) => ({
        ...current,
        isLogoUploading: false,
        logoMessage: getApiErrorMessage(error),
      }));
    }
  }

  async function handleDeleteLogo() {
    setState((current) => ({
      ...current,
      isLogoDeleting: true,
      logoMessage: null,
      successMessage: null,
    }));

    try {
      const response = await deleteClinicLogo();
      setSelectedLogoFile(null);
      setIsLogoDeleteOpen(false);
      setState((current) => ({
        ...current,
        isLogoDeleting: false,
        profile: response.data,
        successMessage: "Logo de clínica eliminado.",
      }));
      await refreshProfile();
    } catch (error) {
      setState((current) => ({
        ...current,
        isLogoDeleting: false,
        logoMessage: getApiErrorMessage(error),
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
            </div>

            {state.flowMessage ? <div className="error-state">{state.flowMessage}</div> : null}

            <section className="clinic-logo-manager" aria-label="Logo de clínica">
              <div className="clinic-logo-preview">
                {logoPreviewUrl || state.profile.logo_url ? (
                  <>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      alt="Logo de la clínica"
                      src={logoPreviewUrl ?? state.profile.logo_url ?? ""}
                    />
                  </>
                ) : (
                  <span className="clinic-logo-placeholder" aria-hidden="true">
                    <ImageIcon size={30} />
                  </span>
                )}
              </div>

              <div className="clinic-logo-manager__body">
                <div>
                  <p className="eyebrow">Branding</p>
                  <h3>Logo de la clínica</h3>
                  <p className="muted-text">
                    Usa PNG, JPG o WebP. Tamaño máximo: 5 MB.
                  </p>
                </div>

                {selectedLogoFile ? (
                  <div className="selected-file-summary">
                    <span>{selectedLogoFile.name}</span>
                    <span>{formatLogoSize(selectedLogoFile.size)}</span>
                  </div>
                ) : null}

                {state.logoMessage ? <div className="error-state">{state.logoMessage}</div> : null}

                <div className="clinic-logo-actions">
                  <label className="secondary-button clinic-logo-file-button">
                    <Upload aria-hidden="true" size={17} />
                    {state.profile.logo_url ? "Reemplazar logo" : "Subir logo"}
                    <input
                      accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
                      className="sr-only"
                      type="file"
                      onChange={(event) => {
                        handleLogoSelection(event.target.files?.[0] ?? null);
                        event.target.value = "";
                      }}
                    />
                  </label>

                  <button
                    className="primary-button"
                    disabled={!selectedLogoFile || state.isLogoUploading}
                    onClick={() => void handleUploadLogo()}
                    type="button"
                  >
                    {state.isLogoUploading ? "Subiendo logo..." : "Guardar logo"}
                  </button>

                  {state.profile.logo_url ? (
                    <button
                      className="secondary-button secondary-button--danger"
                      disabled={state.isLogoDeleting}
                      onClick={() => {
                        setState((current) => ({ ...current, logoMessage: null }));
                        setIsLogoDeleteOpen(true);
                      }}
                      type="button"
                    >
                      <Trash2 aria-hidden="true" size={17} />
                      Eliminar logo
                    </button>
                  ) : null}
                </div>
              </div>
            </section>

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

      {isLogoDeleteOpen ? (
        <div className="modal-backdrop" role="presentation">
          <section aria-labelledby="delete-logo-title" aria-modal="true" className="bottom-sheet" role="dialog">
            <div className="bottom-sheet__header">
              <div>
                <p className="eyebrow">Logo</p>
                <h2 id="delete-logo-title">Eliminar logo</h2>
              </div>
              <button aria-label="Cerrar" className="icon-button" onClick={() => setIsLogoDeleteOpen(false)} type="button">
                <X aria-hidden="true" size={20} />
              </button>
            </div>

            <div className="danger-callout">
              <strong>Esta acción eliminará el logo de la clínica.</strong>
              <span>El encabezado volverá a usar el ícono predeterminado.</span>
            </div>

            {state.logoMessage ? <div className="error-state">{state.logoMessage}</div> : null}

            <div className="modal-actions">
              <button className="secondary-button" onClick={() => setIsLogoDeleteOpen(false)} type="button">
                Cancelar
              </button>
              <button
                className="danger-button"
                disabled={state.isLogoDeleting}
                onClick={() => void handleDeleteLogo()}
                type="button"
              >
                {state.isLogoDeleting ? "Eliminando..." : "Eliminar logo"}
              </button>
            </div>
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
  };
}

function normalizeNullable(value: string) {
  const trimmed = value.trim();
  return trimmed || null;
}

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function validateLogoFile(file: File) {
  if (!allowedLogoTypes.includes(file.type)) {
    return "El logo debe ser una imagen PNG, JPG o WebP.";
  }

  if (file.size > maxLogoSizeBytes) {
    return "El logo no puede superar 5 MB.";
  }

  return null;
}

function formatLogoSize(sizeBytes: number) {
  if (sizeBytes >= 1024 * 1024) {
    return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  return `${Math.max(1, Math.round(sizeBytes / 1024))} KB`;
}

"use client";

import {
  Building2,
  CalendarClock,
  ChevronDown,
  ChevronUp,
  ClipboardList,
  Image as ImageIcon,
  Mail,
  MapPin,
  Pencil,
  Power,
  PowerOff,
  ReceiptText,
  Trash2,
  Upload,
  Users,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";

import { useCurrentUser } from "@/features/auth/current-user-context";
import { useClinic } from "@/features/clinic/clinic-context";
import { ClinicalCatalogsSection } from "@/features/clinic/components/clinical-catalogs-section";
import { InventoryCatalogsSection } from "@/features/clinic/components/inventory-catalogs-section";
import { SpeciesCatalogSection } from "@/features/clinic/components/species-catalog-section";
import { SuppliersSection } from "@/features/clinic/components/suppliers-section";
import { ApiClientError, getApiErrorMessage } from "@/lib/api";
import {
  deleteClinicLogo,
  getClinicProfile,
  getClinicTeam,
  getClinicConfiguration,
  updateClinicPreferences,
  updateClinicProfile,
  updateClinicTeamMember,
  uploadClinicLogo,
} from "@/services/clinic";
import {
  activateService,
  createService,
  deactivateService,
  reorderServices,
  restoreServiceDefaults,
  updateService,
} from "@/services/services";
import type {
  ClinicService as ClinicServiceItem,
  ClinicServiceKind,
  ClinicProfile,
  ClinicTeamMember,
  CreateClinicServicePayload,
  TenantPreferences,
  UpdateClinicProfilePayload,
} from "@/types/api";

type SettingsState = {
  isLoading: boolean;
  isSaving: boolean;
  isLogoUploading: boolean;
  isLogoDeleting: boolean;
  profile: ClinicProfile | null;
  preferences: TenantPreferences | null;
  services: ClinicServiceItem[];
  team: ClinicTeamMember[];
  errorMessage: string | null;
  successMessage: string | null;
  flowMessage: string | null;
  logoMessage: string | null;
  catalogMessage: string | null;
};

type ClinicProfileFormState = {
  display_name: string;
  phone: string;
  email: string;
  address: string;
  notes: string;
};

type PreferencesFormState = {
  currency_code: "USD" | "ARS";
  locale: "es-PA" | "es-AR";
  default_appointment_duration_minutes: string;
  appointment_duration_options: string;
  default_purchase_tax_rate: string;
  default_sale_tax_rate: string;
  default_profit_margin: string;
  money_rounding_increment: string;
};

type ServiceFormState = {
  id: string | null;
  code: string;
  name: string;
  description: string;
  kind: ClinicServiceKind;
  default_duration_minutes: string;
  calendar_color: string;
  is_bookable: boolean;
  sort_order: string;
};

const initialState: SettingsState = {
  isLoading: true,
  isSaving: false,
  isLogoUploading: false,
  isLogoDeleting: false,
  profile: null,
  preferences: null,
  services: [],
  team: [],
  errorMessage: null,
  successMessage: null,
  flowMessage: null,
  logoMessage: null,
  catalogMessage: null,
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
const serviceKindOptions: Array<{ value: ClinicServiceKind; label: string }> = [
  { value: "consultation", label: "Consulta" },
  { value: "follow_up", label: "Control" },
  { value: "vaccine", label: "Vacuna" },
  { value: "deworming", label: "Desparasitación" },
  { value: "exam", label: "Examen" },
  { value: "procedure", label: "Procedimiento" },
  { value: "other", label: "Otro" },
];

export function SettingsScreen() {
  const { refreshProfile, refreshPreferences } = useClinic();
  const { role } = useCurrentUser();
  const [state, setState] = useState<SettingsState>(initialState);
  const [formState, setFormState] = useState<ClinicProfileFormState>(initialFormState);
  const [preferencesFormState, setPreferencesFormState] =
    useState<PreferencesFormState | null>(null);
  const [serviceFormState, setServiceFormState] = useState<ServiceFormState | null>(null);
  const [selectedLogoFile, setSelectedLogoFile] = useState<File | null>(null);
  const [logoPreviewUrl, setLogoPreviewUrl] = useState<string | null>(null);
  const [expandedSettingsSections, setExpandedSettingsSections] = useState<Record<string, boolean>>({});
  const [isTeamOpen, setIsTeamOpen] = useState(false);
  const [editingTeamMember, setEditingTeamMember] = useState<ClinicTeamMember | null>(null);
  const [teamEditName, setTeamEditName] = useState("");
  const [isTeamMemberSaving, setIsTeamMemberSaving] = useState(false);
  const [teamEditMessage, setTeamEditMessage] = useState<string | null>(null);
  const [isLogoDeleteOpen, setIsLogoDeleteOpen] = useState(false);
  const canManageCatalog = role === "clinic_admin";

  async function loadSettings() {
    setState((current) => ({
      ...current,
      isLoading: true,
      errorMessage: null,
    }));

    try {
      const [profileResponse, teamResponse, configurationResponse] = await Promise.all([
        getClinicProfile(),
        getClinicTeam(),
        getClinicConfiguration("preferences,services"),
      ]);
      const profile = profileResponse.data;
      const preferences = configurationResponse.data.preferences ?? null;
      setState((current) => ({
        ...current,
        isLoading: false,
        profile,
        preferences,
        services: configurationResponse.data.services ?? [],
        team: teamResponse.data,
      }));
      setFormState(profileToFormState(profile));
      if (preferences) {
        setPreferencesFormState(preferencesToFormState(preferences));
      }
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

  function toggleSettingsSection(section: string) {
    setExpandedSettingsSections((current) => ({
      ...current,
      [section]: !current[section],
    }));
  }

  function openTeamMemberEditor(member: ClinicTeamMember) {
    setEditingTeamMember(member);
    setTeamEditName(member.full_name);
    setTeamEditMessage(null);
    setState((current) => ({ ...current, successMessage: null }));
  }

  function closeTeamMemberEditor() {
    setEditingTeamMember(null);
    setTeamEditName("");
    setTeamEditMessage(null);
  }

  async function handleSaveTeamMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!editingTeamMember) {
      return;
    }

    const trimmedName = teamEditName.trim();
    if (trimmedName.length < 2) {
      setTeamEditMessage("Ingresa un nombre válido para el veterinario.");
      return;
    }

    if (trimmedName.length > 255) {
      setTeamEditMessage("El nombre no puede superar 255 caracteres.");
      return;
    }

    setIsTeamMemberSaving(true);
    setTeamEditMessage(null);

    try {
      const response = await updateClinicTeamMember(editingTeamMember.id, {
        full_name: trimmedName,
      });
      setState((current) => ({
        ...current,
        team: current.team.map((member) =>
          member.id === response.data.id ? response.data : member,
        ),
        successMessage: "Nombre del veterinario actualizado.",
      }));
      setIsTeamMemberSaving(false);
      closeTeamMemberEditor();
    } catch (error) {
      setIsTeamMemberSaving(false);
      setTeamEditMessage(getTeamMemberUpdateErrorMessage(error));
    }
  }

  async function handleSavePreferences(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!preferencesFormState || !canManageCatalog) {
      return;
    }

    const durationOptions = parseDurationOptions(
      preferencesFormState.appointment_duration_options,
    );
    if (durationOptions.length === 0) {
      setState((current) => ({
        ...current,
        catalogMessage: "Ingresa al menos una duración válida.",
      }));
      return;
    }

    const defaultDuration = Number(
      preferencesFormState.default_appointment_duration_minutes,
    );
    if (!durationOptions.includes(defaultDuration)) {
      setState((current) => ({
        ...current,
        catalogMessage: "La duración predeterminada debe estar en las opciones.",
      }));
      return;
    }

    setState((current) => ({
      ...current,
      isSaving: true,
      catalogMessage: null,
      successMessage: null,
    }));

    try {
      const response = await updateClinicPreferences({
        currency_code: preferencesFormState.currency_code,
        locale: preferencesFormState.locale,
        default_appointment_duration_minutes: defaultDuration,
        appointment_duration_options: durationOptions,
        default_purchase_tax_rate: Number(preferencesFormState.default_purchase_tax_rate),
        default_sale_tax_rate: Number(preferencesFormState.default_sale_tax_rate),
        default_profit_margin: Number(preferencesFormState.default_profit_margin),
        money_rounding_increment: Number(preferencesFormState.money_rounding_increment),
      });
      setState((current) => ({
        ...current,
        isSaving: false,
        preferences: response.data,
        successMessage: "Preferencias actualizadas.",
      }));
      setPreferencesFormState(preferencesToFormState(response.data));
      void refreshPreferences();
    } catch (error) {
      setState((current) => ({
        ...current,
        isSaving: false,
        catalogMessage: getApiErrorMessage(error),
      }));
    }
  }

  function openNewServiceForm() {
    setServiceFormState(getInitialServiceFormState(state.services.length + 1));
    setState((current) => ({ ...current, catalogMessage: null, successMessage: null }));
  }

  function openEditServiceForm(service: ClinicServiceItem) {
    setServiceFormState(serviceToFormState(service));
    setState((current) => ({ ...current, catalogMessage: null, successMessage: null }));
  }

  async function handleSaveService(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!serviceFormState || !canManageCatalog) {
      return;
    }

    const validationMessage = validateServiceForm(serviceFormState);
    if (validationMessage) {
      setState((current) => ({ ...current, catalogMessage: validationMessage }));
      return;
    }

    setState((current) => ({
      ...current,
      isSaving: true,
      catalogMessage: null,
      successMessage: null,
    }));

    try {
      const payload = buildServicePayload(serviceFormState);
      const response = serviceFormState.id
        ? await updateService(serviceFormState.id, payload)
        : await createService(payload);
      setState((current) => ({
        ...current,
        isSaving: false,
        services: upsertService(current.services, response.data),
        successMessage: serviceFormState.id ? "Servicio actualizado." : "Servicio creado.",
      }));
      setServiceFormState(null);
    } catch (error) {
      setState((current) => ({
        ...current,
        isSaving: false,
        catalogMessage: getApiErrorMessage(error),
      }));
    }
  }

  async function handleToggleService(service: ClinicServiceItem) {
    if (!canManageCatalog) {
      return;
    }

    setState((current) => ({
      ...current,
      isSaving: true,
      catalogMessage: null,
      successMessage: null,
    }));

    try {
      const response = service.is_active
        ? await deactivateService(service.id)
        : await activateService(service.id);
      setState((current) => ({
        ...current,
        isSaving: false,
        services: upsertService(current.services, response.data),
        successMessage: response.data.is_active
          ? "Servicio activado."
          : "Servicio desactivado.",
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        isSaving: false,
        catalogMessage: getApiErrorMessage(error),
      }));
    }
  }

  async function handleMoveService(service: ClinicServiceItem, direction: -1 | 1) {
    if (!canManageCatalog) {
      return;
    }
    const ordered = [...state.services].sort((a, b) => a.sort_order - b.sort_order);
    const currentIndex = ordered.findIndex((item) => item.id === service.id);
    const targetIndex = currentIndex + direction;
    if (currentIndex < 0 || targetIndex < 0 || targetIndex >= ordered.length) {
      return;
    }
    const next = [...ordered];
    const [moved] = next.splice(currentIndex, 1);
    next.splice(targetIndex, 0, moved);

    setState((current) => ({
      ...current,
      isSaving: true,
      catalogMessage: null,
      successMessage: null,
    }));

    try {
      const response = await reorderServices(
        next.map((item, index) => ({
          id: item.id,
          sort_order: (index + 1) * 10,
        })),
      );
      setState((current) => ({
        ...current,
        isSaving: false,
        services: response.data,
        successMessage: "Orden de servicios actualizado.",
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        isSaving: false,
        catalogMessage: getApiErrorMessage(error),
      }));
    }
  }

  async function handleRestoreServiceDefaults() {
    if (!canManageCatalog) {
      return;
    }

    setState((current) => ({
      ...current,
      isSaving: true,
      catalogMessage: null,
      successMessage: null,
    }));

    try {
      const response = await restoreServiceDefaults();
      setState((current) => ({
        ...current,
        isSaving: false,
        services: response.data,
        successMessage: "Servicios predeterminados restaurados.",
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        isSaving: false,
        catalogMessage: getApiErrorMessage(error),
      }));
    }
  }

  return (
    <div className="page-stack settings-layout">
      <section className="screen-heading list-page__header">
        <h1>Ajustes</h1>
        <p>Configuración de clínica</p>
      </section>

      {state.isLoading ? <div className="loading-card" aria-label="Cargando ajustes" /> : null}
      {state.errorMessage ? <div className="error-state">{state.errorMessage}</div> : null}
      {state.successMessage ? <div className="success-state">{state.successMessage}</div> : null}

      {!state.isLoading && state.profile ? (
        <div className="settings-section-list">
          <section className="panel settings-section-card">
            <button
              aria-expanded={Boolean(expandedSettingsSections.salesBilling)}
              className="settings-section-card__header"
              type="button"
              onClick={() => toggleSettingsSection("salesBilling")}
            >
              <span className="settings-section-card__icon" aria-hidden="true">
                <ReceiptText size={20} />
              </span>
              <span className="settings-section-card__copy">
                <strong>Ventas y facturación</strong>
                <small>Formas de pago, emisores y comprobantes manuales.</small>
              </span>
              <ChevronDown aria-hidden="true" size={16} />
            </button>

            {expandedSettingsSections.salesBilling ? (
              <div className="settings-section-card__content">
                <Link className="settings-navigation-row" href="/settings/sales/payment-methods">
                  <span><strong>Formas de pago</strong><small>Configura las opciones disponibles para registrar cobros.</small></span>
                  <span aria-hidden="true">→</span>
                </Link>
                <Link className="settings-navigation-row" href="/settings/sales/fiscal-issuers">
                  <span>
                    <strong>Emisores fiscales</strong>
                    <small>Configura quién puede emitir comprobantes y qué tipos tiene habilitados.</small>
                  </span>
                  <span aria-hidden="true">→</span>
                </Link>
              </div>
            ) : null}
          </section>

          <section className="panel settings-section-card">
            <button
              aria-expanded={Boolean(expandedSettingsSections.profile)}
              className="settings-section-card__header"
              type="button"
              onClick={() => toggleSettingsSection("profile")}
            >
              <span className="settings-section-card__icon" aria-hidden="true">
                <Building2 size={20} />
              </span>
              <span className="settings-section-card__copy">
                <strong>Perfil de clínica</strong>
                <small>Datos visibles para documentos, agenda y comunicaciones.</small>
              </span>
              <ChevronDown aria-hidden="true" size={16} />
            </button>

            {expandedSettingsSections.profile ? (
              <div className="settings-section-card__content">
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

                  <label className="field settings-field--full">
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

                  <label className="field settings-field--full">
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
              </div>
            ) : null}
          </section>

          <section className="panel settings-section-card">
            <button
              aria-expanded={Boolean(expandedSettingsSections.team)}
              className="settings-section-card__header"
              type="button"
              onClick={() => toggleSettingsSection("team")}
            >
              <span className="settings-section-card__icon" aria-hidden="true">
                <Users size={20} />
              </span>
              <span className="settings-section-card__copy">
                <strong>Equipo de clínica</strong>
                <small>Veterinarios disponibles para asignar turnos.</small>
              </span>
              <ChevronDown aria-hidden="true" size={16} />
            </button>

            {expandedSettingsSections.team ? (
              <div className="settings-section-card__content">
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
                <button
                  className="secondary-button settings-team-button"
                  onClick={() => {
                    setState((current) => ({ ...current, successMessage: null }));
                    setIsTeamOpen(true);
                  }}
                  type="button"
                >
                  <Users aria-hidden="true" size={16} />
                  Ver equipo
                </button>
              </div>
            ) : null}
          </section>

          <section className="panel settings-section-card">
            <button
              aria-expanded={Boolean(expandedSettingsSections.preferences)}
              className="settings-section-card__header"
              type="button"
              onClick={() => toggleSettingsSection("preferences")}
            >
              <span className="settings-section-card__icon" aria-hidden="true">
                <CalendarClock size={20} />
              </span>
              <span className="settings-section-card__copy">
                <strong>Preferencias</strong>
                <small>Región, moneda y duración base de agenda.</small>
              </span>
              <ChevronDown aria-hidden="true" size={16} />
            </button>

            {expandedSettingsSections.preferences && preferencesFormState ? (
              <div className="settings-section-card__content">
                <form className="entity-form" onSubmit={handleSavePreferences}>
                  <div className="form-grid">
                    <label className="field">
                      <span>Región</span>
                      <select
                        disabled={!canManageCatalog}
                        value={`${preferencesFormState.currency_code}:${preferencesFormState.locale}`}
                        onChange={(event) => {
                          const [currencyCode, locale] = event.target.value.split(":") as [
                            "USD" | "ARS",
                            "es-PA" | "es-AR",
                          ];
                          setPreferencesFormState((current) =>
                            current
                              ? {
                                  ...current,
                                  currency_code: currencyCode,
                                  locale,
                                }
                              : current,
                          );
                        }}
                      >
                        <option value="USD:es-PA">USD · es-PA</option>
                        <option value="ARS:es-AR">ARS · es-AR</option>
                      </select>
                    </label>

                    <label className="field">
                      <span>Duración predeterminada</span>
                      <input
                        disabled={!canManageCatalog}
                        inputMode="numeric"
                        value={preferencesFormState.default_appointment_duration_minutes}
                        onChange={(event) =>
                          setPreferencesFormState((current) =>
                            current
                              ? {
                                  ...current,
                                  default_appointment_duration_minutes: event.target.value,
                                }
                              : current,
                          )
                        }
                      />
                    </label>
                  </div>

                  <label className="field settings-field--full">
                    <span>Opciones de duración</span>
                    <input
                      disabled={!canManageCatalog}
                      value={preferencesFormState.appointment_duration_options}
                      onChange={(event) =>
                        setPreferencesFormState((current) =>
                          current
                            ? {
                                ...current,
                                appointment_duration_options: event.target.value,
                              }
                            : current,
                        )
                      }
                    />
                  </label>

                  <div className="form-grid">
                    <label className="field">
                      <span>Impuesto de compra predeterminado (%)</span>
                      <input
                        disabled={!canManageCatalog}
                        inputMode="decimal"
                        value={preferencesFormState.default_purchase_tax_rate}
                        onChange={(event) =>
                          setPreferencesFormState((current) =>
                            current
                              ? {
                                  ...current,
                                  default_purchase_tax_rate: event.target.value,
                                }
                              : current,
                          )
                        }
                      />
                    </label>

                    <label className="field">
                      <span>Impuesto de venta predeterminado (%)</span>
                      <input
                        disabled={!canManageCatalog}
                        inputMode="decimal"
                        value={preferencesFormState.default_sale_tax_rate}
                        onChange={(event) =>
                          setPreferencesFormState((current) =>
                            current
                              ? {
                                  ...current,
                                  default_sale_tax_rate: event.target.value,
                                }
                              : current,
                          )
                        }
                      />
                    </label>

                    <label className="field">
                      <span>Margen de ganancia predeterminado (%)</span>
                      <input
                        disabled={!canManageCatalog}
                        inputMode="decimal"
                        value={preferencesFormState.default_profit_margin}
                        onChange={(event) =>
                          setPreferencesFormState((current) =>
                            current
                              ? {
                                  ...current,
                                  default_profit_margin: event.target.value,
                                }
                              : current,
                          )
                        }
                      />
                    </label>

                    <label className="field">
                      <span>Incremento de redondeo</span>
                      <input
                        disabled={!canManageCatalog}
                        inputMode="decimal"
                        value={preferencesFormState.money_rounding_increment}
                        onChange={(event) =>
                          setPreferencesFormState((current) =>
                            current
                              ? {
                                  ...current,
                                  money_rounding_increment: event.target.value,
                                }
                              : current,
                          )
                        }
                      />
                    </label>
                  </div>

                  <div className="modal-actions">
                    <button
                      className="primary-button"
                      disabled={!canManageCatalog || state.isSaving}
                      type="submit"
                    >
                      {state.isSaving ? "Guardando..." : "Guardar preferencias"}
                    </button>
                  </div>
                </form>
              </div>
            ) : null}
          </section>

          <section className="panel settings-section-card">
            <button
              aria-expanded={Boolean(expandedSettingsSections.services)}
              className="settings-section-card__header"
              type="button"
              onClick={() => toggleSettingsSection("services")}
            >
              <span className="settings-section-card__icon" aria-hidden="true">
                <ClipboardList size={20} />
              </span>
              <span className="settings-section-card__copy">
                <strong>Servicios</strong>
                <small>Catálogo usado para crear turnos en agenda.</small>
              </span>
              <ChevronDown aria-hidden="true" size={16} />
            </button>

            {expandedSettingsSections.services ? (
              <div className="settings-section-card__content">
                {state.catalogMessage ? (
                  <div className="error-state">{state.catalogMessage}</div>
                ) : null}

                <div className="modal-actions">
                  <button
                    className="secondary-button"
                    disabled={!canManageCatalog || state.isSaving}
                    onClick={() => void handleRestoreServiceDefaults()}
                    type="button"
                  >
                    Restaurar predeterminados
                  </button>
                  <button
                    className="primary-button"
                    disabled={!canManageCatalog || state.isSaving}
                    onClick={openNewServiceForm}
                    type="button"
                  >
                    Nuevo servicio
                  </button>
                </div>

                {state.services.length === 0 ? (
                  <div className="empty-state">No hay servicios configurados.</div>
                ) : (
                  <section className="record-card-list" aria-label="Servicios">
                    {[...state.services]
                      .sort((a, b) => a.sort_order - b.sort_order)
                      .map((service, index, services) => (
                        <article className="record-card clinic-team-card" key={service.id}>
                          <span
                            className="pet-avatar pet-avatar--neutral"
                            style={{ backgroundColor: service.calendar_color }}
                            aria-hidden="true"
                          />
                          <div>
                            <div className="record-card__title-row">
                              <h3>{service.name}</h3>
                              <span className={service.is_active ? "badge badge--success" : "badge"}>
                                {service.is_active ? "Activo" : "Inactivo"}
                              </span>
                            </div>
                            <p>
                              {service.code} · {getServiceKindLabel(service.kind)} ·{" "}
                              {service.default_duration_minutes} min
                            </p>
                            <div className="record-card__actions">
                              <button
                                aria-label="Subir servicio"
                                className="icon-button"
                                disabled={!canManageCatalog || index === 0 || state.isSaving}
                                onClick={() => void handleMoveService(service, -1)}
                                type="button"
                              >
                                <ChevronUp aria-hidden="true" size={16} />
                              </button>
                              <button
                                aria-label="Bajar servicio"
                                className="icon-button"
                                disabled={
                                  !canManageCatalog ||
                                  index === services.length - 1 ||
                                  state.isSaving
                                }
                                onClick={() => void handleMoveService(service, 1)}
                                type="button"
                              >
                                <ChevronDown aria-hidden="true" size={16} />
                              </button>
                              <button
                                className="secondary-button"
                                disabled={!canManageCatalog}
                                onClick={() => openEditServiceForm(service)}
                                type="button"
                              >
                                <Pencil aria-hidden="true" size={16} />
                                Editar
                              </button>
                              <button
                                className="secondary-button"
                                disabled={!canManageCatalog || state.isSaving}
                                onClick={() => void handleToggleService(service)}
                                type="button"
                              >
                                {service.is_active ? (
                                  <PowerOff aria-hidden="true" size={16} />
                                ) : (
                                  <Power aria-hidden="true" size={16} />
                                )}
                                {service.is_active ? "Desactivar" : "Activar"}
                              </button>
                            </div>
                          </div>
                        </article>
                      ))}
                  </section>
                )}
              </div>
            ) : null}
          </section>

          <ClinicalCatalogsSection
            isExpanded={Boolean(expandedSettingsSections.clinicalCatalogs)}
            onToggle={() => toggleSettingsSection("clinicalCatalogs")}
          />

          <SpeciesCatalogSection
            isExpanded={Boolean(expandedSettingsSections.speciesCatalogs)}
            onToggle={() => toggleSettingsSection("speciesCatalogs")}
          />

          <InventoryCatalogsSection
            isExpanded={Boolean(expandedSettingsSections.inventoryCatalogs)}
            onToggle={() => toggleSettingsSection("inventoryCatalogs")}
          />

          <SuppliersSection
            isExpanded={Boolean(expandedSettingsSections.suppliers)}
            onToggle={() => toggleSettingsSection("suppliers")}
          />

          <section className="panel settings-section-card">
            <button
              aria-expanded={Boolean(expandedSettingsSections.location)}
              className="settings-section-card__header"
              type="button"
              onClick={() => toggleSettingsSection("location")}
            >
              <span className="settings-section-card__icon" aria-hidden="true">
                <MapPin size={20} />
              </span>
              <span className="settings-section-card__copy">
                <strong>Ubicación y zona horaria</strong>
                <small>País, ciudad y zona horaria de operación.</small>
              </span>
              <ChevronDown aria-hidden="true" size={16} />
            </button>

            {expandedSettingsSections.location ? (
              <div className="settings-section-card__content">
                <p className="settings-placeholder-text">
                  Próximamente podrás configurar país, ciudad y zona horaria de la clínica.
                </p>
              </div>
            ) : null}
          </section>
        </div>
      ) : null}

      {isTeamOpen && !editingTeamMember ? (
        <div className="modal-backdrop" role="presentation">
          <section aria-labelledby="clinic-team-title" aria-modal="true" className="bottom-sheet" role="dialog">
            <div className="bottom-sheet__header">
              <div>
                <h2 id="clinic-team-title">Equipo de clínica</h2>
              </div>
              <button aria-label="Cerrar" className="icon-button" onClick={() => setIsTeamOpen(false)} type="button">
                <X aria-hidden="true" size={20} />
              </button>
            </div>

            {state.successMessage ? (
              <div className="success-state">{state.successMessage}</div>
            ) : null}

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
                      <button
                        className="secondary-button clinic-team-card__edit"
                        onClick={() => openTeamMemberEditor(member)}
                        type="button"
                      >
                        Editar
                      </button>
                    </div>
                  </article>
                ))}
              </section>
            )}
          </section>
        </div>
      ) : null}

      {editingTeamMember ? (
        <div className="modal-backdrop" role="presentation">
          <section
            aria-labelledby="edit-team-member-title"
            aria-modal="true"
            className="bottom-sheet"
            role="dialog"
          >
            <div className="bottom-sheet__header">
              <div>
                <h2 id="edit-team-member-title">Editar veterinario</h2>
              </div>
              <button
                aria-label="Cerrar"
                className="icon-button"
                disabled={isTeamMemberSaving}
                onClick={closeTeamMemberEditor}
                type="button"
              >
                <X aria-hidden="true" size={20} />
              </button>
            </div>

            <form className="entity-form" onSubmit={handleSaveTeamMember}>
              <label className="field">
                <span>Nombre visible</span>
                <input
                  aria-describedby="team-member-name-help"
                  autoFocus
                  value={teamEditName}
                  onChange={(event) => {
                    setTeamEditName(event.target.value);
                    setTeamEditMessage(null);
                  }}
                />
                <small className="muted-text" id="team-member-name-help">
                  Este nombre se mostrará en agenda, consultas y registros clínicos.
                </small>
              </label>

              <p className="muted-text">Email: {editingTeamMember.email}</p>

              {teamEditMessage ? <div className="error-state">{teamEditMessage}</div> : null}

              <div className="modal-actions">
                <button
                  className="secondary-button"
                  disabled={isTeamMemberSaving}
                  onClick={closeTeamMemberEditor}
                  type="button"
                >
                  Cancelar
                </button>
                <button
                  className="primary-button"
                  disabled={
                    isTeamMemberSaving ||
                    teamEditName.trim() === editingTeamMember.full_name
                  }
                  type="submit"
                >
                  {isTeamMemberSaving ? "Guardando..." : "Guardar cambios"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}

      {serviceFormState ? (
        <div className="modal-backdrop" role="presentation">
          <section
            aria-labelledby="service-form-title"
            aria-modal="true"
            className="bottom-sheet"
            role="dialog"
          >
            <div className="bottom-sheet__header">
              <div>
                <h2 id="service-form-title">
                  {serviceFormState.id ? "Editar servicio" : "Nuevo servicio"}
                </h2>
              </div>
              <button
                aria-label="Cerrar"
                className="icon-button"
                disabled={state.isSaving}
                onClick={() => setServiceFormState(null)}
                type="button"
              >
                <X aria-hidden="true" size={20} />
              </button>
            </div>

            <form className="entity-form" onSubmit={handleSaveService}>
              <div className="form-grid">
                <label className="field">
                  <span>Código</span>
                  <input
                    required
                    value={serviceFormState.code}
                    onChange={(event) =>
                      setServiceFormState((current) =>
                        current ? { ...current, code: event.target.value } : current,
                      )
                    }
                  />
                </label>
                <label className="field">
                  <span>Nombre</span>
                  <input
                    required
                    value={serviceFormState.name}
                    onChange={(event) =>
                      setServiceFormState((current) =>
                        current ? { ...current, name: event.target.value } : current,
                      )
                    }
                  />
                </label>
                <label className="field">
                  <span>Tipo</span>
                  <select
                    value={serviceFormState.kind}
                    onChange={(event) =>
                      setServiceFormState((current) =>
                        current
                          ? {
                              ...current,
                              kind: event.target.value as ClinicServiceKind,
                            }
                          : current,
                      )
                    }
                  >
                    {serviceKindOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>Duración</span>
                  <input
                    required
                    inputMode="numeric"
                    value={serviceFormState.default_duration_minutes}
                    onChange={(event) =>
                      setServiceFormState((current) =>
                        current
                          ? {
                              ...current,
                              default_duration_minutes: event.target.value,
                            }
                          : current,
                      )
                    }
                  />
                </label>
                <label className="field">
                  <span>Color</span>
                  <input
                    type="color"
                    value={serviceFormState.calendar_color}
                    onChange={(event) =>
                      setServiceFormState((current) =>
                        current
                          ? { ...current, calendar_color: event.target.value }
                          : current,
                      )
                    }
                  />
                </label>
                <label className="field">
                  <span>Orden</span>
                  <input
                    inputMode="numeric"
                    value={serviceFormState.sort_order}
                    onChange={(event) =>
                      setServiceFormState((current) =>
                        current ? { ...current, sort_order: event.target.value } : current,
                      )
                    }
                  />
                </label>
              </div>

              <label className="field settings-field--full">
                <span>Descripción</span>
                <textarea
                  rows={3}
                  value={serviceFormState.description}
                  onChange={(event) =>
                    setServiceFormState((current) =>
                      current
                        ? { ...current, description: event.target.value }
                        : current,
                    )
                  }
                />
              </label>

              <label className="checkbox-row">
                <input
                  checked={serviceFormState.is_bookable}
                  type="checkbox"
                  onChange={(event) =>
                    setServiceFormState((current) =>
                      current
                        ? { ...current, is_bookable: event.target.checked }
                        : current,
                    )
                  }
                />
                <span>Disponible para agenda</span>
              </label>

              {state.catalogMessage ? (
                <div className="error-state">{state.catalogMessage}</div>
              ) : null}

              <div className="modal-actions">
                <button
                  className="secondary-button"
                  disabled={state.isSaving}
                  onClick={() => setServiceFormState(null)}
                  type="button"
                >
                  Cancelar
                </button>
                <button className="primary-button" disabled={state.isSaving} type="submit">
                  {state.isSaving ? "Guardando..." : "Guardar servicio"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}

      {isLogoDeleteOpen ? (
        <div className="modal-backdrop" role="presentation">
          <section aria-labelledby="delete-logo-title" aria-modal="true" className="bottom-sheet" role="dialog">
            <div className="bottom-sheet__header">
              <div>
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

function preferencesToFormState(preferences: TenantPreferences): PreferencesFormState {
  return {
    currency_code: preferences.currency_code,
    locale: preferences.locale,
    default_appointment_duration_minutes: String(
      preferences.default_appointment_duration_minutes,
    ),
    appointment_duration_options: preferences.appointment_duration_options.join(", "),
    default_purchase_tax_rate: preferences.default_purchase_tax_rate,
    default_sale_tax_rate: preferences.default_sale_tax_rate,
    default_profit_margin: preferences.default_profit_margin,
    money_rounding_increment: preferences.money_rounding_increment,
  };
}

function getInitialServiceFormState(nextSortOrder: number): ServiceFormState {
  return {
    id: null,
    code: "",
    name: "",
    description: "",
    kind: "consultation",
    default_duration_minutes: "30",
    calendar_color: "#2563eb",
    is_bookable: true,
    sort_order: String(nextSortOrder * 10),
  };
}

function serviceToFormState(service: ClinicServiceItem): ServiceFormState {
  return {
    id: service.id,
    code: service.code,
    name: service.name,
    description: service.description ?? "",
    kind: service.kind,
    default_duration_minutes: String(service.default_duration_minutes),
    calendar_color: service.calendar_color,
    is_bookable: service.is_bookable,
    sort_order: String(service.sort_order),
  };
}

function validateServiceForm(form: ServiceFormState) {
  if (!form.code.trim() || !form.name.trim()) {
    return "Código y nombre son obligatorios.";
  }
  const duration = Number(form.default_duration_minutes);
  if (!Number.isInteger(duration) || duration <= 0 || duration > 480) {
    return "La duración debe ser un número entero entre 1 y 480.";
  }
  const sortOrder = Number(form.sort_order);
  if (!Number.isInteger(sortOrder)) {
    return "El orden debe ser un número entero.";
  }
  return null;
}

function buildServicePayload(form: ServiceFormState): CreateClinicServicePayload {
  return {
    code: form.code.trim(),
    name: form.name.trim(),
    description: normalizeNullable(form.description),
    kind: form.kind,
    default_duration_minutes: Number(form.default_duration_minutes),
    calendar_color: form.calendar_color,
    is_bookable: form.is_bookable,
    sort_order: Number(form.sort_order),
  };
}

function parseDurationOptions(value: string) {
  const options = value
    .split(",")
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isInteger(item) && item > 0 && item <= 480);
  return Array.from(new Set(options));
}

function upsertService(
  services: ClinicServiceItem[],
  service: ClinicServiceItem,
): ClinicServiceItem[] {
  const exists = services.some((item) => item.id === service.id);
  const next = exists
    ? services.map((item) => (item.id === service.id ? service : item))
    : [...services, service];
  return next.sort((a, b) => a.sort_order - b.sort_order);
}

function getServiceKindLabel(kind: ClinicServiceKind) {
  return serviceKindOptions.find((option) => option.value === kind)?.label ?? "Otro";
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

function getTeamMemberUpdateErrorMessage(error: unknown) {
  if (error instanceof ApiClientError && error.status === 422) {
    return "Ingresa un nombre válido para el veterinario.";
  }

  if (error instanceof ApiClientError && error.status === 404) {
    return "No fue posible encontrar este integrante del equipo.";
  }

  return getApiErrorMessage(error);
}

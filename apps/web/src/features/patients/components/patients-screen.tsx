"use client";

import {
  AlertCircle,
  ChevronRight,
  Filter,
  Plus,
  Search,
  PawPrint,
  X,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { getApiErrorMessage } from "@/lib/api";
import { createOwner, getOwners } from "@/services/owners";
import { createPatient, getPatients } from "@/services/patients";
import type {
  CreateOwnerPayload,
  CreatePatientPayload,
  Owner,
  Patient,
} from "@/types/api";

type PatientsState = {
  isLoading: boolean;
  isSubmitting: boolean;
  isOwnerSubmitting: boolean;
  patients: Patient[];
  owners: Owner[];
  errorMessage: string | null;
  successMessage: string | null;
  flowMessage: string | null;
  flowMessageType: "success" | "error";
};

type PatientFormState = {
  owner_id: string;
  name: string;
  species: string;
  breed: string;
  sex: string;
  estimated_age: string;
  weight_kg: string;
  allergies: string;
  chronic_conditions: string;
};

type OwnerFormState = {
  full_name: string;
  phone: string;
  email: string;
  address: string;
};

type CreationStep = "patient" | "owner";

const initialPatientsState: PatientsState = {
  isLoading: true,
  isSubmitting: false,
  isOwnerSubmitting: false,
  patients: [],
  owners: [],
  errorMessage: null,
  successMessage: null,
  flowMessage: null,
  flowMessageType: "success",
};

const initialPatientFormState: PatientFormState = {
  owner_id: "",
  name: "",
  species: "",
  breed: "",
  sex: "",
  estimated_age: "",
  weight_kg: "",
  allergies: "",
  chronic_conditions: "",
};

const initialOwnerFormState: OwnerFormState = {
  full_name: "",
  phone: "",
  email: "",
  address: "",
};

export function PatientsScreen() {
  const [state, setState] = useState<PatientsState>(initialPatientsState);
  const [formState, setFormState] = useState<PatientFormState>(
    initialPatientFormState,
  );
  const [ownerFormState, setOwnerFormState] = useState<OwnerFormState>(
    initialOwnerFormState,
  );
  const [query, setQuery] = useState("");
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [creationStep, setCreationStep] = useState<CreationStep>("patient");

  async function loadPatientsScreen() {
    setState((current) => ({
      ...current,
      isLoading: true,
      errorMessage: null,
    }));

    try {
      const [patientsResponse, ownersResponse] = await Promise.all([
        getPatients(),
        getOwners(),
      ]);

      setState((current) => ({
        ...current,
        isLoading: false,
        patients: patientsResponse.data,
        owners: ownersResponse.data,
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        isLoading: false,
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }

  useEffect(() => {
    void loadPatientsScreen();
  }, []);

  function openCreateFlow() {
    setIsCreateOpen(true);
    setCreationStep("patient");
    setState((current) => ({
      ...current,
      errorMessage: null,
      flowMessage: null,
      flowMessageType: "success",
      successMessage: null,
    }));
  }

  function closeCreateFlow() {
    setIsCreateOpen(false);
    setCreationStep("patient");
    setFormState(initialPatientFormState);
    setOwnerFormState(initialOwnerFormState);
    setState((current) => ({
      ...current,
      isSubmitting: false,
      isOwnerSubmitting: false,
      flowMessage: null,
      flowMessageType: "success",
    }));
  }

  async function handleCreatePatient(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const payload: CreatePatientPayload = {
      owner_id: formState.owner_id,
      name: formState.name.trim(),
      species: formState.species.trim(),
    };

    if (formState.breed.trim()) {
      payload.breed = formState.breed.trim();
    }
    if (formState.sex.trim()) {
      payload.sex = formState.sex.trim();
    }
    if (formState.estimated_age.trim()) {
      payload.estimated_age = formState.estimated_age.trim();
    }
    if (formState.weight_kg.trim()) {
      payload.weight_kg = Number(formState.weight_kg);
    }
    if (formState.allergies.trim()) {
      payload.allergies = formState.allergies.trim();
    }
    if (formState.chronic_conditions.trim()) {
      payload.chronic_conditions = formState.chronic_conditions.trim();
    }

    setState((current) => ({
      ...current,
      isSubmitting: true,
      errorMessage: null,
      successMessage: null,
      flowMessage: null,
      flowMessageType: "success",
    }));

    try {
      await createPatient(payload);
      setFormState(initialPatientFormState);
      setIsCreateOpen(false);
      setCreationStep("patient");
      setState((current) => ({
        ...current,
        isSubmitting: false,
        successMessage: "Paciente creado correctamente.",
      }));
      await loadPatientsScreen();
    } catch (error) {
      setState((current) => ({
        ...current,
        isSubmitting: false,
        flowMessage: getApiErrorMessage(error),
        flowMessageType: "error",
      }));
    }
  }

  async function handleCreateOwner(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const payload: CreateOwnerPayload = {
      full_name: ownerFormState.full_name.trim(),
      phone: ownerFormState.phone.trim(),
    };

    if (ownerFormState.email.trim()) {
      payload.email = ownerFormState.email.trim();
    }
    if (ownerFormState.address.trim()) {
      payload.address = ownerFormState.address.trim();
    }

    setState((current) => ({
      ...current,
      isOwnerSubmitting: true,
      flowMessage: null,
      flowMessageType: "success",
    }));

    try {
      const response = await createOwner(payload);
      const newOwner = response.data;
      setState((current) => ({
        ...current,
        isOwnerSubmitting: false,
        owners: [...current.owners, newOwner],
        flowMessage: "Propietario creado y seleccionado.",
        flowMessageType: "success",
      }));
      setFormState((current) => ({ ...current, owner_id: newOwner.id }));
      setOwnerFormState(initialOwnerFormState);
      setCreationStep("patient");
    } catch (error) {
      setState((current) => ({
        ...current,
        isOwnerSubmitting: false,
        flowMessage: getApiErrorMessage(error),
        flowMessageType: "error",
      }));
    }
  }

  const getOwnerName = useCallback(
    (ownerId: string) => {
      return state.owners.find((owner) => owner.id === ownerId)?.full_name ?? ownerId;
    },
    [state.owners],
  );

  const filteredPatients = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) {
      return state.patients;
    }

    return state.patients.filter((patient) => {
      const ownerName = getOwnerName(patient.owner_id).toLowerCase();
      return [patient.name, patient.species, patient.breed ?? "", ownerName]
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery);
    });
  }, [getOwnerName, query, state.patients]);

  return (
    <div className="page-stack patients-layout">
      <section className="screen-heading screen-heading--with-action">
        <div>
          <h1>Pacientes</h1>
          <p>
            {state.isLoading
              ? "Cargando pacientes..."
              : `${state.patients.length} paciente${state.patients.length === 1 ? "" : "s"} registrado${state.patients.length === 1 ? "" : "s"}`}
          </p>
        </div>
        <button
          className="floating-add-button"
          type="button"
          aria-label="Crear paciente"
          onClick={openCreateFlow}
        >
          <Plus aria-hidden="true" size={24} />
        </button>
      </section>

      <section className="toolbar-card" aria-label="Buscar y filtrar pacientes">
        <label className="search-field">
          <Search aria-hidden="true" size={18} />
          <span className="sr-only">Buscar pacientes</span>
          <input
            placeholder="Buscar por nombre, especie o propietario"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <button className="filter-button" type="button" aria-label="Filtros">
          <Filter aria-hidden="true" size={18} />
          <span>Filtros</span>
        </button>
      </section>

      {state.successMessage ? (
        <div className="success-state">{state.successMessage}</div>
      ) : null}

      {state.isLoading ? <div className="loading-card" aria-label="Cargando pacientes" /> : null}

      {!state.isLoading && state.errorMessage ? (
        <div className="error-state">{state.errorMessage}</div>
      ) : null}

      {!state.isLoading && !state.errorMessage && filteredPatients.length === 0 ? (
        <div className="empty-state">No hay pacientes que coincidan con la búsqueda.</div>
      ) : null}

      {!state.isLoading && !state.errorMessage && filteredPatients.length > 0 ? (
        <section className="patient-card-list" aria-label="Lista de pacientes">
          {filteredPatients.map((patient) => (
            <Link className="patient-card" href={`/patients/${patient.id}`} key={patient.id}>
              <span className="pet-avatar" aria-hidden="true">
                <PawPrint size={24} />
              </span>
              <span className="patient-card__body">
                <span className="patient-card__title-row">
                  <strong>{patient.name}</strong>
                  {patient.allergies ? (
                    <span className="badge badge--danger">
                      <AlertCircle size={13} /> Alergias
                    </span>
                  ) : null}
                </span>
                <span className="patient-card__meta">
                  {patient.species}
                  {patient.breed ? ` · ${patient.breed}` : ""}
                  {patient.estimated_age ? ` · ${patient.estimated_age}` : ""}
                  {patient.weight_kg ? ` · ${patient.weight_kg} kg` : ""}
                </span>
                <span className="patient-card__owner">
                  Propietario: {getOwnerName(patient.owner_id)}
                </span>
              </span>
              <ChevronRight aria-hidden="true" className="patient-card__chevron" size={20} />
            </Link>
          ))}
        </section>
      ) : null}

      {isCreateOpen ? (
        <div className="modal-backdrop" role="presentation">
          <section
            aria-labelledby="patient-flow-title"
            aria-modal="true"
            className="bottom-sheet"
            role="dialog"
          >
            <div className="bottom-sheet__header">
              <div>
                <p className="eyebrow">Registro clínico</p>
                <h2 id="patient-flow-title">
                  {creationStep === "patient" ? "Crear paciente" : "Crear propietario"}
                </h2>
              </div>
              <button
                aria-label="Cancelar"
                className="icon-button"
                onClick={closeCreateFlow}
                type="button"
              >
                <X aria-hidden="true" size={20} />
              </button>
            </div>

            {state.flowMessage ? (
              <div className={state.flowMessageType === "success" ? "success-state" : "error-state"}>
                {state.flowMessage}
              </div>
            ) : null}

            {creationStep === "patient" ? (
              <form className="entity-form" onSubmit={handleCreatePatient}>
                <label className="field">
                  <span>Propietario</span>
                  <select
                    required
                    value={formState.owner_id}
                    onChange={(event) =>
                      setFormState((current) => ({
                        ...current,
                        owner_id: event.target.value,
                      }))
                    }
                  >
                    <option value="">Selecciona un propietario</option>
                    {state.owners.map((owner) => (
                      <option key={owner.id} value={owner.id}>
                        {owner.full_name} · {owner.phone}
                      </option>
                    ))}
                  </select>
                </label>

                {state.isLoading ? (
                  <p className="panel-note">Cargando propietarios...</p>
                ) : null}
                {!state.isLoading && state.owners.length === 0 ? (
                  <p className="empty-state">
                    No hay propietarios registrados. Crea uno para continuar.
                  </p>
                ) : null}

                <button
                  className="secondary-button secondary-button--full"
                  onClick={() => {
                    setCreationStep("owner");
                    setState((current) => ({
                      ...current,
                      flowMessage: null,
                      flowMessageType: "success",
                    }));
                  }}
                  type="button"
                >
                  + Crear nuevo propietario
                </button>

                <div className="form-grid">
                  <label className="field">
                    <span>Nombre del paciente</span>
                    <input
                      required
                      value={formState.name}
                      onChange={(event) =>
                        setFormState((current) => ({ ...current, name: event.target.value }))
                      }
                    />
                  </label>

                  <label className="field">
                    <span>Especie</span>
                    <input
                      required
                      value={formState.species}
                      onChange={(event) =>
                        setFormState((current) => ({ ...current, species: event.target.value }))
                      }
                    />
                  </label>

                  <label className="field">
                    <span>Raza</span>
                    <input
                      value={formState.breed}
                      onChange={(event) =>
                        setFormState((current) => ({ ...current, breed: event.target.value }))
                      }
                    />
                  </label>

                  <label className="field">
                    <span>Sexo</span>
                    <input
                      value={formState.sex}
                      onChange={(event) =>
                        setFormState((current) => ({ ...current, sex: event.target.value }))
                      }
                    />
                  </label>

                  <label className="field">
                    <span>Edad estimada</span>
                    <input
                      value={formState.estimated_age}
                      onChange={(event) =>
                        setFormState((current) => ({
                          ...current,
                          estimated_age: event.target.value,
                        }))
                      }
                    />
                  </label>

                  <label className="field">
                    <span>Peso (kg)</span>
                    <input
                      inputMode="decimal"
                      value={formState.weight_kg}
                      onChange={(event) =>
                        setFormState((current) => ({
                          ...current,
                          weight_kg: event.target.value,
                        }))
                      }
                    />
                  </label>
                </div>

                <label className="field">
                  <span>Alergias</span>
                  <textarea
                    rows={2}
                    value={formState.allergies}
                    onChange={(event) =>
                      setFormState((current) => ({ ...current, allergies: event.target.value }))
                    }
                  />
                </label>

                <label className="field">
                  <span>Condiciones crónicas</span>
                  <textarea
                    rows={2}
                    value={formState.chronic_conditions}
                    onChange={(event) =>
                      setFormState((current) => ({
                        ...current,
                        chronic_conditions: event.target.value,
                      }))
                    }
                  />
                </label>

                <div className="modal-actions">
                  <button className="secondary-button" onClick={closeCreateFlow} type="button">
                    Cancelar
                  </button>
                  <button
                    className="primary-button"
                    disabled={state.isSubmitting || state.owners.length === 0}
                    type="submit"
                  >
                    {state.isSubmitting ? "Creando..." : "Crear paciente"}
                  </button>
                </div>
              </form>
            ) : (
              <form className="entity-form" onSubmit={handleCreateOwner}>
                <label className="field">
                  <span>Nombre completo</span>
                  <input
                    required
                    value={ownerFormState.full_name}
                    onChange={(event) =>
                      setOwnerFormState((current) => ({
                        ...current,
                        full_name: event.target.value,
                      }))
                    }
                  />
                </label>

                <label className="field">
                  <span>Teléfono</span>
                  <input
                    required
                    value={ownerFormState.phone}
                    onChange={(event) =>
                      setOwnerFormState((current) => ({ ...current, phone: event.target.value }))
                    }
                  />
                </label>

                <label className="field">
                  <span>Correo opcional</span>
                  <input
                    type="email"
                    value={ownerFormState.email}
                    onChange={(event) =>
                      setOwnerFormState((current) => ({ ...current, email: event.target.value }))
                    }
                  />
                </label>

                <label className="field">
                  <span>Dirección opcional</span>
                  <textarea
                    rows={2}
                    value={ownerFormState.address}
                    onChange={(event) =>
                      setOwnerFormState((current) => ({ ...current, address: event.target.value }))
                    }
                  />
                </label>

                <div className="modal-actions modal-actions--three">
                  <button
                    className="secondary-button"
                    onClick={() => {
                      setCreationStep("patient");
                      setOwnerFormState(initialOwnerFormState);
                      setState((current) => ({
                        ...current,
                        flowMessage: null,
                        flowMessageType: "success",
                      }));
                    }}
                    type="button"
                  >
                    Volver
                  </button>
                  <button className="secondary-button" onClick={closeCreateFlow} type="button">
                    Cancelar
                  </button>
                  <button
                    className="primary-button"
                    disabled={state.isOwnerSubmitting}
                    type="submit"
                  >
                    {state.isOwnerSubmitting ? "Creando..." : "Crear propietario"}
                  </button>
                </div>
              </form>
            )}
          </section>
        </div>
      ) : null}
    </div>
  );
}

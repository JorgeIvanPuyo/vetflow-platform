"use client";

import { AlertCircle, ChevronRight, Filter, Plus, Search, PawPrint } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { ApiClientError } from "@/lib/api";
import { getOwners } from "@/services/owners";
import { createPatient, getPatients } from "@/services/patients";
import type { CreatePatientPayload, Owner, Patient } from "@/types/api";

type PatientsState = {
  isLoading: boolean;
  isSubmitting: boolean;
  patients: Patient[];
  owners: Owner[];
  errorMessage: string | null;
  successMessage: string | null;
};

type PatientFormState = {
  owner_id: string;
  name: string;
  species: string;
  breed: string;
  sex: string;
  estimated_age: string;
  weight_kg: string;
};

const initialPatientsState: PatientsState = {
  isLoading: true,
  isSubmitting: false,
  patients: [],
  owners: [],
  errorMessage: null,
  successMessage: null,
};

const initialFormState: PatientFormState = {
  owner_id: "",
  name: "",
  species: "",
  breed: "",
  sex: "",
  estimated_age: "",
  weight_kg: "",
};

export function PatientsScreen() {
  const [state, setState] = useState<PatientsState>(initialPatientsState);
  const [formState, setFormState] = useState<PatientFormState>(initialFormState);
  const [query, setQuery] = useState("");

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
      const message =
        error instanceof ApiClientError
          ? error.message
          : "No se pudieron cargar los pacientes";

      setState((current) => ({
        ...current,
        isLoading: false,
        errorMessage: message,
      }));
    }
  }

  useEffect(() => {
    void loadPatientsScreen();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
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

    setState((current) => ({
      ...current,
      isSubmitting: true,
      errorMessage: null,
      successMessage: null,
    }));

    try {
      await createPatient(payload);
      setFormState(initialFormState);
      setState((current) => ({
        ...current,
        isSubmitting: false,
        successMessage: "Paciente creado correctamente.",
      }));
      await loadPatientsScreen();
    } catch (error) {
      const message =
        error instanceof ApiClientError
          ? error.message
          : "No se pudo crear el paciente";

      setState((current) => ({
        ...current,
        isSubmitting: false,
        errorMessage: message,
      }));
    }
  }

  const getOwnerName = useCallback((ownerId: string) => {
    return state.owners.find((owner) => owner.id === ownerId)?.full_name ?? ownerId;
  }, [state.owners]);

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
        <a className="floating-add-button" href="#new-patient" aria-label="Crear paciente">
          <Plus aria-hidden="true" size={24} />
        </a>
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

      {state.isLoading ? <div className="panel-note">Cargando pacientes...</div> : null}

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

      <section className="panel form-panel" id="new-patient">
        <div className="section-heading">
          <p className="eyebrow">Registro clínico</p>
          <h2>Crear paciente</h2>
          <p>Asocia el paciente a un propietario existente.</p>
        </div>

        <form className="entity-form" onSubmit={handleSubmit}>
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
                  {owner.full_name}
                </option>
              ))}
            </select>
          </label>

          <div className="form-grid">
            <label className="field">
              <span>Nombre</span>
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
                  setFormState((current) => ({ ...current, weight_kg: event.target.value }))
                }
              />
            </label>
          </div>

          <button
            className="primary-button"
            disabled={state.isSubmitting || state.owners.length === 0}
            type="submit"
          >
            {state.isSubmitting ? "Guardando..." : "Crear paciente"}
          </button>
        </form>

        {state.owners.length === 0 && !state.isLoading ? (
          <p className="empty-state">Crea un propietario antes de registrar un paciente.</p>
        ) : null}

        {state.successMessage ? <p className="success-state">{state.successMessage}</p> : null}
        {state.errorMessage && !state.isLoading ? (
          <p className="error-state">{state.errorMessage}</p>
        ) : null}
      </section>
    </div>
  );
}

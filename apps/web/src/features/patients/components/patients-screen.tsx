"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

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

  function getOwnerName(ownerId: string) {
    return state.owners.find((owner) => owner.id === ownerId)?.full_name ?? ownerId;
  }

  return (
    <div className="content-grid">
      <section className="panel">
        <h2>Crear paciente</h2>
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

          <label className="field">
            <span>Nombre</span>
            <input
              required
              value={formState.name}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  name: event.target.value,
                }))
              }
            />
          </label>

          <label className="field">
            <span>Especie</span>
            <input
              required
              value={formState.species}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  species: event.target.value,
                }))
              }
            />
          </label>

          <label className="field">
            <span>Raza</span>
            <input
              value={formState.breed}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  breed: event.target.value,
                }))
              }
            />
          </label>

          <label className="field">
            <span>Sexo</span>
            <input
              value={formState.sex}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  sex: event.target.value,
                }))
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

        {state.successMessage ? (
          <p className="success-state">{state.successMessage}</p>
        ) : null}
        {state.errorMessage && !state.isLoading ? (
          <p className="error-state">{state.errorMessage}</p>
        ) : null}
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>Pacientes</h2>
          <p className="muted-text">Lista básica conectada al backend activo.</p>
        </div>

        {state.isLoading ? <div className="panel-note">Cargando pacientes...</div> : null}

        {!state.isLoading && state.errorMessage ? (
          <div className="error-state">{state.errorMessage}</div>
        ) : null}

        {!state.isLoading && !state.errorMessage && state.patients.length === 0 ? (
          <div className="empty-state">No hay pacientes registrados para esta cuenta.</div>
        ) : null}

        {!state.isLoading && !state.errorMessage && state.patients.length > 0 ? (
          <ul className="simple-list">
            {state.patients.map((patient) => (
              <li className="simple-list__item" key={patient.id}>
                <Link className="simple-list__title-link" href={`/patients/${patient.id}`}>
                  {patient.name}
                </Link>
                <p className="simple-list__meta">{patient.species}</p>
                <p className="simple-list__meta">
                  Propietario: {getOwnerName(patient.owner_id)}
                </p>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  );
}

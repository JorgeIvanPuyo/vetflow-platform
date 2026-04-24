"use client";

import { FormEvent, useEffect, useState } from "react";

import { ApiClientError } from "@/lib/api";
import { createOwner, getOwners } from "@/services/owners";
import type { CreateOwnerPayload, Owner } from "@/types/api";

type OwnersState = {
  isLoading: boolean;
  isSubmitting: boolean;
  owners: Owner[];
  errorMessage: string | null;
  successMessage: string | null;
};

type OwnerFormState = {
  full_name: string;
  phone: string;
  email: string;
};

const initialOwnersState: OwnersState = {
  isLoading: true,
  isSubmitting: false,
  owners: [],
  errorMessage: null,
  successMessage: null,
};

const initialFormState: OwnerFormState = {
  full_name: "",
  phone: "",
  email: "",
};

export function OwnersScreen() {
  const [state, setState] = useState<OwnersState>(initialOwnersState);
  const [formState, setFormState] = useState<OwnerFormState>(initialFormState);

  async function loadOwners() {
    setState((current) => ({
      ...current,
      isLoading: true,
      errorMessage: null,
    }));

    try {
      const response = await getOwners();
      setState((current) => ({
        ...current,
        isLoading: false,
        owners: response.data,
      }));
    } catch (error) {
      const message =
        error instanceof ApiClientError
          ? error.message
          : "No se pudieron cargar los propietarios";

      setState((current) => ({
        ...current,
        isLoading: false,
        errorMessage: message,
      }));
    }
  }

  useEffect(() => {
    void loadOwners();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const payload: CreateOwnerPayload = {
      full_name: formState.full_name.trim(),
      phone: formState.phone.trim(),
    };

    if (formState.email.trim()) {
      payload.email = formState.email.trim();
    }

    setState((current) => ({
      ...current,
      isSubmitting: true,
      errorMessage: null,
      successMessage: null,
    }));

    try {
      await createOwner(payload);
      setFormState(initialFormState);
      setState((current) => ({
        ...current,
        isSubmitting: false,
        successMessage: "Propietario creado correctamente.",
      }));
      await loadOwners();
    } catch (error) {
      const message =
        error instanceof ApiClientError
          ? error.message
          : "No se pudo crear el propietario";

      setState((current) => ({
        ...current,
        isSubmitting: false,
        errorMessage: message,
      }));
    }
  }

  return (
    <div className="content-grid">
      <section className="panel">
        <h2>Crear propietario</h2>
        <form className="entity-form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Nombre completo</span>
            <input
              required
              value={formState.full_name}
              onChange={(event) =>
                setFormState((current) => ({
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
            <span>Correo</span>
            <input
              type="email"
              value={formState.email}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  email: event.target.value,
                }))
              }
            />
          </label>

          <button className="primary-button" disabled={state.isSubmitting} type="submit">
            {state.isSubmitting ? "Guardando..." : "Crear propietario"}
          </button>
        </form>

        {state.successMessage ? (
          <p className="success-state">{state.successMessage}</p>
        ) : null}
        {state.errorMessage && !state.isLoading ? (
          <p className="error-state">{state.errorMessage}</p>
        ) : null}
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>Propietarios</h2>
          <p className="muted-text">Conectado al backend real de la cuenta activa.</p>
        </div>

        {state.isLoading ? <div className="panel-note">Cargando propietarios...</div> : null}

        {!state.isLoading && state.errorMessage ? (
          <div className="error-state">{state.errorMessage}</div>
        ) : null}

        {!state.isLoading && !state.errorMessage && state.owners.length === 0 ? (
          <div className="empty-state">No hay propietarios registrados para esta cuenta.</div>
        ) : null}

        {!state.isLoading && !state.errorMessage && state.owners.length > 0 ? (
          <ul className="simple-list">
            {state.owners.map((owner) => (
              <li className="simple-list__item" key={owner.id}>
                <p className="simple-list__title">{owner.full_name}</p>
                <p className="simple-list__meta">{owner.phone}</p>
                {owner.email ? <p className="simple-list__meta">{owner.email}</p> : null}
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  );
}

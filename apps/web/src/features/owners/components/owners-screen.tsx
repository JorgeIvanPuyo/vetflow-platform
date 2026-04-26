"use client";

import { Mail, Phone, UserPlus, Users } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { getApiErrorMessage } from "@/lib/api";
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
        getApiErrorMessage(error);

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
        getApiErrorMessage(error);

      setState((current) => ({
        ...current,
        isSubmitting: false,
        errorMessage: message,
      }));
    }
  }

  return (
    <div className="content-grid owners-layout">
      <section className="panel form-panel">
        <div className="section-heading">
          <span className="icon-bubble"><UserPlus size={22} /></span>
          <p className="eyebrow">Directorio</p>
          <h2>Crear propietario</h2>
          <p>Registra los datos mínimos de contacto para vincular pacientes.</p>
        </div>

        <form className="entity-form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Nombre completo</span>
            <input
              required
              value={formState.full_name}
              onChange={(event) =>
                setFormState((current) => ({ ...current, full_name: event.target.value }))
              }
            />
          </label>

          <label className="field">
            <span>Teléfono</span>
            <input
              required
              value={formState.phone}
              onChange={(event) =>
                setFormState((current) => ({ ...current, phone: event.target.value }))
              }
            />
          </label>

          <label className="field">
            <span>Correo</span>
            <input
              type="email"
              value={formState.email}
              onChange={(event) =>
                setFormState((current) => ({ ...current, email: event.target.value }))
              }
            />
          </label>

          <button className="primary-button" disabled={state.isSubmitting} type="submit">
            {state.isSubmitting ? "Guardando..." : "Crear propietario"}
          </button>
        </form>

        {state.successMessage ? <p className="success-state">{state.successMessage}</p> : null}
        {state.errorMessage && !state.isLoading ? (
          <p className="error-state">{state.errorMessage}</p>
        ) : null}
      </section>

      <section className="panel">
        <div className="section-heading section-heading--row">
          <div>
            <p className="eyebrow">Contactos</p>
            <h2>Propietarios</h2>
            <p>{state.isLoading ? "Cargando..." : `${state.owners.length} registrados`}</p>
          </div>
          <span className="icon-bubble icon-bubble--blue"><Users size={22} /></span>
        </div>

        {state.isLoading ? <div className="panel-note">Cargando propietarios...</div> : null}

        {!state.isLoading && state.errorMessage ? (
          <div className="error-state">{state.errorMessage}</div>
        ) : null}

        {!state.isLoading && !state.errorMessage && state.owners.length === 0 ? (
          <div className="empty-state">No hay propietarios registrados para esta cuenta.</div>
        ) : null}

        {!state.isLoading && !state.errorMessage && state.owners.length > 0 ? (
          <ul className="contact-list">
            {state.owners.map((owner) => (
              <li className="contact-card" key={owner.id}>
                <span className="contact-avatar" aria-hidden="true">
                  {owner.full_name.charAt(0).toUpperCase()}
                </span>
                <span className="contact-card__body">
                  <strong>{owner.full_name}</strong>
                  <span><Phone size={14} /> {owner.phone}</span>
                  {owner.email ? <span><Mail size={14} /> {owner.email}</span> : null}
                </span>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  );
}

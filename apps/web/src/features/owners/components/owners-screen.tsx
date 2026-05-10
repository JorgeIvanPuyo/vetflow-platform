"use client";

import { ChevronRight, Mail, MapPin, PawPrint, Phone, Plus, UserPlus, X } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { getApiErrorMessage } from "@/lib/api";
import { createOwner, getOwners } from "@/services/owners";
import { getPatients } from "@/services/patients";
import type { CreateOwnerPayload, Owner, Patient } from "@/types/api";

type OwnersState = {
  isLoading: boolean;
  isSubmitting: boolean;
  owners: Owner[];
  patients: Patient[];
  errorMessage: string | null;
  successMessage: string | null;
  formMessage: string | null;
};

type OwnerFormState = {
  full_name: string;
  phone: string;
  email: string;
  address: string;
};

const initialOwnersState: OwnersState = {
  isLoading: true,
  isSubmitting: false,
  owners: [],
  patients: [],
  errorMessage: null,
  successMessage: null,
  formMessage: null,
};

const initialFormState: OwnerFormState = {
  full_name: "",
  phone: "",
  email: "",
  address: "",
};

export function OwnersScreen() {
  const [state, setState] = useState<OwnersState>(initialOwnersState);
  const [formState, setFormState] = useState<OwnerFormState>(initialFormState);
  const [isCreateOpen, setIsCreateOpen] = useState(false);

  async function loadOwners() {
    setState((current) => ({
      ...current,
      isLoading: true,
      errorMessage: null,
    }));

    try {
      const [ownersResponse, patientsResponse] = await Promise.all([
        getOwners(),
        getPatients(),
      ]);
      setState((current) => ({
        ...current,
        isLoading: false,
        owners: ownersResponse.data,
        patients: patientsResponse.data,
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
    void loadOwners();
  }, []);

  const petCountByOwner = useMemo(() => {
    return state.patients.reduce<Record<string, number>>((counts, patient) => {
      counts[patient.owner_id] = (counts[patient.owner_id] ?? 0) + 1;
      return counts;
    }, {});
  }, [state.patients]);

  function openCreateModal() {
    setIsCreateOpen(true);
    setFormState(initialFormState);
    setState((current) => ({
      ...current,
      formMessage: null,
      successMessage: null,
      errorMessage: null,
    }));
  }

  function closeCreateModal() {
    setIsCreateOpen(false);
    setFormState(initialFormState);
    setState((current) => ({ ...current, formMessage: null, isSubmitting: false }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const payload: CreateOwnerPayload = {
      full_name: formState.full_name.trim(),
      phone: formState.phone.trim(),
    };

    if (formState.email.trim()) {
      payload.email = formState.email.trim();
    }
    if (formState.address.trim()) {
      payload.address = formState.address.trim();
    }

    setState((current) => ({
      ...current,
      isSubmitting: true,
      formMessage: null,
      successMessage: null,
    }));

    try {
      await createOwner(payload);
      closeCreateModal();
      setState((current) => ({
        ...current,
        isSubmitting: false,
        successMessage: "Propietario creado correctamente.",
      }));
      await loadOwners();
    } catch (error) {
      setState((current) => ({
        ...current,
        isSubmitting: false,
        formMessage: getApiErrorMessage(error),
      }));
    }
  }

  return (
    <div className="page-stack owners-layout">
      <section className="screen-heading list-page__header">
        <div>
          <h1>Propietarios</h1>
          <p>
            {state.isLoading
              ? "Cargando propietarios..."
              : `${state.owners.length} propietario${state.owners.length === 1 ? "" : "s"} registrado${state.owners.length === 1 ? "" : "s"} en la clínica`}
          </p>
        </div>
      </section>

      <button
        aria-label="Crear propietario"
        className="floating-add-button list-page__fab"
        onClick={openCreateModal}
        type="button"
      >
        <Plus aria-hidden="true" size={24} />
      </button>

      {state.successMessage ? <div className="success-state">{state.successMessage}</div> : null}

      {state.isLoading ? <div className="loading-card" aria-label="Cargando propietarios" /> : null}

      {!state.isLoading && state.errorMessage ? (
        <div className="error-state">{state.errorMessage}</div>
      ) : null}

      {!state.isLoading && !state.errorMessage && state.owners.length === 0 ? (
        <div className="empty-state">No hay propietarios registrados en la clínica.</div>
      ) : null}

      {!state.isLoading && !state.errorMessage && state.owners.length > 0 ? (
        <section className="owner-card-list" aria-label="Lista de propietarios">
          {state.owners.map((owner) => {
            const petCount = petCountByOwner[owner.id] ?? 0;

            return (
              <Link className="owner-card-link" href={`/owners/${owner.id}`} key={owner.id}>
                <span className="contact-avatar" aria-hidden="true">
                  {owner.full_name.charAt(0).toUpperCase()}
                </span>
                <span className="owner-card-link__body">
                  <span className="owner-card-link__title-row">
                    <strong>{owner.full_name}</strong>
                    <span className="badge badge--success">
                      <PawPrint size={13} /> {petCount} mascota{petCount === 1 ? "" : "s"}
                    </span>
                  </span>
                  <span><Phone size={14} /> {owner.phone}</span>
                  {owner.email ? <span><Mail size={14} /> {owner.email}</span> : null}
                  {owner.address ? <span><MapPin size={14} /> {owner.address}</span> : null}
                </span>
                <span className="list-page__chevron" aria-hidden="true">
                  <ChevronRight size={16} />
                </span>
              </Link>
            );
          })}
        </section>
      ) : null}

      {isCreateOpen ? (
        <div className="modal-backdrop" role="presentation">
          <section
            aria-labelledby="create-owner-title"
            aria-modal="true"
            className="bottom-sheet"
            role="dialog"
          >
            <div className="bottom-sheet__header">
              <div>
                <p className="eyebrow">Directorio</p>
                <h2 id="create-owner-title">Crear propietario</h2>
              </div>
              <button
                aria-label="Cancelar"
                className="icon-button"
                onClick={closeCreateModal}
                type="button"
              >
                <X aria-hidden="true" size={20} />
              </button>
            </div>

            {state.formMessage ? <div className="error-state">{state.formMessage}</div> : null}

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
                <span>Correo opcional</span>
                <input
                  type="email"
                  value={formState.email}
                  onChange={(event) =>
                    setFormState((current) => ({ ...current, email: event.target.value }))
                  }
                />
              </label>

              <label className="field">
                <span>Dirección opcional</span>
                <textarea
                  rows={2}
                  value={formState.address}
                  onChange={(event) =>
                    setFormState((current) => ({ ...current, address: event.target.value }))
                  }
                />
              </label>

              <div className="modal-actions">
                <button className="secondary-button" onClick={closeCreateModal} type="button">
                  Cancelar
                </button>
                <button className="primary-button" disabled={state.isSubmitting} type="submit">
                  {state.isSubmitting ? "Creando..." : "Crear propietario"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </div>
  );
}

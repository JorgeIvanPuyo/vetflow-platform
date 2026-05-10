"use client";

import { Edit, Mail, MapPin, PawPrint, Phone, Trash2, User, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { getApiErrorMessage } from "@/lib/api";
import { deleteOwner, getOwner, updateOwner } from "@/services/owners";
import { getPatients } from "@/services/patients";
import type { Owner, Patient, UpdateOwnerPayload } from "@/types/api";

type OwnerDetailProps = {
  ownerId: string;
};

type OwnerDetailState = {
  isLoading: boolean;
  isSaving: boolean;
  isDeleting: boolean;
  owner: Owner | null;
  pets: Patient[];
  errorMessage: string | null;
  successMessage: string | null;
  formMessage: string | null;
  deleteMessage: string | null;
};

type OwnerFormState = {
  full_name: string;
  phone: string;
  email: string;
  address: string;
};

const initialState: OwnerDetailState = {
  isLoading: true,
  isSaving: false,
  isDeleting: false,
  owner: null,
  pets: [],
  errorMessage: null,
  successMessage: null,
  formMessage: null,
  deleteMessage: null,
};

const initialFormState: OwnerFormState = {
  full_name: "",
  phone: "",
  email: "",
  address: "",
};

export function OwnerDetail({ ownerId }: OwnerDetailProps) {
  const router = useRouter();
  const [state, setState] = useState<OwnerDetailState>(initialState);
  const [formState, setFormState] = useState<OwnerFormState>(initialFormState);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");

  const loadOwnerDetail = useCallback(async () => {
    setState((current) => ({ ...current, isLoading: true, errorMessage: null }));

    try {
      const [ownerResponse, petsResponse] = await Promise.all([
        getOwner(ownerId),
        getPatients({ ownerId }),
      ]);

      setState((current) => ({
        ...current,
        isLoading: false,
        owner: ownerResponse.data,
        pets: petsResponse.data,
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        isLoading: false,
        owner: null,
        pets: [],
        errorMessage: getApiErrorMessage(error),
      }));
    }
  }, [ownerId]);

  useEffect(() => {
    void loadOwnerDetail();
  }, [loadOwnerDetail]);

  function openEditModal() {
    if (!state.owner) {
      return;
    }

    setFormState({
      full_name: state.owner.full_name,
      phone: state.owner.phone,
      email: state.owner.email ?? "",
      address: state.owner.address ?? "",
    });
    setIsEditOpen(true);
    setState((current) => ({ ...current, formMessage: null, successMessage: null }));
  }

  function closeEditModal() {
    setIsEditOpen(false);
    setFormState(initialFormState);
    setState((current) => ({ ...current, formMessage: null, isSaving: false }));
  }

  function openDeleteModal() {
    setIsDeleteOpen(true);
    setDeleteConfirmation("");
    setState((current) => ({
      ...current,
      deleteMessage: null,
      successMessage: null,
    }));
  }

  function closeDeleteModal() {
    if (state.isDeleting) {
      return;
    }

    setIsDeleteOpen(false);
    setDeleteConfirmation("");
    setState((current) => ({ ...current, deleteMessage: null }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const payload: UpdateOwnerPayload = {
      full_name: formState.full_name.trim(),
      phone: formState.phone.trim(),
      email: formState.email.trim() || null,
      address: formState.address.trim() || null,
    };

    setState((current) => ({
      ...current,
      isSaving: true,
      formMessage: null,
      successMessage: null,
    }));

    try {
      await updateOwner(ownerId, payload);
      closeEditModal();
      setState((current) => ({
        ...current,
        isSaving: false,
        successMessage: "Propietario actualizado correctamente.",
      }));
      await loadOwnerDetail();
    } catch (error) {
      setState((current) => ({
        ...current,
        isSaving: false,
        formMessage: getApiErrorMessage(error),
      }));
    }
  }

  async function handleDeleteOwner(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (deleteConfirmation !== "ELIMINAR" || state.isDeleting) {
      return;
    }

    setState((current) => ({
      ...current,
      isDeleting: true,
      deleteMessage: null,
      successMessage: null,
    }));

    try {
      await deleteOwner(ownerId);
      router.push("/owners");
    } catch (error) {
      setState((current) => ({
        ...current,
        isDeleting: false,
        deleteMessage: getApiErrorMessage(error),
      }));
    }
  }

  if (state.isLoading) {
    return <div className="loading-card" aria-label="Cargando propietario" />;
  }

  if (state.errorMessage && !state.owner) {
    return <div className="error-state">{state.errorMessage}</div>;
  }

  if (!state.owner) {
    return <div className="empty-state">Propietario no encontrado.</div>;
  }

  return (
    <div className="page-stack owner-detail-page">
      <section className="detail-hero owner-detail-hero">
        <div className="detail-hero__main owner-detail-hero__main">
          <span className="contact-avatar" aria-hidden="true">
            {state.owner.full_name.charAt(0).toUpperCase()}
          </span>
          <div>
            <h1>{state.owner.full_name}</h1>
            <p>Contacto principal y mascotas asociadas</p>
          </div>
        </div>
        <div className="detail-hero__actions owner-detail-hero__actions">
          <button
            aria-label="Editar propietario"
            className="primary-button"
            onClick={openEditModal}
            type="button"
          >
            <Edit aria-hidden="true" size={16} />
            Editar
          </button>
          <button
            aria-label="Eliminar propietario"
            className="secondary-button secondary-button--danger"
            onClick={openDeleteModal}
            type="button"
          >
            <Trash2 aria-hidden="true" size={16} />
            Eliminar
          </button>
        </div>
      </section>

      {state.successMessage ? <div className="success-state">{state.successMessage}</div> : null}

      <section className="summary-grid">
        <article className="panel owner-data-card">
          <div className="section-heading">
            <h2>Información del propietario</h2>
          </div>
          <dl className="owner-details">
            <div><dt>Nombre</dt><dd><User size={14} /> {state.owner.full_name}</dd></div>
            <div><dt>Teléfono</dt><dd><Phone size={14} /> {state.owner.phone}</dd></div>
            <div><dt>Correo</dt><dd><Mail size={14} /> {state.owner.email ?? "No indicado"}</dd></div>
            <div><dt>Dirección</dt><dd><MapPin size={14} /> {state.owner.address ?? "No indicada"}</dd></div>
            <div><dt>Creado</dt><dd>{formatDate(state.owner.created_at)}</dd></div>
          </dl>
        </article>

        <article className="panel owner-pets-card">
          <div className="section-heading section-heading--row owner-pets-card__header">
            <div>
              <h2>{state.pets.length} Mascota{state.pets.length === 1 ? "" : "s"}</h2>
            </div>
            <span className="icon-bubble owner-pets-card__icon"><PawPrint size={20} /></span>
          </div>

          {state.pets.length === 0 ? (
            <div className="empty-state">Este propietario aún no tiene mascotas registradas.</div>
          ) : (
            <div className="patient-card-list">
              {state.pets.map((pet) => (
                <Link className="patient-card" href={`/patients/${pet.id}`} key={pet.id}>
                  <span className="pet-avatar" aria-hidden="true"><PawPrint size={22} /></span>
                  <span className="patient-card__body">
                    <strong>{pet.name}</strong>
                    <span className="patient-card__meta">
                      {pet.species}
                      {pet.breed ? ` · ${pet.breed}` : ""}
                      {pet.estimated_age ? ` · ${pet.estimated_age}` : ""}
                      {pet.weight_kg ? ` · ${pet.weight_kg} kg` : ""}
                    </span>
                  </span>
                </Link>
              ))}
            </div>
          )}
        </article>
      </section>

      {isEditOpen ? (
        <div className="modal-backdrop" role="presentation">
          <section
            aria-labelledby="edit-owner-title"
            aria-modal="true"
            className="bottom-sheet"
            role="dialog"
          >
            <div className="bottom-sheet__header">
              <div>
                <p className="eyebrow">Edición</p>
                <h2 id="edit-owner-title">Editar propietario</h2>
              </div>
              <button
                aria-label="Cancelar"
                className="icon-button"
                onClick={closeEditModal}
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
                <button className="secondary-button" onClick={closeEditModal} type="button">
                  Cancelar
                </button>
                <button className="primary-button" disabled={state.isSaving} type="submit">
                  {state.isSaving ? "Guardando..." : "Guardar cambios"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}

      {isDeleteOpen ? (
        <div className="modal-backdrop" role="presentation">
          <section
            aria-labelledby="delete-owner-title"
            aria-modal="true"
            className="bottom-sheet"
            role="dialog"
          >
            <div className="bottom-sheet__header">
              <div>
                <p className="eyebrow">Acción irreversible</p>
                <h2 id="delete-owner-title">Eliminar propietario</h2>
              </div>
              <button
                aria-label="Cancelar"
                className="icon-button"
                disabled={state.isDeleting}
                onClick={closeDeleteModal}
                type="button"
              >
                <X aria-hidden="true" size={20} />
              </button>
            </div>

            <div className="danger-callout" role="alert">
              <strong>Esta acción eliminará el propietario y todos los pacientes asociados a este propietario. Procede con precaución.</strong>
              <span>Esta acción no se puede deshacer.</span>
            </div>

            {state.deleteMessage ? <div className="error-state">{state.deleteMessage}</div> : null}

            <form className="entity-form" onSubmit={handleDeleteOwner}>
              <label className="field">
                <span>Escribe ELIMINAR para confirmar</span>
                <input
                  autoComplete="off"
                  value={deleteConfirmation}
                  onChange={(event) => setDeleteConfirmation(event.target.value)}
                />
              </label>

              <div className="modal-actions">
                <button
                  className="secondary-button"
                  disabled={state.isDeleting}
                  onClick={closeDeleteModal}
                  type="button"
                >
                  Cancelar
                </button>
                <button
                  className="danger-button"
                  disabled={deleteConfirmation !== "ELIMINAR" || state.isDeleting}
                  type="submit"
                >
                  {state.isDeleting ? "Eliminando..." : "Confirmar eliminación"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </div>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("es", { dateStyle: "medium" }).format(new Date(value));
}

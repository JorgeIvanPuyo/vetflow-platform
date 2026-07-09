"use client";

import { ArrowLeft, Edit, Mail, MapPin, PawPrint, Phone, Trash2, User, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { getApiErrorMessage } from "@/lib/api";
import { deleteOwner, getOwner, updateOwner } from "@/services/owners";
import { getPatient, getPatients, updatePatient } from "@/services/patients";
import type { Owner, Patient, UpdateOwnerPayload, UpdatePatientPayload } from "@/types/api";

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

type PatientFormState = {
  name: string;
  species: string;
  breed: string;
  sex: string;
  estimated_age: string;
  weight_kg: string;
  allergies: string;
  chronic_conditions: string;
};

const initialPatientFormState: PatientFormState = {
  name: "",
  species: "",
  breed: "",
  sex: "",
  estimated_age: "",
  weight_kg: "",
  allergies: "",
  chronic_conditions: "",
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
  const [isPetEditOpen, setIsPetEditOpen] = useState(false);
  const [editingPet, setEditingPet] = useState<Patient | null>(null);
  const [petFormState, setPetFormState] = useState<PatientFormState>(initialPatientFormState);
  const [isPetLoading, setIsPetLoading] = useState(false);
  const [isSavingPet, setIsSavingPet] = useState(false);
  const [petFormMessage, setPetFormMessage] = useState<string | null>(null);

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

  function toPatientFormState(patient: Patient): PatientFormState {
    return {
      name: patient.name,
      species: patient.species,
      breed: patient.breed ?? "",
      sex: patient.sex ?? "",
      estimated_age: patient.estimated_age ?? "",
      weight_kg: patient.weight_kg ?? "",
      allergies: patient.allergies ?? "",
      chronic_conditions: patient.chronic_conditions ?? "",
    };
  }

  async function openPetEditModal(pet: Patient) {
    setEditingPet(pet);
    // Precarga con los datos ya disponibles en la lista; el fetch por id los refresca.
    setPetFormState(toPatientFormState(pet));
    setPetFormMessage(null);
    setIsPetLoading(true);
    setIsPetEditOpen(true);
    setState((current) => ({ ...current, successMessage: null }));

    try {
      const response = await getPatient(pet.id);
      const patient = response.data;

      setPetFormState(toPatientFormState(patient));
      setEditingPet(patient);
      setIsPetLoading(false);
    } catch (error) {
      setIsPetLoading(false);
      setPetFormMessage(getApiErrorMessage(error));
    }
  }

  function closePetEditModal() {
    if (isSavingPet) {
      return;
    }

    setIsPetEditOpen(false);
    setEditingPet(null);
    setPetFormState(initialPatientFormState);
    setPetFormMessage(null);
    setIsPetLoading(false);
  }

  async function handlePetSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!editingPet) {
      return;
    }

    const name = petFormState.name.trim();
    const species = petFormState.species.trim();

    if (!name || !species) {
      setPetFormMessage("El nombre y la especie son obligatorios.");
      return;
    }

    const weightRaw = petFormState.weight_kg.trim();
    let weight_kg: number | null = null;
    if (weightRaw) {
      const parsed = Number(weightRaw);
      if (Number.isNaN(parsed) || parsed < 0) {
        setPetFormMessage("El peso debe ser un número válido.");
        return;
      }
      weight_kg = parsed;
    }

    const payload: UpdatePatientPayload = {
      name,
      species,
      breed: petFormState.breed.trim() || null,
      sex: petFormState.sex.trim() || null,
      estimated_age: petFormState.estimated_age.trim() || null,
      weight_kg,
      allergies: petFormState.allergies.trim() || null,
      chronic_conditions: petFormState.chronic_conditions.trim() || null,
    };

    setIsSavingPet(true);
    setPetFormMessage(null);

    try {
      await updatePatient(editingPet.id, payload);
      setIsSavingPet(false);
      setIsPetEditOpen(false);
      setEditingPet(null);
      setPetFormState(initialPatientFormState);
      setState((current) => ({
        ...current,
        successMessage: "Paciente actualizado correctamente.",
      }));
      await loadOwnerDetail();
    } catch (error) {
      setIsSavingPet(false);
      setPetFormMessage(getApiErrorMessage(error));
    }
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
        <Link className="back-link" href="/owners">
          <ArrowLeft aria-hidden="true" size={17} /> Volver a propietarios
        </Link>
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
                <div className="patient-card patient-card--editable" key={pet.id}>
                  <Link
                    aria-label={`Ver ${pet.name}`}
                    className="patient-card__link-overlay"
                    href={`/patients/${pet.id}`}
                  />
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
                  <button
                    aria-label={`Editar ${pet.name}`}
                    className="icon-button patient-card__edit"
                    onClick={() => openPetEditModal(pet)}
                    type="button"
                  >
                    <Edit aria-hidden="true" size={16} />
                  </button>
                </div>
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

      {isPetEditOpen ? (
        <div className="modal-backdrop" role="presentation">
          <section
            aria-labelledby="edit-pet-title"
            aria-modal="true"
            className="bottom-sheet"
            role="dialog"
          >
            <div className="bottom-sheet__header">
              <div>
                <p className="eyebrow">Edición</p>
                <h2 id="edit-pet-title">
                  {editingPet ? `Editar ${editingPet.name}` : "Editar paciente"}
                </h2>
              </div>
              <button
                aria-label="Cancelar"
                className="icon-button"
                disabled={isSavingPet}
                onClick={closePetEditModal}
                type="button"
              >
                <X aria-hidden="true" size={20} />
              </button>
            </div>

            {petFormMessage ? <div className="error-state">{petFormMessage}</div> : null}

            {isPetLoading ? (
              <div className="loading-card" aria-label="Cargando paciente" />
            ) : (
              <form className="entity-form" onSubmit={handlePetSubmit}>
                <label className="field">
                  <span>Nombre</span>
                  <input
                    required
                    value={petFormState.name}
                    onChange={(event) =>
                      setPetFormState((current) => ({ ...current, name: event.target.value }))
                    }
                  />
                </label>

                <label className="field">
                  <span>Especie</span>
                  <input
                    required
                    value={petFormState.species}
                    onChange={(event) =>
                      setPetFormState((current) => ({ ...current, species: event.target.value }))
                    }
                  />
                </label>

                <label className="field">
                  <span>Raza opcional</span>
                  <input
                    value={petFormState.breed}
                    onChange={(event) =>
                      setPetFormState((current) => ({ ...current, breed: event.target.value }))
                    }
                  />
                </label>

                <label className="field">
                  <span>Sexo opcional</span>
                  <select
                    value={petFormState.sex}
                    onChange={(event) =>
                      setPetFormState((current) => ({ ...current, sex: event.target.value }))
                    }
                  >
                    <option value="">Sin especificar</option>
                    <option value="Macho">Macho</option>
                    <option value="Hembra">Hembra</option>
                  </select>
                </label>

                <label className="field">
                  <span>Edad estimada opcional</span>
                  <input
                    value={petFormState.estimated_age}
                    onChange={(event) =>
                      setPetFormState((current) => ({
                        ...current,
                        estimated_age: event.target.value,
                      }))
                    }
                  />
                </label>

                <label className="field">
                  <span>Peso (kg) opcional</span>
                  <input
                    inputMode="decimal"
                    min="0"
                    step="0.01"
                    type="number"
                    value={petFormState.weight_kg}
                    onChange={(event) =>
                      setPetFormState((current) => ({ ...current, weight_kg: event.target.value }))
                    }
                  />
                </label>

                <label className="field">
                  <span>Alergias opcional</span>
                  <textarea
                    rows={2}
                    value={petFormState.allergies}
                    onChange={(event) =>
                      setPetFormState((current) => ({ ...current, allergies: event.target.value }))
                    }
                  />
                </label>

                <label className="field">
                  <span>Condiciones crónicas opcional</span>
                  <textarea
                    rows={2}
                    value={petFormState.chronic_conditions}
                    onChange={(event) =>
                      setPetFormState((current) => ({
                        ...current,
                        chronic_conditions: event.target.value,
                      }))
                    }
                  />
                </label>

                <div className="modal-actions">
                  <button className="secondary-button" onClick={closePetEditModal} type="button">
                    Cancelar
                  </button>
                  <button className="primary-button" disabled={isSavingPet} type="submit">
                    {isSavingPet ? "Guardando..." : "Guardar cambios"}
                  </button>
                </div>
              </form>
            )}
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

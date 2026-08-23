"use client";

import { ChevronDown, Pencil, Power, PowerOff, Truck, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { useCurrentUser } from "@/features/auth/current-user-context";
import { getApiErrorMessage } from "@/lib/api";
import {
  activateSupplier,
  createSupplier,
  deactivateSupplier,
  getSuppliers,
  updateSupplier,
} from "@/services/suppliers";
import type { Supplier } from "@/types/api";

type SupplierFormState = {
  id: string | null;
  name: string;
  document_id: string;
  phone: string;
  email: string;
  address: string;
  notes: string;
};

const emptySupplierFormState: SupplierFormState = {
  id: null,
  name: "",
  document_id: "",
  phone: "",
  email: "",
  address: "",
  notes: "",
};

type SuppliersSectionProps = {
  isExpanded: boolean;
  onToggle: () => void;
};

export function SuppliersSection({ isExpanded, onToggle }: SuppliersSectionProps) {
  const { role } = useCurrentUser();
  const canManageCatalog = role === "clinic_admin";
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [formState, setFormState] = useState<SupplierFormState | null>(null);

  useEffect(() => {
    let isCurrent = true;

    async function loadSuppliers() {
      setIsLoading(true);
      try {
        const response = await getSuppliers({ include_inactive: true });
        if (isCurrent) {
          setSuppliers(response.data);
          setMessage(null);
        }
      } catch (error) {
        if (isCurrent) {
          setMessage(getApiErrorMessage(error));
        }
      } finally {
        if (isCurrent) {
          setIsLoading(false);
        }
      }
    }

    void loadSuppliers();

    return () => {
      isCurrent = false;
    };
  }, []);

  function replaceSupplier(supplier: Supplier) {
    setSuppliers((current) =>
      current.map((existing) => (existing.id === supplier.id ? supplier : existing)),
    );
  }

  function openNewSupplierForm() {
    setFormState(emptySupplierFormState);
    setMessage(null);
  }

  function openEditSupplierForm(supplier: Supplier) {
    setFormState({
      id: supplier.id,
      name: supplier.name,
      document_id: supplier.document_id ?? "",
      phone: supplier.phone ?? "",
      email: supplier.email ?? "",
      address: supplier.address ?? "",
      notes: supplier.notes ?? "",
    });
    setMessage(null);
  }

  async function handleSaveSupplier(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!formState || !canManageCatalog) {
      return;
    }

    const trimmedName = formState.name.trim();
    if (!trimmedName) {
      setMessage("Ingresa un nombre para el proveedor.");
      return;
    }

    setIsSaving(true);
    setMessage(null);

    try {
      const payload = {
        name: trimmedName,
        document_id: formState.document_id.trim() || null,
        phone: formState.phone.trim() || null,
        email: formState.email.trim() || null,
        address: formState.address.trim() || null,
        notes: formState.notes.trim() || null,
      };
      if (formState.id) {
        const response = await updateSupplier(formState.id, payload);
        replaceSupplier(response.data);
      } else {
        const response = await createSupplier(payload);
        setSuppliers((current) => [...current, response.data]);
      }
      setFormState(null);
    } catch (error) {
      setMessage(getApiErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleToggleSupplier(supplier: Supplier) {
    if (!canManageCatalog) {
      return;
    }

    setIsSaving(true);
    setMessage(null);

    try {
      const response = supplier.is_active
        ? await deactivateSupplier(supplier.id)
        : await activateSupplier(supplier.id);
      replaceSupplier(response.data);
    } catch (error) {
      setMessage(getApiErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }

  const sortedSuppliers = [...suppliers].sort((a, b) => a.name.localeCompare(b.name));

  return (
    <section className="panel settings-section-card">
      <button
        aria-expanded={isExpanded}
        className="settings-section-card__header"
        type="button"
        onClick={onToggle}
      >
        <span className="settings-section-card__icon" aria-hidden="true">
          <Truck size={20} />
        </span>
        <span className="settings-section-card__copy">
          <strong>Proveedores</strong>
          <small>Directorio usado al registrar compras de inventario.</small>
        </span>
        <ChevronDown aria-hidden="true" size={16} />
      </button>

      {isExpanded ? (
        <div className="settings-section-card__content">
          {message ? <div className="error-state">{message}</div> : null}

          <div className="modal-actions">
            <button
              className="primary-button"
              disabled={!canManageCatalog || isSaving}
              onClick={openNewSupplierForm}
              type="button"
            >
              Nuevo proveedor
            </button>
          </div>

          {isLoading ? (
            <div className="empty-state">Cargando proveedores…</div>
          ) : sortedSuppliers.length === 0 ? (
            <div className="empty-state">No hay proveedores configurados.</div>
          ) : (
            <section className="record-card-list" aria-label="Proveedores">
              {sortedSuppliers.map((supplier) => (
                <article className="record-card clinic-team-card" key={supplier.id}>
                  <div>
                    <div className="record-card__title-row">
                      <h3>{supplier.name}</h3>
                      <span
                        className={supplier.is_active ? "badge badge--success" : "badge"}
                      >
                        {supplier.is_active ? "Activo" : "Inactivo"}
                      </span>
                    </div>
                    <p>
                      {[supplier.document_id, supplier.phone, supplier.email]
                        .filter(Boolean)
                        .join(" · ") || "Sin datos de contacto"}
                    </p>
                    <div className="record-card__actions">
                      <button
                        className="secondary-button"
                        disabled={!canManageCatalog}
                        onClick={() => openEditSupplierForm(supplier)}
                        type="button"
                      >
                        <Pencil aria-hidden="true" size={16} />
                        Editar
                      </button>
                      <button
                        className="secondary-button"
                        disabled={!canManageCatalog || isSaving}
                        onClick={() => void handleToggleSupplier(supplier)}
                        type="button"
                      >
                        {supplier.is_active ? (
                          <PowerOff aria-hidden="true" size={16} />
                        ) : (
                          <Power aria-hidden="true" size={16} />
                        )}
                        {supplier.is_active ? "Desactivar" : "Activar"}
                      </button>
                    </div>
                  </div>
                </article>
              ))}
            </section>
          )}

          {formState ? (
            <form className="form-grid" onSubmit={handleSaveSupplier}>
              <div className="record-card__title-row">
                <h3>{formState.id ? "Editar proveedor" : "Nuevo proveedor"}</h3>
                <button
                  aria-label="Cerrar formulario"
                  className="icon-button"
                  onClick={() => setFormState(null)}
                  type="button"
                >
                  <X aria-hidden="true" size={16} />
                </button>
              </div>
              <label className="field">
                <span>Nombre</span>
                <input
                  maxLength={255}
                  required
                  value={formState.name}
                  onChange={(event) =>
                    setFormState((current) =>
                      current ? { ...current, name: event.target.value } : current,
                    )
                  }
                />
              </label>
              <label className="field">
                <span>Documento / RUC (opcional)</span>
                <input
                  value={formState.document_id}
                  onChange={(event) =>
                    setFormState((current) =>
                      current
                        ? { ...current, document_id: event.target.value }
                        : current,
                    )
                  }
                />
              </label>
              <label className="field">
                <span>Teléfono (opcional)</span>
                <input
                  value={formState.phone}
                  onChange={(event) =>
                    setFormState((current) =>
                      current ? { ...current, phone: event.target.value } : current,
                    )
                  }
                />
              </label>
              <label className="field">
                <span>Email (opcional)</span>
                <input
                  type="email"
                  value={formState.email}
                  onChange={(event) =>
                    setFormState((current) =>
                      current ? { ...current, email: event.target.value } : current,
                    )
                  }
                />
              </label>
              <label className="field settings-field--full">
                <span>Dirección (opcional)</span>
                <input
                  value={formState.address}
                  onChange={(event) =>
                    setFormState((current) =>
                      current ? { ...current, address: event.target.value } : current,
                    )
                  }
                />
              </label>
              <label className="field settings-field--full">
                <span>Notas (opcional)</span>
                <input
                  value={formState.notes}
                  onChange={(event) =>
                    setFormState((current) =>
                      current ? { ...current, notes: event.target.value } : current,
                    )
                  }
                />
              </label>
              <div className="modal-actions">
                <button
                  className="secondary-button"
                  onClick={() => setFormState(null)}
                  type="button"
                >
                  Cancelar
                </button>
                <button
                  className="primary-button"
                  disabled={!canManageCatalog || isSaving}
                  type="submit"
                >
                  {formState.id ? "Guardar cambios" : "Crear proveedor"}
                </button>
              </div>
            </form>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

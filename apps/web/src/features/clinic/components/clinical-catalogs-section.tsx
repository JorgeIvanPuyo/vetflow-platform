"use client";

import {
  ChevronDown,
  ChevronUp,
  Pencil,
  Power,
  PowerOff,
  Stethoscope,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { useCurrentUser } from "@/features/auth/current-user-context";
import { getApiErrorMessage } from "@/lib/api";
import {
  activateCatalogItem,
  createCatalogItem,
  deactivateCatalogItem,
  getCatalogItems,
  reorderCatalogItems,
  updateCatalogItem,
} from "@/services/catalogs";
import type { CatalogItem, CatalogType } from "@/types/api";

const clinicalCatalogConfigs: Array<{
  type: CatalogType;
  label: string;
  description: string;
}> = [
  {
    type: "mucous_membrane",
    label: "Mucosas",
    description: "Opciones del campo Mucosas en el examen clínico.",
  },
  {
    type: "hydration",
    label: "Hidratación",
    description: "Opciones del campo Hidratación en el examen clínico.",
  },
  {
    type: "exam_type",
    label: "Estudios y exámenes",
    description: "Nombres reutilizables para estudios y exámenes solicitados.",
  },
  {
    type: "preventive_care_type",
    label: "Prestaciones preventivas",
    description: "Nombres reutilizables para vacunas y desparasitaciones.",
  },
  {
    type: "document_type",
    label: "Tipos de archivo clínico",
    description: "Categorías disponibles al adjuntar archivos de un paciente.",
  },
  {
    type: "follow_up_template",
    label: "Plantillas de seguimiento",
    description: "Títulos sugeridos al crear un seguimiento.",
  },
];

const CLINICAL_CATALOG_TYPES = clinicalCatalogConfigs.map((config) => config.type);

type CatalogFormState = {
  id: string | null;
  catalogType: CatalogType;
  name: string;
  description: string;
};

type ClinicalCatalogsSectionProps = {
  isExpanded: boolean;
  onToggle: () => void;
};

export function ClinicalCatalogsSection({
  isExpanded,
  onToggle,
}: ClinicalCatalogsSectionProps) {
  const { role } = useCurrentUser();
  const canManageCatalog = role === "clinic_admin";
  const [itemsByType, setItemsByType] = useState<
    Partial<Record<CatalogType, CatalogItem[]>>
  >(() => Object.fromEntries(CLINICAL_CATALOG_TYPES.map((type) => [type, []])));
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [formState, setFormState] = useState<CatalogFormState | null>(null);

  useEffect(() => {
    let isCurrent = true;

    async function loadCatalogs() {
      setIsLoading(true);
      try {
        const responses = await Promise.all(
          clinicalCatalogConfigs.map((config) =>
            getCatalogItems(config.type, { include_inactive: true }),
          ),
        );
        if (!isCurrent) {
          return;
        }
        setItemsByType(
          Object.fromEntries(
            clinicalCatalogConfigs.map((config, index) => [
              config.type,
              responses[index].data,
            ]),
          ),
        );
        setMessage(null);
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

    void loadCatalogs();

    return () => {
      isCurrent = false;
    };
  }, []);

  function setItemsForType(catalogType: CatalogType, items: CatalogItem[]) {
    setItemsByType((current) => ({ ...current, [catalogType]: items }));
  }

  function replaceItem(item: CatalogItem) {
    setItemsByType((current) => ({
      ...current,
      [item.catalog_type]: (current[item.catalog_type] ?? []).map((existing) =>
        existing.id === item.id ? item : existing,
      ),
    }));
  }

  function openNewItemForm(catalogType: CatalogType) {
    setFormState({ id: null, catalogType, name: "", description: "" });
    setMessage(null);
  }

  function openEditItemForm(item: CatalogItem) {
    setFormState({
      id: item.id,
      catalogType: item.catalog_type,
      name: item.name,
      description: item.description ?? "",
    });
    setMessage(null);
  }

  async function handleSaveItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!formState || !canManageCatalog) {
      return;
    }

    const trimmedName = formState.name.trim();
    if (!trimmedName) {
      setMessage("Ingresa un nombre para la opción.");
      return;
    }

    setIsSaving(true);
    setMessage(null);

    try {
      const payload = {
        name: trimmedName,
        description: formState.description.trim() || null,
      };
      if (formState.id) {
        const response = await updateCatalogItem(
          formState.catalogType,
          formState.id,
          payload,
        );
        replaceItem(response.data);
      } else {
        const items = itemsByType[formState.catalogType] ?? [];
        const nextSortOrder =
          items.reduce((max, item) => Math.max(max, item.sort_order), 0) + 10;
        const response = await createCatalogItem(formState.catalogType, {
          ...payload,
          sort_order: nextSortOrder,
        });
        setItemsForType(formState.catalogType, [...items, response.data]);
      }
      setFormState(null);
    } catch (error) {
      setMessage(getApiErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleToggleItem(item: CatalogItem) {
    if (!canManageCatalog) {
      return;
    }

    setIsSaving(true);
    setMessage(null);

    try {
      const response = item.is_active
        ? await deactivateCatalogItem(item.catalog_type, item.id)
        : await activateCatalogItem(item.catalog_type, item.id);
      replaceItem(response.data);
    } catch (error) {
      setMessage(getApiErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleMoveItem(item: CatalogItem, direction: -1 | 1) {
    if (!canManageCatalog) {
      return;
    }

    const ordered = [...(itemsByType[item.catalog_type] ?? [])].sort(
      (a, b) => a.sort_order - b.sort_order,
    );
    const currentIndex = ordered.findIndex((existing) => existing.id === item.id);
    const targetIndex = currentIndex + direction;
    if (currentIndex < 0 || targetIndex < 0 || targetIndex >= ordered.length) {
      return;
    }
    const next = [...ordered];
    const [moved] = next.splice(currentIndex, 1);
    next.splice(targetIndex, 0, moved);

    setIsSaving(true);
    setMessage(null);

    try {
      const response = await reorderCatalogItems(
        item.catalog_type,
        next.map((entry, index) => ({
          id: entry.id,
          sort_order: (index + 1) * 10,
        })),
      );
      setItemsForType(item.catalog_type, response.data);
    } catch (error) {
      setMessage(getApiErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="panel settings-section-card">
      <button
        aria-expanded={isExpanded}
        className="settings-section-card__header"
        type="button"
        onClick={onToggle}
      >
        <span className="settings-section-card__icon" aria-hidden="true">
          <Stethoscope size={20} />
        </span>
        <span className="settings-section-card__copy">
          <strong>Catálogos clínicos</strong>
          <small>Opciones seleccionables usadas durante la consulta.</small>
        </span>
        <ChevronDown aria-hidden="true" size={16} />
      </button>

      {isExpanded ? (
        <div className="settings-section-card__content">
          {message ? <div className="error-state">{message}</div> : null}

          {isLoading ? (
            <div className="empty-state">Cargando catálogos clínicos…</div>
          ) : (
            clinicalCatalogConfigs.map((config) => {
              const items = [...(itemsByType[config.type] ?? [])].sort(
                (a, b) => a.sort_order - b.sort_order,
              );

              return (
                <div key={config.type}>
                  <div className="record-card__title-row">
                    <h3>{config.label}</h3>
                    <button
                      className="primary-button"
                      disabled={!canManageCatalog || isSaving}
                      onClick={() => openNewItemForm(config.type)}
                      type="button"
                    >
                      Nueva opción
                    </button>
                  </div>
                  <p>{config.description}</p>

                  {items.length === 0 ? (
                    <div className="empty-state">
                      No hay opciones configuradas para {config.label.toLowerCase()}.
                    </div>
                  ) : (
                    <section
                      className="record-card-list"
                      aria-label={`Opciones de ${config.label}`}
                    >
                      {items.map((item, index) => (
                        <article className="record-card clinic-team-card" key={item.id}>
                          <div>
                            <div className="record-card__title-row">
                              <h3>{item.name}</h3>
                              <span
                                className={item.is_active ? "badge badge--success" : "badge"}
                              >
                                {item.is_active ? "Activa" : "Inactiva"}
                              </span>
                            </div>
                            {item.description ? <p>{item.description}</p> : null}
                            <div className="record-card__actions">
                              <button
                                aria-label={`Subir opción ${item.name}`}
                                className="icon-button"
                                disabled={!canManageCatalog || index === 0 || isSaving}
                                onClick={() => void handleMoveItem(item, -1)}
                                type="button"
                              >
                                <ChevronUp aria-hidden="true" size={16} />
                              </button>
                              <button
                                aria-label={`Bajar opción ${item.name}`}
                                className="icon-button"
                                disabled={
                                  !canManageCatalog ||
                                  index === items.length - 1 ||
                                  isSaving
                                }
                                onClick={() => void handleMoveItem(item, 1)}
                                type="button"
                              >
                                <ChevronDown aria-hidden="true" size={16} />
                              </button>
                              <button
                                className="secondary-button"
                                disabled={!canManageCatalog}
                                onClick={() => openEditItemForm(item)}
                                type="button"
                              >
                                <Pencil aria-hidden="true" size={16} />
                                Editar
                              </button>
                              <button
                                className="secondary-button"
                                disabled={!canManageCatalog || isSaving}
                                onClick={() => void handleToggleItem(item)}
                                type="button"
                              >
                                {item.is_active ? (
                                  <PowerOff aria-hidden="true" size={16} />
                                ) : (
                                  <Power aria-hidden="true" size={16} />
                                )}
                                {item.is_active ? "Desactivar" : "Activar"}
                              </button>
                            </div>
                          </div>
                        </article>
                      ))}
                    </section>
                  )}
                </div>
              );
            })
          )}

          {formState ? (
            <form className="form-grid" onSubmit={handleSaveItem}>
              <div className="record-card__title-row">
                <h3>
                  {formState.id ? "Editar opción de " : "Nueva opción de "}
                  {
                    clinicalCatalogConfigs.find(
                      (config) => config.type === formState.catalogType,
                    )?.label
                  }
                </h3>
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
                <span>Descripción (opcional)</span>
                <input
                  value={formState.description}
                  onChange={(event) =>
                    setFormState((current) =>
                      current
                        ? { ...current, description: event.target.value }
                        : current,
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
                  {formState.id ? "Guardar cambios" : "Crear opción"}
                </button>
              </div>
            </form>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

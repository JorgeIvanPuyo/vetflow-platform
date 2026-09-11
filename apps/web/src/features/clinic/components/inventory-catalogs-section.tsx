"use client";

import {
  Boxes,
  ChevronDown,
  ChevronUp,
  Pencil,
  Power,
  PowerOff,
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

const CATEGORY_TYPE: CatalogType = "inventory_category";
const SUBCATEGORY_TYPE: CatalogType = "inventory_subcategory";

type CatalogFormState = {
  id: string | null;
  catalogType: CatalogType;
  name: string;
  description: string;
  parentId: string;
};

type InventoryCatalogsSectionProps = {
  isExpanded: boolean;
  onToggle: () => void;
};

export function InventoryCatalogsSection({
  isExpanded,
  onToggle,
}: InventoryCatalogsSectionProps) {
  const { role } = useCurrentUser();
  const canManageCatalog = role === "clinic_admin";
  const [categories, setCategories] = useState<CatalogItem[]>([]);
  const [subcategories, setSubcategories] = useState<CatalogItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [formState, setFormState] = useState<CatalogFormState | null>(null);

  useEffect(() => {
    let isCurrent = true;

    async function loadCatalogs() {
      setIsLoading(true);
      try {
        const [categoryResponse, subcategoryResponse] = await Promise.all([
          getCatalogItems(CATEGORY_TYPE, { include_inactive: true }),
          getCatalogItems(SUBCATEGORY_TYPE, { include_inactive: true }),
        ]);
        if (!isCurrent) {
          return;
        }
        setCategories(categoryResponse.data);
        setSubcategories(subcategoryResponse.data);
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

  function itemsForType(catalogType: CatalogType): CatalogItem[] {
    return catalogType === CATEGORY_TYPE ? categories : subcategories;
  }

  function setItemsForType(catalogType: CatalogType, items: CatalogItem[]) {
    if (catalogType === CATEGORY_TYPE) {
      setCategories(items);
    } else {
      setSubcategories(items);
    }
  }

  function replaceItem(item: CatalogItem) {
    setItemsForType(
      item.catalog_type,
      itemsForType(item.catalog_type).map((existing) =>
        existing.id === item.id ? item : existing,
      ),
    );
  }

  function categoryName(categoryId: string | null): string | null {
    if (!categoryId) {
      return null;
    }
    return categories.find((category) => category.id === categoryId)?.name ?? null;
  }

  function openNewItemForm(catalogType: CatalogType) {
    setFormState({
      id: null,
      catalogType,
      name: "",
      description: "",
      parentId: "",
    });
    setMessage(null);
  }

  function openEditItemForm(item: CatalogItem) {
    setFormState({
      id: item.id,
      catalogType: item.catalog_type,
      name: item.name,
      description: item.description ?? "",
      parentId: item.parent_id ?? "",
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
    if (formState.catalogType === SUBCATEGORY_TYPE && !formState.parentId) {
      setMessage("Selecciona la categoría a la que pertenece.");
      return;
    }

    setIsSaving(true);
    setMessage(null);

    try {
      const payload = {
        name: trimmedName,
        description: formState.description.trim() || null,
        parent_id:
          formState.catalogType === SUBCATEGORY_TYPE ? formState.parentId : null,
      };
      if (formState.id) {
        const response = await updateCatalogItem(
          formState.catalogType,
          formState.id,
          payload,
        );
        replaceItem(response.data);
      } else {
        const items = itemsForType(formState.catalogType);
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

    const ordered = [...itemsForType(item.catalog_type)].sort(
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

  const sections: Array<{ type: CatalogType; label: string; description: string }> = [
    {
      type: CATEGORY_TYPE,
      label: "Categorías",
      description: "Categorías disponibles al registrar un artículo de inventario.",
    },
    {
      type: SUBCATEGORY_TYPE,
      label: "Subcategorías",
      description: "Subcategorías opcionales, relacionadas con una categoría.",
    },
  ];

  return (
    <section className="panel settings-section-card">
      <button
        aria-expanded={isExpanded}
        className="settings-section-card__header"
        type="button"
        onClick={onToggle}
      >
        <span className="settings-section-card__icon" aria-hidden="true">
          <Boxes size={20} />
        </span>
        <span className="settings-section-card__copy">
          <strong>Categorías de inventario</strong>
          <small>Categorías y subcategorías usadas al registrar artículos.</small>
        </span>
        <ChevronDown aria-hidden="true" size={16} />
      </button>

      {isExpanded ? (
        <div className="settings-section-card__content">
          {message ? <div className="error-state">{message}</div> : null}

          {isLoading ? (
            <div className="empty-state">Cargando categorías de inventario…</div>
          ) : (
            sections.map((section) => {
              const items = [...itemsForType(section.type)].sort(
                (a, b) => a.sort_order - b.sort_order,
              );

              return (
                <div key={section.type}>
                  <div className="record-card__title-row">
                    <h3>{section.label}</h3>
                    <button
                      className="primary-button"
                      disabled={
                        !canManageCatalog ||
                        isSaving ||
                        (section.type === SUBCATEGORY_TYPE && categories.length === 0)
                      }
                      onClick={() => openNewItemForm(section.type)}
                      type="button"
                    >
                      Nueva opción
                    </button>
                  </div>
                  <p>{section.description}</p>

                  {items.length === 0 ? (
                    <div className="empty-state">
                      No hay opciones configuradas para {section.label.toLowerCase()}.
                    </div>
                  ) : (
                    <section
                      className="record-card-list"
                      aria-label={`Opciones de ${section.label}`}
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
                            {item.parent_id ? (
                              <p>Categoría: {categoryName(item.parent_id) ?? "—"}</p>
                            ) : null}
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
                  {sections.find((section) => section.type === formState.catalogType)?.label}
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
              {formState.catalogType === SUBCATEGORY_TYPE ? (
                <label className="field">
                  <span>Categoría</span>
                  <select
                    required
                    value={formState.parentId}
                    onChange={(event) =>
                      setFormState((current) =>
                        current ? { ...current, parentId: event.target.value } : current,
                      )
                    }
                  >
                    <option value="">Selecciona una categoría</option>
                    {categories
                      .filter((category) => category.is_active)
                      .map((category) => (
                        <option key={category.id} value={category.id}>
                          {category.name}
                        </option>
                      ))}
                  </select>
                </label>
              ) : null}
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

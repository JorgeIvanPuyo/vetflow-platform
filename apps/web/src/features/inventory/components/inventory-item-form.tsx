"use client";

import { Calculator, Package, Save, X } from "lucide-react";
import { FormEvent } from "react";

import {
  calculateSalePricePreview,
  getInventoryCategoryIcon,
  inventoryCategoryOptions,
  InventoryFormState,
  inventoryUnitOptions,
} from "@/features/inventory/components/inventory-helpers";

type InventoryItemFormProps = {
  title: string;
  subtitle: string;
  formState: InventoryFormState;
  onChange: (nextState: InventoryFormState) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancel: () => void;
  isSubmitting: boolean;
  submitLabel: string;
  flowMessage: string | null;
  manualSalePriceOverride: boolean;
  onManualSalePriceOverrideChange: (value: boolean) => void;
  isEdit?: boolean;
};

export function InventoryItemForm({
  title,
  subtitle,
  formState,
  onChange,
  onSubmit,
  onCancel,
  isSubmitting,
  submitLabel,
  flowMessage,
  manualSalePriceOverride,
  onManualSalePriceOverrideChange,
  isEdit = false,
}: InventoryItemFormProps) {
  const salePricePreview = calculateSalePricePreview(formState);

  function updateField<K extends keyof InventoryFormState>(
    field: K,
    value: InventoryFormState[K],
  ) {
    onChange({
      ...formState,
      [field]: value,
    });
  }

  return (
    <form className="page-stack inventory-form-page" onSubmit={onSubmit}>
      <section className="detail-hero inventory-form-hero">
        <button className="back-link inventory-inline-back" type="button" onClick={onCancel}>
          Volver a inventario
        </button>
        <div className="detail-hero__main">
          <span className="inventory-form-hero__icon" aria-hidden="true">
            <Package size={28} />
          </span>
          <div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
        </div>
      </section>

      {flowMessage ? <div className="error-state">{flowMessage}</div> : null}

      <section className="panel">
        <div className="section-heading">
          <p className="eyebrow">1. Categoría</p>
          <h2>Tipo de item</h2>
        </div>
        <div className="choice-grid inventory-category-grid">
          {inventoryCategoryOptions.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`choice-card${formState.category === option.value ? " choice-card--selected" : ""}`}
              onClick={() => updateField("category", option.value)}
            >
              <span className="inventory-choice-icon">{getInventoryCategoryIcon(option.value)}</span>
              <span>{option.label}</span>
              <small>{option.description}</small>
            </button>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <p className="eyebrow">2. Información básica</p>
          <h2>Datos del producto</h2>
        </div>

        <div className="form-grid">
          <label className="field">
            <span>Nombre *</span>
            <input
              value={formState.name}
              onChange={(event) => updateField("name", event.target.value)}
              placeholder="Ej: Amoxicilina 50 mg"
            />
          </label>

          <label className="field">
            <span>Subcategoría</span>
            <input
              value={formState.subcategory}
              onChange={(event) => updateField("subcategory", event.target.value)}
              placeholder="Ej: Antibiótico, Antiinflamatorio..."
            />
          </label>

          <label className="field">
            <span>Unidad de medida *</span>
            <select
              value={formState.unit}
              onChange={(event) => updateField("unit", event.target.value as InventoryFormState["unit"])}
            >
              {inventoryUnitOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Proveedor</span>
            <input
              value={formState.supplier}
              onChange={(event) => updateField("supplier", event.target.value)}
              placeholder="Distribuidora o laboratorio"
            />
          </label>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <p className="eyebrow">3. Control de stock</p>
          <h2>Seguimiento básico</h2>
        </div>

        <div className="form-grid">
          {!isEdit ? (
            <label className="field">
              <span>Stock inicial *</span>
              <input
                inputMode="decimal"
                type="number"
                min="0"
                step="0.01"
                value={formState.current_stock}
                onChange={(event) => updateField("current_stock", event.target.value)}
              />
            </label>
          ) : (
            <div className="clinical-section inventory-readonly-field">
              <strong>Stock actual</strong>
              <span>El stock se actualizará con movimientos en el siguiente módulo.</span>
            </div>
          )}

          <label className="field">
            <span>Stock mínimo *</span>
            <input
              inputMode="decimal"
              type="number"
              min="0"
              step="0.01"
              value={formState.minimum_stock}
              onChange={(event) => updateField("minimum_stock", event.target.value)}
            />
          </label>

          <label className="field">
            <span>Número de lote</span>
            <input
              value={formState.lot_number}
              onChange={(event) => updateField("lot_number", event.target.value)}
              placeholder="Opcional"
            />
          </label>

          <label className="field">
            <span>Fecha de vencimiento</span>
            <input
              type="date"
              value={formState.expiration_date}
              onChange={(event) => updateField("expiration_date", event.target.value)}
            />
          </label>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <p className="eyebrow">4. Precios</p>
          <h2>Configuración ARS</h2>
        </div>

        <div className="form-grid">
          <label className="field">
            <span>Precio de compra (ARS)</span>
            <input
              inputMode="decimal"
              type="number"
              min="0"
              step="0.01"
              value={formState.purchase_price_ars}
              onChange={(event) => updateField("purchase_price_ars", event.target.value)}
              placeholder="0"
            />
          </label>

          <label className="field">
            <span>Margen (%)</span>
            <input
              inputMode="decimal"
              type="number"
              min="0"
              step="0.01"
              value={formState.profit_margin_percentage}
              onChange={(event) => updateField("profit_margin_percentage", event.target.value)}
            />
          </label>

          <label className="field">
            <span>Precio de venta</span>
            <input
              inputMode="decimal"
              type="number"
              min="0"
              step="0.01"
              value={formState.sale_price_ars}
              onChange={(event) => {
                updateField("sale_price_ars", event.target.value);
                onManualSalePriceOverrideChange(Boolean(event.target.value.trim()));
              }}
              placeholder={salePricePreview !== null ? String(salePricePreview) : "Calculado automáticamente"}
            />
          </label>

          <div className="clinical-section inventory-price-preview">
            <strong>
              <Calculator size={16} />
              Vista previa
            </strong>
            <span>
              {salePricePreview !== null
                ? `Precio calculado: ARS ${new Intl.NumberFormat("es-AR", {
                    maximumFractionDigits: 0,
                  }).format(salePricePreview)}`
                : "Agrega precio de compra y margen para calcular el valor de venta."}
            </span>
          </div>
        </div>

        <div className="checkbox-card-list">
          <label className="checkbox-row checkbox-row--card">
            <input
              type="checkbox"
              checked={formState.round_sale_price}
              onChange={(event) => updateField("round_sale_price", event.target.checked)}
            />
            <span>Redondear precio al múltiplo de 10 ARS más cercano</span>
          </label>
          <label className="checkbox-row checkbox-row--card">
            <input
              type="checkbox"
              checked={manualSalePriceOverride}
              onChange={(event) => onManualSalePriceOverrideChange(event.target.checked)}
            />
            <span>Usar precio de venta manual</span>
          </label>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <p className="eyebrow">Notas</p>
          <h2>Detalles adicionales</h2>
        </div>

        <label className="field">
          <span>Notas</span>
          <textarea
            rows={4}
            value={formState.notes}
            onChange={(event) => updateField("notes", event.target.value)}
            placeholder="Indicaciones, conservación, observaciones..."
          />
        </label>
      </section>

      <div className="button-row inventory-form-actions">
        <button className="secondary-button" type="button" onClick={onCancel}>
          <X size={18} />
          Cancelar
        </button>
        <button className="primary-button" type="submit" disabled={isSubmitting}>
          <Save size={18} />
          {isSubmitting ? "Guardando..." : submitLabel}
        </button>
      </div>
    </form>
  );
}

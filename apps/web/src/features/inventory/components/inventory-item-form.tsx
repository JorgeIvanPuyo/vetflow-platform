"use client";

import { Calculator, Package, Save, X } from "lucide-react";
import { FormEvent } from "react";

import {
  calculateInventoryPricePreview,
  formatInventoryCurrency,
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
  onManualSalePriceOverrideChange,
  isEdit = false,
}: InventoryItemFormProps) {
  const pricePreview = calculateInventoryPricePreview(formState, false);

  function updateField<K extends keyof InventoryFormState>(
    field: K,
    value: InventoryFormState[K],
  ) {
    onChange({
      ...formState,
      [field]: value,
    });
  }

  function updatePurchaseTaxMode(value: InventoryFormState["purchase_tax_mode"]) {
    if (value === "standard") {
      onChange({
        ...formState,
        purchase_tax_mode: value,
        purchase_tax_rate_percentage: "21",
      });
      return;
    }
    if (value === "none") {
      onChange({
        ...formState,
        purchase_tax_mode: value,
        purchase_tax_rate_percentage: "0",
      });
      return;
    }
    onChange({
      ...formState,
      purchase_tax_mode: value,
      purchase_tax_rate_percentage:
        formState.purchase_tax_mode === "custom"
          ? formState.purchase_tax_rate_percentage
          : "",
    });
  }

  return (
    <form className="page-stack inventory-form-page" onSubmit={onSubmit} noValidate>
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
          <div className="clinical-section inventory-readonly-field">
            <strong>Código interno</strong>
            <span>
              {formState.internal_code ||
                "El código interno se generará automáticamente al guardar"}
            </span>
          </div>

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
            <span>Marca</span>
            <input
              value={formState.brand}
              onChange={(event) => updateField("brand", event.target.value)}
              placeholder="Laboratorio, línea o marca"
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
          <div className="clinical-section inventory-readonly-field">
            <strong>Stock actual</strong>
            <span>
              {isEdit
                ? `${formState.current_stock || "0"} unidades. El stock se modifica mediante entradas y salidas.`
                : "Todo producto nuevo se crea con stock 0. Luego se actualiza mediante entradas y salidas."}
            </span>
          </div>

          <label className="field">
            <span>Stock mínimo *</span>
            <input
              inputMode="numeric"
              type="number"
              min="0"
              step="1"
              required
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

        <div className="inventory-pricing-sections">
          <section className="inventory-pricing-section" aria-labelledby="purchase-pricing-title">
            <h3 id="purchase-pricing-title">Compra</h3>
            <div className="form-grid">
              <label className="field">
                <span>Precio compra sin IVA</span>
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
                <span>IVA compra (%)</span>
                <select
                  value={formState.purchase_tax_mode}
                  onChange={(event) =>
                    updatePurchaseTaxMode(
                      event.target.value as InventoryFormState["purchase_tax_mode"],
                    )
                  }
                >
                  <option value="standard">IVA 21%</option>
                  <option value="none">Sin IVA</option>
                  <option value="custom">Otro porcentaje</option>
                </select>
              </label>

              {formState.purchase_tax_mode === "custom" ? (
                <label className="field">
                  <span>IVA compra personalizado (%)</span>
                  <input
                    inputMode="decimal"
                    type="number"
                    min="0"
                    max="100"
                    step="0.01"
                    value={formState.purchase_tax_rate_percentage}
                    onChange={(event) =>
                      updateField("purchase_tax_rate_percentage", event.target.value)
                    }
                    placeholder="0"
                  />
                </label>
              ) : null}

              <div className="clinical-section inventory-price-preview">
                <strong>
                  <Calculator size={16} />
                  Costo compra con IVA
                </strong>
                <span>
                  {pricePreview.purchaseWithTax !== null
                    ? formatInventoryCurrency(pricePreview.purchaseWithTax)
                    : "Agrega un precio de compra para ver el total."}
                </span>
                {pricePreview.purchaseTaxAmount !== null ? (
                  <small>
                    IVA compra: {formatInventoryCurrency(pricePreview.purchaseTaxAmount)}
                  </small>
                ) : null}
              </div>
            </div>
          </section>

          <section className="inventory-pricing-section" aria-labelledby="sale-pricing-title">
            <h3 id="sale-pricing-title">Venta</h3>
            <div className="form-grid">
              <label className="field">
                <span>Margen de ganancia (%)</span>
                <input
                  inputMode="decimal"
                  type="number"
                  min="0"
                  step="0.01"
                  value={formState.profit_margin_percentage}
                  onChange={(event) =>
                    updateField("profit_margin_percentage", event.target.value)
                  }
                />
              </label>

              <div className="clinical-section inventory-price-preview">
                <strong>
                  <Calculator size={16} />
                  Precio sugerido
                </strong>
                <span>
                  {pricePreview.saleWithoutTax !== null
                    ? formatInventoryCurrency(pricePreview.saleWithoutTax)
                    : "Agrega los precios para ver el total de venta."}
                </span>
              </div>

              <label className="field">
                <span>Precio final de venta</span>
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
                  placeholder={
                    pricePreview.saleWithoutTax !== null
                      ? String(pricePreview.saleWithoutTax)
                      : "Calculado automáticamente"
                  }
                />
                <small>El precio de venta es el valor final que pagará el cliente.</small>
              </label>
            </div>
          </section>
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

"use client";

import { Calculator, Package, Save, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { useClinic } from "@/features/clinic/clinic-context";
import {
  calculateInventoryPricePreview,
  formatInventoryCurrency,
  getInventoryCategoryIcon,
  inventoryCategoryOptions,
  InventoryFormState,
  inventoryUnitOptions,
} from "@/features/inventory/components/inventory-helpers";
import { getCatalogItems } from "@/services/catalogs";
import { getSuppliers } from "@/services/suppliers";
import type { CatalogItem, Supplier } from "@/types/api";

const MANUAL_SUPPLIER_VALUE = "__manual__";

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
  const { preferences } = useClinic();
  const moneyPreferences = {
    currencyCode: preferences?.currency_code ?? "USD",
    locale: preferences?.locale ?? "es-PA",
  };
  const roundingIncrement = Number(preferences?.money_rounding_increment ?? 10);
  const pricePreview = calculateInventoryPricePreview(
    formState,
    manualSalePriceOverride,
  );
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [inventoryCategories, setInventoryCategories] = useState<CatalogItem[]>([]);

  useEffect(() => {
    let isCurrent = true;

    async function loadSuppliers() {
      try {
        const response = await getSuppliers({ include_inactive: false });
        if (isCurrent) {
          setSuppliers(response.data);
        }
      } catch {
        if (isCurrent) {
          setSuppliers([]);
        }
      }
    }

    async function loadInventoryCategories() {
      try {
        const response = await getCatalogItems("inventory_category", {
          include_inactive: false,
        });
        if (isCurrent) {
          setInventoryCategories(response.data);
        }
      } catch {
        if (isCurrent) {
          setInventoryCategories([]);
        }
      }
    }

    void loadSuppliers();
    void loadInventoryCategories();

    return () => {
      isCurrent = false;
    };
  }, []);

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
          <label className="field">
            <span>Nombre *</span>
            <input
              value={formState.name}
              onChange={(event) => updateField("name", event.target.value)}
              placeholder="Ej: Amoxicilina 50 mg"
            />
          </label>

          <label className="field">
            <span>Categoría de la clínica (opcional)</span>
            <select
              value={formState.category_catalog_item_id}
              onChange={(event) =>
                updateField("category_catalog_item_id", event.target.value)
              }
            >
              <option value="">Sin categoría específica</option>
              {inventoryCategories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
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
            <select
              value={formState.supplier_id || (formState.supplier ? MANUAL_SUPPLIER_VALUE : "")}
              onChange={(event) => {
                const value = event.target.value;
                if (value === MANUAL_SUPPLIER_VALUE || value === "") {
                  onChange({ ...formState, supplier_id: "" });
                  return;
                }
                const selected = suppliers.find((supplier) => supplier.id === value);
                onChange({
                  ...formState,
                  supplier_id: value,
                  supplier: selected?.name ?? formState.supplier,
                });
              }}
            >
              <option value="">Seleccionar del directorio</option>
              {suppliers.map((supplier) => (
                <option key={supplier.id} value={supplier.id}>
                  {supplier.name}
                </option>
              ))}
              <option value={MANUAL_SUPPLIER_VALUE}>Otro (texto libre)</option>
            </select>
            {!formState.supplier_id ? (
              <input
                value={formState.supplier}
                onChange={(event) => updateField("supplier", event.target.value)}
                placeholder="Distribuidora o laboratorio"
              />
            ) : null}
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
                inputMode="numeric"
                type="number"
                min="0"
                step="1"
                required
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
          <h2>Configuración de precios</h2>
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

              <div className="clinical-section inventory-price-preview">
                <strong>
                  <Calculator size={16} />
                  Costo compra con IVA
                </strong>
                <span>
                  {pricePreview.purchaseWithTax !== null
                    ? formatInventoryCurrency(pricePreview.purchaseWithTax, moneyPreferences)
                    : "Agrega un precio de compra para ver el total."}
                </span>
                {pricePreview.purchaseTaxAmount !== null ? (
                  <small>
                    IVA compra: {formatInventoryCurrency(pricePreview.purchaseTaxAmount, moneyPreferences)}
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

              <label className="field">
                <span>Precio venta sin IVA</span>
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
              </label>

              <label className="field">
                <span>IVA venta (%)</span>
                <input
                  inputMode="decimal"
                  type="number"
                  min="0"
                  max="100"
                  step="0.01"
                  value={formState.sale_tax_rate_percentage}
                  onChange={(event) =>
                    updateField("sale_tax_rate_percentage", event.target.value)
                  }
                  placeholder="0"
                />
              </label>

              <div className="clinical-section inventory-price-preview">
                <strong>
                  <Calculator size={16} />
                  Precio venta final con IVA
                </strong>
                <span>
                  {pricePreview.saleWithTax !== null
                    ? formatInventoryCurrency(pricePreview.saleWithTax, moneyPreferences)
                    : "Agrega los precios para ver el total de venta."}
                </span>
                {pricePreview.saleTaxAmount !== null ? (
                  <small>IVA venta: {formatInventoryCurrency(pricePreview.saleTaxAmount, moneyPreferences)}</small>
                ) : null}
              </div>
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
            <span>{`Redondear precio al múltiplo de ${roundingIncrement} más cercano`}</span>
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

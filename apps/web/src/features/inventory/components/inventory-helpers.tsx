import {
  Apple,
  Box,
  Pill,
  ShieldAlert,
  Syringe,
} from "lucide-react";
import type { ReactNode } from "react";
import { formatCurrency, formatPercentage, type MoneyPreferences } from "@/lib/money";
import type {
  CreateInventoryEntryPayload,
  CreateInventoryExitPayload,
  CreateInventoryItemPayload,
  InventoryCategory,
  InventoryExitReason,
  InventoryItem,
  InventoryListFilters,
  InventoryMovement,
  InventoryMovementType,
  InventorySortBy,
  InventorySortOrder,
  InventoryStockStatus,
  InventoryStatusFilter,
  InventoryUnit,
  TenantPreferences,
  UpdateInventoryItemPayload,
} from "@/types/api";

export type InventoryMovementFilter =
  | Extract<InventoryMovementType, "manual_entry" | "manual_exit" | "entry" | "exit" | "reversal">
  | "all";

export const inventoryCategoryOptions: Array<{
  value: InventoryCategory;
  label: string;
  description: string;
}> = [
  { value: "medication", label: "Medicamento", description: "Fármacos y tratamientos" },
  { value: "vaccine", label: "Vacuna", description: "Biológicos preventivos" },
  { value: "supply", label: "Insumo", description: "Material clínico y descartables" },
  { value: "food", label: "Alimento", description: "Nutrición y dietas" },
  { value: "accessory", label: "Accesorio", description: "Collares, correas y accesorios" },
  { value: "other", label: "Otro", description: "Productos varios" },
];

export const inventoryUnitOptions: Array<{
  value: InventoryUnit;
  label: string;
}> = [
  { value: "unit", label: "unidad" },
  { value: "tablet", label: "comprimido" },
  { value: "capsule", label: "cápsula" },
  { value: "ampoule", label: "ampolla" },
  { value: "dose", label: "dosis" },
  { value: "pipette", label: "pipeta" },
  { value: "bottle", label: "frasco" },
  { value: "vial", label: "vial" },
  { value: "syringe", label: "jeringa" },
  { value: "ml", label: "ml" },
  { value: "liter", label: "litro" },
  { value: "gram", label: "gramo" },
  { value: "kg", label: "kg" },
  { value: "pair", label: "par" },
  { value: "box", label: "caja" },
  { value: "package", label: "paquete" },
  { value: "other", label: "otro" },
];

export const inventoryStatusOptions: Array<{
  value: InventoryStatusFilter | "all";
  label: string;
}> = [
  { value: "all", label: "Todos" },
  { value: "active", label: "Activos" },
  { value: "low_stock", label: "Bajo stock" },
  { value: "expiring_soon", label: "Por vencer" },
  { value: "expired", label: "Vencidos" },
  { value: "inactive", label: "Inactivos" },
];

export const inventoryStockStatusOptions: Array<{
  value: InventoryStockStatus | "all";
  label: string;
}> = [
  { value: "all", label: "Todos" },
  { value: "in_stock", label: "Disponible" },
  { value: "low_stock", label: "Stock bajo" },
  { value: "out_of_stock", label: "Agotado" },
  { value: "negative", label: "Stock negativo" },
];

export const inventoryActiveStatusOptions: Array<{
  value: "active" | "inactive";
  label: string;
}> = [
  { value: "active", label: "Activos" },
  { value: "inactive", label: "Inactivos" },
];

export const inventorySortOptions: Array<{
  value: InventorySortBy;
  label: string;
}> = [
  { value: "name", label: "Nombre" },
  { value: "internal_code", label: "Código" },
  { value: "current_stock", label: "Stock" },
  { value: "sale_price_ars", label: "Precio de venta" },
  { value: "updated_at", label: "Última actualización" },
];

export const inventorySortDirectionOptions: Array<{
  value: InventorySortOrder;
  label: string;
}> = [
  { value: "asc", label: "Ascendente" },
  { value: "desc", label: "Descendente" },
];

export const inventoryMovementFilterOptions: Array<{
  value: InventoryMovementFilter;
  label: string;
}> = [
  { value: "all", label: "Todos" },
  { value: "manual_entry", label: "Entradas" },
  { value: "manual_exit", label: "Salidas" },
  { value: "reversal", label: "Reversas" },
];

export const inventoryExitReasonOptions: Array<{
  value: InventoryExitReason;
  label: string;
}> = [
  { value: "sale", label: "Venta" },
  { value: "consultation_use", label: "Uso en consulta" },
  { value: "inventory_adjustment", label: "Ajuste de inventario" },
  { value: "expired_discard", label: "Vencimiento / descarte" },
  { value: "damaged", label: "Dañado" },
  { value: "other", label: "Otro" },
];

export type InventoryFormState = {
  internal_code: string;
  name: string;
  category: InventoryCategory;
  category_catalog_item_id: string;
  subcategory: string;
  brand: string;
  unit: InventoryUnit;
  supplier: string;
  supplier_id: string;
  lot_number: string;
  expiration_date: string;
  current_stock: string;
  minimum_stock: string;
  purchase_tax_mode: "standard" | "none" | "custom";
  purchase_price_ars: string;
  purchase_tax_rate_percentage: string;
  profit_margin_percentage: string;
  sale_price_ars: string;
  sale_tax_rate_percentage: string;
  round_sale_price: boolean;
  notes: string;
};

export type InventoryFilterState = {
  category: InventoryCategory | "all";
  brand: string;
  supplier: string;
  stock_status: InventoryStockStatus | "all";
  active_status: "active" | "inactive";
  sort_by: InventorySortBy;
  sort_direction: InventorySortOrder;
};

export type InventoryEntryFormState = {
  quantity: string;
  total_cost_ars: string;
  unit_cost_ars: string;
  supplier: string;
  notes: string;
};

export type InventoryExitFormState = {
  quantity: string;
  reason: InventoryExitReason;
  unit_sale_price_ars: string;
  notes: string;
};

export const initialInventoryFilterState: InventoryFilterState = {
  category: "all",
  brand: "",
  supplier: "",
  stock_status: "all",
  active_status: "active",
  sort_by: "name",
  sort_direction: "asc",
};

export function getInitialInventoryFormState(
  preferences?: TenantPreferences | null,
): InventoryFormState {
  const defaultPurchaseTaxRate = preferences?.default_purchase_tax_rate ?? "21";
  return {
    internal_code: "",
    name: "",
    category: "medication",
    category_catalog_item_id: "",
    subcategory: "",
    brand: "",
    unit: "unit",
    supplier: "",
    supplier_id: "",
    lot_number: "",
    expiration_date: "",
    current_stock: "0",
    minimum_stock: "0",
    purchase_tax_mode: getPurchaseTaxMode(defaultPurchaseTaxRate, defaultPurchaseTaxRate),
    purchase_price_ars: "",
    purchase_tax_rate_percentage: defaultPurchaseTaxRate,
    profit_margin_percentage: preferences?.default_profit_margin ?? "35",
    sale_price_ars: "",
    sale_tax_rate_percentage: preferences?.default_sale_tax_rate ?? "0",
    round_sale_price: false,
    notes: "",
  };
}

export const initialInventoryEntryFormState: InventoryEntryFormState = {
  quantity: "",
  total_cost_ars: "",
  unit_cost_ars: "",
  supplier: "",
  notes: "",
};

export const initialInventoryExitFormState: InventoryExitFormState = {
  quantity: "",
  reason: "sale",
  unit_sale_price_ars: "",
  notes: "",
};

export function getInventoryCategoryLabel(category: InventoryCategory) {
  return (
    inventoryCategoryOptions.find((option) => option.value === category)?.label ?? "Otro"
  );
}

export function getInventoryUnitLabel(unit: InventoryUnit) {
  return inventoryUnitOptions.find((option) => option.value === unit)?.label ?? "otro";
}

export function getInventoryCategoryIcon(category: InventoryCategory): ReactNode {
  if (category === "medication") {
    return <Pill size={20} />;
  }
  if (category === "vaccine") {
    return <Syringe size={20} />;
  }
  if (category === "food") {
    return <Apple size={20} />;
  }
  if (category === "accessory") {
    return <Box size={20} />;
  }
  if (category === "other") {
    return <ShieldAlert size={20} />;
  }
  return <Box size={20} />;
}

const legacyMoneyPreferences: MoneyPreferences = {
  currencyCode: "ARS",
  locale: "es-AR",
};

export function formatInventoryCurrency(
  value: string | number | null | undefined,
  preferences: MoneyPreferences = legacyMoneyPreferences,
) {
  return formatCurrency(value, preferences);
}

export function formatInventoryPercentage(
  value: string | number | null | undefined,
  locale: string,
) {
  return formatPercentage(value, locale);
}

export function formatInventoryDate(value?: string | null) {
  if (!value) {
    return "No indicado";
  }

  return new Intl.DateTimeFormat("es", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(value));
}

export function formatInventoryDateCompact(value?: string | null) {
  if (!value) {
    return "Sin vencimiento";
  }

  return new Intl.DateTimeFormat("es", {
    day: "numeric",
    month: "short",
  }).format(new Date(value));
}

export function formatInventoryQuantity(
  value: string,
  unit: InventoryUnit,
  locale = legacyMoneyPreferences.locale,
) {
  const numericValue = Number(value);
  const formatted = Number.isInteger(numericValue)
    ? new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(numericValue)
    : new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(numericValue);
  return `${formatted} ${getInventoryUnitLabel(unit)}`;
}

export function formatInventorySignedQuantity(
  quantity: string,
  unit: InventoryUnit,
  movementType: InventoryMovementType,
  locale = legacyMoneyPreferences.locale,
) {
  const direction = getInventoryMovementDirection(movementType);
  const sign = direction > 0 ? "+" : direction < 0 ? "-" : "";
  return `${sign}${formatInventoryQuantity(quantity, unit, locale)}`;
}

export function formatInventoryDateTime(value?: string | null) {
  if (!value) {
    return "No indicado";
  }

  return new Intl.DateTimeFormat("es", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function getInventoryStatusBadges(item: InventoryItem) {
  const badges: Array<{ label: string; className: string }> = [];
  const stockStatus = getInventoryStockStatus(item);

  if (stockStatus === "negative") {
    badges.push({ label: "Stock negativo", className: "badge badge--danger" });
  } else if (stockStatus === "out_of_stock") {
    badges.push({ label: "Agotado", className: "badge badge--danger" });
  } else if (stockStatus === "low_stock") {
    badges.push({ label: "Stock bajo", className: "badge badge--warning" });
  } else {
    badges.push({ label: "Disponible", className: "badge badge--success" });
  }

  if (item.is_expired) {
    badges.push({ label: "Vencido", className: "badge badge--danger" });
  } else if (item.is_expiring_soon) {
    badges.push({ label: "Por vencer", className: "badge badge--warning" });
  }

  if (!item.is_active) {
    badges.push({ label: "Inactivo", className: "badge badge--muted" });
  }

  return badges;
}

export function getInventoryStockStatus(item: InventoryItem): InventoryStockStatus {
  const currentStock = Number(item.current_stock);
  const minimumStock = Number(item.minimum_stock);

  if (currentStock < 0) {
    return "negative";
  }
  if (currentStock === 0) {
    return "out_of_stock";
  }
  if (currentStock <= minimumStock) {
    return "low_stock";
  }
  return "in_stock";
}

export function getInventoryMovementTypeLabel(movementType: InventoryMovementType) {
  if (movementType === "manual_entry") {
    return "Entrada manual";
  }
  if (movementType === "manual_exit") {
    return "Salida manual";
  }
  if (movementType === "initial_stock") {
    return "Stock inicial";
  }
  if (movementType === "purchase") {
    return "Compra";
  }
  if (movementType === "sale") {
    return "Venta";
  }
  if (movementType === "clinical_consumption") {
    return "Consumo clínico";
  }
  if (movementType === "customer_return") {
    return "Devolución de cliente";
  }
  if (movementType === "supplier_return") {
    return "Devolución a proveedor";
  }
  if (movementType === "adjustment_in") {
    return "Ajuste positivo";
  }
  if (movementType === "adjustment_out") {
    return "Ajuste negativo";
  }
  if (movementType === "expiration") {
    return "Vencimiento";
  }
  if (movementType === "loss") {
    return "Pérdida";
  }
  if (movementType === "breakage") {
    return "Rotura";
  }
  if (movementType === "transfer_in") {
    return "Transferencia entrante";
  }
  if (movementType === "transfer_out") {
    return "Transferencia saliente";
  }
  if (movementType === "reversal") {
    return "Reversa";
  }
  if (movementType === "entry") {
    return "Compra / Entrada";
  }
  if (movementType === "exit") {
    return "Salida";
  }
  return "Ajuste";
}

export function getInventoryExitReasonLabel(reason?: string | null) {
  if (!reason) {
    return "Sin motivo";
  }

  return (
    inventoryExitReasonOptions.find((option) => option.value === reason)?.label ?? "Otro"
  );
}

export function getInventoryMovementAmountLabel(
  movement: InventoryMovement,
  preferences: MoneyPreferences = legacyMoneyPreferences,
) {
  if (
    ["entry", "manual_entry", "purchase", "customer_return", "adjustment_in", "transfer_in"].includes(
      movement.movement_type,
    ) &&
    movement.total_cost_ars
  ) {
    return formatInventoryCurrency(movement.total_cost_ars, preferences);
  }

  if (
    [
      "exit",
      "manual_exit",
      "sale",
      "clinical_consumption",
      "supplier_return",
      "adjustment_out",
      "expiration",
      "loss",
      "breakage",
      "transfer_out",
    ].includes(movement.movement_type) &&
    movement.total_sale_price_ars
  ) {
    return formatInventoryCurrency(movement.total_sale_price_ars, preferences);
  }

  return null;
}

export function getInventoryMovementDirection(movementType: InventoryMovementType) {
  if (
    [
      "initial_stock",
      "manual_entry",
      "purchase",
      "customer_return",
      "adjustment_in",
      "transfer_in",
      "entry",
    ].includes(movementType)
  ) {
    return 1;
  }
  if (
    [
      "manual_exit",
      "sale",
      "clinical_consumption",
      "supplier_return",
      "adjustment_out",
      "expiration",
      "loss",
      "breakage",
      "transfer_out",
      "exit",
    ].includes(movementType)
  ) {
    return -1;
  }
  return 0;
}

export function isNonNegativeInteger(value: string) {
  if (!value.trim()) {
    return false;
  }

  const numericValue = Number(value);
  return Number.isInteger(numericValue) && numericValue >= 0;
}

export function isPositiveInteger(value: string) {
  if (!value.trim()) {
    return false;
  }

  const numericValue = Number(value);
  return Number.isInteger(numericValue) && numericValue >= 1;
}

export function validateInventoryForm(
  formState: InventoryFormState,
  _options: { isEdit?: boolean } = {},
) {
  if (!formState.name.trim()) {
    return "Escribe un nombre para el item.";
  }
  if (!formState.category) {
    return "Selecciona una categoría.";
  }
  if (!formState.unit) {
    return "Selecciona una unidad de medida.";
  }

  if (!isNonNegativeInteger(formState.minimum_stock)) {
    return "Ingresa un número entero mayor o igual a 0.";
  }

  const purchasePriceValue = formState.purchase_price_ars
    ? Number(formState.purchase_price_ars)
    : null;
  if (purchasePriceValue !== null && (Number.isNaN(purchasePriceValue) || purchasePriceValue < 0)) {
    return "El precio de compra no puede ser negativo.";
  }

  const purchaseTaxRate = Number(formState.purchase_tax_rate_percentage || "0");
  if (formState.purchase_tax_mode === "custom" && !formState.purchase_tax_rate_percentage.trim()) {
    return "Ingresa un IVA de compra personalizado entre 0 y 100.";
  }
  if (Number.isNaN(purchaseTaxRate) || purchaseTaxRate < 0 || purchaseTaxRate > 100) {
    return "El IVA de compra debe estar entre 0 y 100.";
  }

  const marginValue = formState.profit_margin_percentage
    ? Number(formState.profit_margin_percentage)
    : 0;
  if (Number.isNaN(marginValue) || marginValue < 0) {
    return "El margen no puede ser negativo.";
  }

  const salePriceValue = formState.sale_price_ars ? Number(formState.sale_price_ars) : null;
  if (salePriceValue !== null && (Number.isNaN(salePriceValue) || salePriceValue < 0)) {
    return "El precio de venta no puede ser negativo.";
  }

  const saleTaxRate = Number(formState.sale_tax_rate_percentage || "0");
  if (Number.isNaN(saleTaxRate) || saleTaxRate < 0 || saleTaxRate > 100) {
    return "El impuesto de venta debe estar entre 0 y 100.";
  }

  return null;
}

export function calculateSalePricePreview(
  formState: InventoryFormState,
  roundingIncrement = 10,
) {
  return calculateInventoryPricePreview(formState, false, roundingIncrement).saleWithoutTax;
}

export function calculateInventoryPricePreview(
  formState: InventoryFormState,
  manualSalePriceOverride: boolean,
  roundingIncrement = 10,
) {
  const purchasePrice = parseOptionalNonNegativeNumber(formState.purchase_price_ars);
  const purchaseTaxRate = parseTaxRate(formState.purchase_tax_rate_percentage);
  const margin = parseOptionalNonNegativeNumber(formState.profit_margin_percentage);
  const saleTaxRate = parseTaxRate(formState.sale_tax_rate_percentage);

  const purchaseTaxAmount =
    purchasePrice !== null && purchaseTaxRate !== null
      ? roundMoney(purchasePrice * purchaseTaxRate / 100)
      : null;
  const purchaseWithTax =
    purchasePrice !== null && purchaseTaxAmount !== null
      ? roundMoney(purchasePrice + purchaseTaxAmount)
      : null;

  let saleWithoutTax: number | null = null;
  if (manualSalePriceOverride) {
    saleWithoutTax = parseOptionalNonNegativeNumber(formState.sale_price_ars);
  } else if (purchaseWithTax !== null && margin !== null) {
    const calculatedPrice = roundMoney(purchaseWithTax * (1 + margin / 100));
    const safeIncrement = Number.isFinite(roundingIncrement) && roundingIncrement > 0
      ? roundingIncrement
      : 10;
    saleWithoutTax = formState.round_sale_price
      ? roundMoney(Math.round(calculatedPrice / safeIncrement) * safeIncrement)
      : calculatedPrice;
  }

  const saleTaxAmount =
    saleWithoutTax !== null && saleTaxRate !== null
      ? roundMoney(saleWithoutTax * saleTaxRate / 100)
      : null;
  const saleWithTax =
    saleWithoutTax !== null && saleTaxAmount !== null
      ? roundMoney(saleWithoutTax + saleTaxAmount)
      : null;

  return {
    purchaseTaxAmount,
    purchaseWithTax,
    saleWithoutTax,
    saleTaxAmount,
    saleWithTax,
  };
}

function parseOptionalNonNegativeNumber(value: string) {
  if (!value.trim()) {
    return null;
  }

  const numericValue = Number(value);
  return Number.isNaN(numericValue) || numericValue < 0 ? null : numericValue;
}

function parseTaxRate(value: string) {
  const numericValue = Number(value || "0");
  return Number.isNaN(numericValue) || numericValue < 0 || numericValue > 100
    ? null
    : numericValue;
}

function roundMoney(value: number) {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

export function inventoryFormToCreatePayload(
  formState: InventoryFormState,
  manualSalePriceOverride: boolean,
): CreateInventoryItemPayload {
  const payload: CreateInventoryItemPayload = {
    name: formState.name.trim(),
    category: formState.category,
    unit: formState.unit,
    minimum_stock: Number(formState.minimum_stock || "0"),
    purchase_tax_rate_percentage: Number(
      formState.purchase_tax_rate_percentage || "0",
    ),
    profit_margin_percentage: Number(formState.profit_margin_percentage || "35"),
    sale_tax_rate_percentage: Number(formState.sale_tax_rate_percentage || "0"),
    round_sale_price: formState.round_sale_price,
    is_active: true,
  };

  if (formState.subcategory.trim()) {
    payload.subcategory = formState.subcategory.trim();
  }
  if (formState.brand.trim()) {
    payload.brand = formState.brand.trim();
  }
  if (formState.supplier.trim()) {
    payload.supplier = formState.supplier.trim();
  }
  if (formState.supplier_id) {
    payload.supplier_id = formState.supplier_id;
  }
  if (formState.category_catalog_item_id) {
    payload.category_catalog_item_id = formState.category_catalog_item_id;
  }
  if (formState.lot_number.trim()) {
    payload.lot_number = formState.lot_number.trim();
  }
  if (formState.expiration_date) {
    payload.expiration_date = formState.expiration_date;
  }
  if (formState.purchase_price_ars.trim()) {
    payload.purchase_price_ars = Number(formState.purchase_price_ars);
  }
  if (formState.notes.trim()) {
    payload.notes = formState.notes.trim();
  }
  if (manualSalePriceOverride && formState.sale_price_ars.trim()) {
    payload.sale_price_ars = Number(formState.sale_price_ars);
  }

  return payload;
}

export function inventoryFormToUpdatePayload(
  formState: InventoryFormState,
  manualSalePriceOverride: boolean,
): UpdateInventoryItemPayload {
  const payload: UpdateInventoryItemPayload = {
    name: formState.name.trim(),
    category: formState.category,
    unit: formState.unit,
    minimum_stock: Number(formState.minimum_stock || "0"),
    purchase_tax_rate_percentage: Number(
      formState.purchase_tax_rate_percentage || "0",
    ),
    profit_margin_percentage: Number(formState.profit_margin_percentage || "35"),
    sale_tax_rate_percentage: Number(formState.sale_tax_rate_percentage || "0"),
    round_sale_price: formState.round_sale_price,
  };

  payload.subcategory = formState.subcategory.trim() || null;
  payload.brand = formState.brand.trim() || null;
  payload.supplier = formState.supplier.trim() || null;
  payload.supplier_id = formState.supplier_id || null;
  payload.category_catalog_item_id = formState.category_catalog_item_id || null;
  payload.lot_number = formState.lot_number.trim() || null;
  payload.expiration_date = formState.expiration_date || null;
  payload.purchase_price_ars = formState.purchase_price_ars.trim()
    ? Number(formState.purchase_price_ars)
    : null;
  payload.notes = formState.notes.trim() || null;
  payload.sale_price_ars =
    manualSalePriceOverride && formState.sale_price_ars.trim()
      ? Number(formState.sale_price_ars)
      : null;

  return payload;
}

export function inventoryItemToFormState(item: InventoryItem): InventoryFormState {
  return {
    internal_code: item.internal_code,
    name: item.name,
    category: item.category,
    category_catalog_item_id: item.category_catalog_item_id ?? "",
    subcategory: item.subcategory ?? "",
    brand: item.brand ?? "",
    unit: item.unit,
    supplier: item.supplier ?? "",
    supplier_id: item.supplier_id ?? "",
    lot_number: item.lot_number ?? "",
    expiration_date: item.expiration_date ?? "",
    current_stock: item.current_stock,
    minimum_stock: item.minimum_stock,
    purchase_tax_mode: getPurchaseTaxMode(item.purchase_tax_rate_percentage),
    purchase_price_ars: item.purchase_price_ars ?? "",
    purchase_tax_rate_percentage: String(item.purchase_tax_rate_percentage ?? 0),
    profit_margin_percentage: item.profit_margin_percentage,
    sale_price_ars: item.sale_price_ars ?? "",
    sale_tax_rate_percentage: String(item.sale_tax_rate_percentage ?? 0),
    round_sale_price: item.round_sale_price,
    notes: item.notes ?? "",
  };
}

function getPurchaseTaxMode(
  value?: string | number | null,
  standardRate: string | number = 21,
): InventoryFormState["purchase_tax_mode"] {
  const numericValue = Number(value ?? 0);
  const numericStandardRate = Number(standardRate);
  if (Number.isFinite(numericValue) && Math.abs(numericValue) < 0.005) {
    return "none";
  }
  if (
    Number.isFinite(numericValue) &&
    Number.isFinite(numericStandardRate) &&
    Math.abs(numericValue - numericStandardRate) < 0.005
  ) {
    return "standard";
  }
  return "custom";
}

export function isInventorySalePriceManual(
  item: InventoryItem,
  roundingIncrement = 10,
) {
  if (!item.sale_price_ars) {
    return false;
  }

  const comparableFormState = inventoryItemToFormState(item);
  const calculatedValue = calculateSalePricePreview(comparableFormState, roundingIncrement);
  if (calculatedValue === null) {
    return true;
  }

  return Math.abs(Number(item.sale_price_ars) - calculatedValue) > 0.01;
}

export function buildInventoryListFilters(
  query: string,
  filterState: InventoryFilterState,
  page: number,
  pageSize = 20,
): InventoryListFilters {
  const filters: InventoryListFilters = {
    page,
    page_size: pageSize,
    sort_by: filterState.sort_by,
    sort_direction: filterState.sort_direction,
  };

  if (query.trim()) {
    filters.search = query.trim();
  }
  if (filterState.category !== "all") {
    filters.category = filterState.category;
  }
  if (filterState.brand.trim()) {
    filters.brand = filterState.brand.trim();
  }
  if (filterState.supplier.trim()) {
    filters.supplier = filterState.supplier.trim();
  }
  if (filterState.stock_status !== "all") {
    filters.stock_status = filterState.stock_status;
  }
  if (filterState.active_status !== "active") {
    filters.is_active = false;
  }

  return filters;
}

export function validateInventoryEntryForm(formState: InventoryEntryFormState) {
  if (!isPositiveInteger(formState.quantity)) {
    return "Ingresa una cantidad entera mayor o igual a 1.";
  }

  const totalCostValue = formState.total_cost_ars ? Number(formState.total_cost_ars) : null;
  if (totalCostValue !== null && (Number.isNaN(totalCostValue) || totalCostValue < 0)) {
    return "El costo total no puede ser negativo.";
  }

  const unitCostValue = formState.unit_cost_ars ? Number(formState.unit_cost_ars) : null;
  if (unitCostValue !== null && (Number.isNaN(unitCostValue) || unitCostValue < 0)) {
    return "El costo unitario no puede ser negativo.";
  }

  return null;
}

export function validateInventoryExitForm(
  formState: InventoryExitFormState,
  currentStock: string,
) {
  const quantityValue = Number(formState.quantity);
  if (!isPositiveInteger(formState.quantity)) {
    return "Ingresa una cantidad entera mayor o igual a 1.";
  }

  if (quantityValue > Number(currentStock)) {
    return "No puedes registrar una salida mayor al stock disponible.";
  }

  if (!formState.reason) {
    return "Selecciona el motivo de la salida.";
  }

  const unitSalePriceValue = formState.unit_sale_price_ars
    ? Number(formState.unit_sale_price_ars)
    : null;
  if (
    unitSalePriceValue !== null &&
    (Number.isNaN(unitSalePriceValue) || unitSalePriceValue < 0)
  ) {
    return "El precio unitario no puede ser negativo.";
  }

  return null;
}

export function calculateInventoryEntryUnitCostPreview(formState: InventoryEntryFormState) {
  const quantityValue = Number(formState.quantity);
  const totalCostValue = Number(formState.total_cost_ars);

  if (
    !isPositiveInteger(formState.quantity) ||
    Number.isNaN(totalCostValue) ||
    totalCostValue < 0
  ) {
    return null;
  }

  return totalCostValue / quantityValue;
}

export function inventoryEntryFormToPayload(
  formState: InventoryEntryFormState,
): CreateInventoryEntryPayload {
  const payload: CreateInventoryEntryPayload = {
    quantity: Number(formState.quantity),
  };

  if (formState.total_cost_ars.trim()) {
    payload.total_cost_ars = Number(formState.total_cost_ars);
  }
  if (formState.unit_cost_ars.trim()) {
    payload.unit_cost_ars = Number(formState.unit_cost_ars);
  }
  if (formState.supplier.trim()) {
    payload.supplier = formState.supplier.trim();
  }
  if (formState.notes.trim()) {
    payload.notes = formState.notes.trim();
  }

  return payload;
}

export function inventoryExitFormToPayload(
  formState: InventoryExitFormState,
): CreateInventoryExitPayload {
  const payload: CreateInventoryExitPayload = {
    quantity: Number(formState.quantity),
    reason: formState.reason,
  };

  if (formState.unit_sale_price_ars.trim()) {
    payload.unit_sale_price_ars = Number(formState.unit_sale_price_ars);
  }
  if (formState.notes.trim()) {
    payload.notes = formState.notes.trim();
  }

  return payload;
}

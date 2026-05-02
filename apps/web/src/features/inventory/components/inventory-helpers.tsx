import {
  Apple,
  Box,
  Pill,
  ShieldAlert,
  Syringe,
} from "lucide-react";
import type { ReactNode } from "react";
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
  InventoryStatusFilter,
  InventoryUnit,
  UpdateInventoryItemPayload,
} from "@/types/api";

export type InventoryMovementFilter = Extract<InventoryMovementType, "entry" | "exit"> | "all";

export const inventoryCategoryOptions: Array<{
  value: InventoryCategory;
  label: string;
  description: string;
}> = [
  { value: "medication", label: "Medicamento", description: "Fármacos y tratamientos" },
  { value: "vaccine", label: "Vacuna", description: "Biológicos preventivos" },
  { value: "supply", label: "Insumo", description: "Material clínico y descartables" },
  { value: "food", label: "Alimento", description: "Nutrición y dietas" },
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

export const inventoryMovementFilterOptions: Array<{
  value: InventoryMovementFilter;
  label: string;
}> = [
  { value: "all", label: "Todos" },
  { value: "entry", label: "Entradas" },
  { value: "exit", label: "Salidas" },
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
  name: string;
  category: InventoryCategory;
  subcategory: string;
  unit: InventoryUnit;
  supplier: string;
  lot_number: string;
  expiration_date: string;
  current_stock: string;
  minimum_stock: string;
  purchase_price_ars: string;
  profit_margin_percentage: string;
  sale_price_ars: string;
  round_sale_price: boolean;
  notes: string;
};

export type InventoryFilterState = {
  category: InventoryCategory | "all";
  status: InventoryStatusFilter | "all";
  supplier: string;
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
  status: "active",
  supplier: "",
};

export const initialInventoryFormState: InventoryFormState = {
  name: "",
  category: "medication",
  subcategory: "",
  unit: "unit",
  supplier: "",
  lot_number: "",
  expiration_date: "",
  current_stock: "0",
  minimum_stock: "0",
  purchase_price_ars: "",
  profit_margin_percentage: "35",
  sale_price_ars: "",
  round_sale_price: false,
  notes: "",
};

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
  if (category === "other") {
    return <ShieldAlert size={20} />;
  }
  return <Box size={20} />;
}

export function formatInventoryCurrency(value?: string | null) {
  if (!value) {
    return "ARS -";
  }

  const numericValue = Number(value);
  if (Number.isNaN(numericValue)) {
    return "ARS -";
  }

  return `ARS ${new Intl.NumberFormat("es-AR", {
    maximumFractionDigits: 0,
  }).format(numericValue)}`;
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

export function formatInventoryQuantity(value: string, unit: InventoryUnit) {
  const numericValue = Number(value);
  const formatted = Number.isInteger(numericValue)
    ? new Intl.NumberFormat("es-AR", { maximumFractionDigits: 0 }).format(numericValue)
    : new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 }).format(numericValue);
  return `${formatted} ${getInventoryUnitLabel(unit)}`;
}

export function formatInventorySignedQuantity(
  quantity: string,
  unit: InventoryUnit,
  movementType: InventoryMovementType,
) {
  const sign = movementType === "entry" ? "+" : movementType === "exit" ? "-" : "";
  return `${sign}${formatInventoryQuantity(quantity, unit)}`;
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

  if (Number(item.current_stock) === 0) {
    badges.push({ label: "Sin stock", className: "badge badge--danger" });
  }

  if (item.is_expired) {
    badges.push({ label: "Vencido", className: "badge badge--danger" });
  } else if (item.is_expiring_soon) {
    badges.push({ label: "Por vencer", className: "badge badge--warning" });
  }

  if (item.is_low_stock) {
    badges.push({ label: "Bajo stock", className: "badge badge--danger" });
  }

  if (!item.is_active) {
    badges.push({ label: "Inactivo", className: "badge badge--blue" });
  }

  return badges;
}

export function getInventoryMovementTypeLabel(movementType: InventoryMovementType) {
  if (movementType === "entry") {
    return "Compra / Entrada";
  }
  if (movementType === "exit") {
    return "Salida";
  }
  return "Ajuste";
}

export function getInventoryExitReasonLabel(reason?: InventoryExitReason | null) {
  if (!reason) {
    return "Sin motivo";
  }

  return (
    inventoryExitReasonOptions.find((option) => option.value === reason)?.label ?? "Otro"
  );
}

export function getInventoryMovementAmountLabel(movement: InventoryMovement) {
  if (movement.movement_type === "entry" && movement.total_cost_ars) {
    return formatInventoryCurrency(movement.total_cost_ars);
  }

  if (movement.movement_type === "exit" && movement.total_sale_price_ars) {
    return formatInventoryCurrency(movement.total_sale_price_ars);
  }

  return null;
}

export function validateInventoryForm(
  formState: InventoryFormState,
  options: { isEdit?: boolean } = {},
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

  const stockValue = Number(formState.current_stock || "0");
  if (!options.isEdit && (Number.isNaN(stockValue) || stockValue < 0)) {
    return "El stock inicial no puede ser negativo.";
  }

  const minimumStockValue = Number(formState.minimum_stock || "0");
  if (Number.isNaN(minimumStockValue) || minimumStockValue < 0) {
    return "El stock mínimo no puede ser negativo.";
  }

  const purchasePriceValue = formState.purchase_price_ars
    ? Number(formState.purchase_price_ars)
    : null;
  if (purchasePriceValue !== null && (Number.isNaN(purchasePriceValue) || purchasePriceValue < 0)) {
    return "El precio de compra no puede ser negativo.";
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

  return null;
}

export function calculateSalePricePreview(formState: InventoryFormState) {
  const purchasePrice = Number(formState.purchase_price_ars);
  const margin = Number(formState.profit_margin_percentage);

  if (Number.isNaN(purchasePrice) || purchasePrice < 0 || Number.isNaN(margin) || margin < 0) {
    return null;
  }

  const calculatedPrice = purchasePrice * (1 + margin / 100);
  const roundedPrice = formState.round_sale_price
    ? Math.round(calculatedPrice / 10) * 10
    : calculatedPrice;

  return Math.round(roundedPrice * 100) / 100;
}

export function inventoryFormToCreatePayload(
  formState: InventoryFormState,
  manualSalePriceOverride: boolean,
): CreateInventoryItemPayload {
  const payload: CreateInventoryItemPayload = {
    name: formState.name.trim(),
    category: formState.category,
    unit: formState.unit,
    current_stock: Number(formState.current_stock || "0"),
    minimum_stock: Number(formState.minimum_stock || "0"),
    profit_margin_percentage: Number(formState.profit_margin_percentage || "35"),
    round_sale_price: formState.round_sale_price,
    is_active: true,
  };

  if (formState.subcategory.trim()) {
    payload.subcategory = formState.subcategory.trim();
  }
  if (formState.supplier.trim()) {
    payload.supplier = formState.supplier.trim();
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
    profit_margin_percentage: Number(formState.profit_margin_percentage || "35"),
    round_sale_price: formState.round_sale_price,
  };

  payload.subcategory = formState.subcategory.trim() || null;
  payload.supplier = formState.supplier.trim() || null;
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
    name: item.name,
    category: item.category,
    subcategory: item.subcategory ?? "",
    unit: item.unit,
    supplier: item.supplier ?? "",
    lot_number: item.lot_number ?? "",
    expiration_date: item.expiration_date ?? "",
    current_stock: item.current_stock,
    minimum_stock: item.minimum_stock,
    purchase_price_ars: item.purchase_price_ars ?? "",
    profit_margin_percentage: item.profit_margin_percentage,
    sale_price_ars: item.sale_price_ars ?? "",
    round_sale_price: item.round_sale_price,
    notes: item.notes ?? "",
  };
}

export function isInventorySalePriceManual(item: InventoryItem) {
  if (!item.sale_price_ars) {
    return false;
  }

  const comparableFormState = inventoryItemToFormState(item);
  const calculatedValue = calculateSalePricePreview(comparableFormState);
  if (calculatedValue === null) {
    return true;
  }

  return Math.abs(Number(item.sale_price_ars) - calculatedValue) > 0.01;
}

export function buildInventoryListFilters(
  query: string,
  filterState: InventoryFilterState,
  page: number,
): InventoryListFilters {
  const filters: InventoryListFilters = {
    page,
    page_size: 10,
    sort_by: "name",
    sort_order: "asc",
  };

  if (query.trim()) {
    filters.q = query.trim();
  }
  if (filterState.category !== "all") {
    filters.category = filterState.category;
  }
  if (filterState.status !== "all") {
    filters.status = filterState.status;
  }
  if (filterState.supplier.trim()) {
    filters.supplier = filterState.supplier.trim();
  }

  return filters;
}

export function validateInventoryEntryForm(formState: InventoryEntryFormState) {
  const quantityValue = Number(formState.quantity);
  if (Number.isNaN(quantityValue) || quantityValue <= 0) {
    return "Ingresa una cantidad mayor a cero.";
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
  if (Number.isNaN(quantityValue) || quantityValue <= 0) {
    return "Ingresa una cantidad mayor a cero.";
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
    Number.isNaN(quantityValue) ||
    quantityValue <= 0 ||
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

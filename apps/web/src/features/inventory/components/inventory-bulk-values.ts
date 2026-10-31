import { formatInventoryCurrency } from "./inventory-helpers";

const reasons: Record<string, string> = {
  inventory_item_not_found: "El producto ya no está disponible.",
  catalog_pricing_incomplete: "Completar costo/porcentaje antes de cambiar el precio.",
  sale_price_missing: "Falta el precio de venta vigente.",
  sale_price_would_be_negative: "La disminución produciría un precio negativo.",
  catalog_zero_cost_target: "Con costo cero sólo se puede obtener una venta de cero.",
  catalog_price_limit: "El precio supera el límite monetario permitido.",
  catalog_target_not_representable: "No se alcanza el importe exacto con un porcentaje de 0 a 1000%, dos decimales y el redondeo actual.",
  catalog_target_requires_negative_margin: "El objetivo requiere un porcentaje negativo, fuera del rango permitido.",
  catalog_target_margin_out_of_range: "El objetivo requiere un porcentaje mayor que 1000%.",
  catalog_adjustment_direction: "El redondeo no permite un resultado en la dirección solicitada.",
  supplier_unavailable_after_bulk_operation: "El proveedor original cambió o ya no está disponible.",
  pricing_changed_after_bulk_operation: "Cambió el costo, impuesto o redondeo después de la operación.",
  value_changed_after_bulk_operation: "El producto tiene cambios posteriores.",
};

export function bulkRowReason(reason: string | null) {
  return reason ? reasons[reason] ?? reason : "";
}

export function formatBulkValue(
  box: Record<string, unknown> | null,
  preferences?: { currencyCode: string; locale: string },
) {
  if (!box) return "—";
  const value = box.value;
  if (value && typeof value === "object") {
    const pricing = value as Record<string, unknown>;
    if ("supplier_id" in pricing) return pricing.supplier == null ? "Sin proveedor" : String(pricing.supplier);
    const context = box.pricing_context as Record<string, unknown> | undefined;
    if ("profit_margin_percentage" in pricing) {
      const cost = context?.purchase_price_ars;
      const sale = pricing.sale_price_ars;
      const total = box.sale_price_with_tax_ars;
      const adjustment = box.requested_sale_price_ars != null
        ? ` · Objetivo ${formatInventoryCurrency(String(box.requested_sale_price_ars), preferences)} · Diferencia ${formatInventoryCurrency(String(box.price_difference_ars), preferences)}${box.sale_price_unchanged ? (context?.round_sale_price ? " · Venta sin cambios por redondeo" : " · Venta sin cambios") : ""}` : "";
      return `Costo ${formatInventoryCurrency(cost == null || cost === "None" ? null : String(cost), preferences)} · Porcentaje ${String(pricing.profit_margin_percentage ?? "—")}% · Venta base ${formatInventoryCurrency(sale == null ? null : String(sale), preferences)}${total != null && Number(context?.sale_tax_rate_percentage ?? 0) > 0 ? ` · Con impuesto de venta ${formatInventoryCurrency(String(total), preferences)}` : ""}${adjustment}`;
    }
  }
  return value === null || value === "" ? "Vacío" : String(value);
}

export function bulkFieldLabel(field: string) {
  return ({ sale_price_ars: "Precio y porcentaje", profit_margin_percentage: "Margen y venta", brand: "Marca", supplier: "Proveedor", minimum_stock: "Stock mínimo", is_active: "Actividad" } as Record<string, string>)[field] ?? field;
}

export function bulkRowStatus(status: string) {
  return ({ pending: "Aplicable", changed: "Aplicada", unchanged: "Sin cambios", invalid: "No aplicable", conflict: "Conflicto", reverted: "Revertida", excluded: "Excluida" } as Record<string, string>)[status] ?? status;
}

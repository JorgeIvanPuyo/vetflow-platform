import {
  formatInventoryCurrency,
  formatInventoryDateTime,
  getInventoryCategoryLabel,
  getInventoryUnitLabel,
} from "./inventory-helpers";
import type { MoneyPreferences } from "@/lib/money";
import { getInventoryItems } from "@/services/inventory";
import type { InventoryItem, InventoryListFilters } from "@/types/api";

export const inventoryPrintColumns = [
  { id: "name", label: "Nombre" },
  { id: "sale_price", label: "Precio final" },
  { id: "internal_code", label: "Código interno" },
  { id: "category", label: "Categoría" },
  { id: "brand", label: "Marca" },
  { id: "supplier", label: "Proveedor" },
  { id: "stock", label: "Stock" },
  { id: "unit", label: "Unidad" },
  { id: "purchase_price", label: "Costo de compra (sin IVA)" },
  { id: "status", label: "Estado" },
] as const;
export type InventoryPrintColumn = typeof inventoryPrintColumns[number]["id"];
export const defaultInventoryPrintColumns: InventoryPrintColumn[] = ["name", "sale_price"];
export const MAX_INVENTORY_PRINT_ROWS = 5_000;
const PRINT_PAGE_SIZE = 100;

// Use the same authenticated, tenant-scoped list endpoint and filters as the screen.
export async function loadInventoryPrintItems(
  filters: InventoryListFilters,
  onProgress: (loaded: number, total: number) => void,
  isCancelled: () => boolean,
): Promise<InventoryItem[] | null> {
  const items: InventoryItem[] = [];
  const ids = new Set<string>();
  let total: number | undefined;
  let pages = 1;
  for (let page = 1; page <= pages; page += 1) {
    if (isCancelled()) return null;
    const response = await getInventoryItems({ ...filters, page, page_size: PRINT_PAGE_SIZE });
    if (isCancelled()) return null;
    if (response.meta.total > MAX_INVENTORY_PRINT_ROWS) {
      throw new Error("La impresión supera 5.000 productos. Aplica filtros para reducir el listado.");
    }
    total ??= response.meta.total;
    pages = Math.ceil(total / PRINT_PAGE_SIZE);
    const expectedRows = Math.min(PRINT_PAGE_SIZE, total - items.length);
    if (response.meta.total !== total || response.data.length !== expectedRows ||
        response.data.some((item) => ids.has(item.id))) {
      throw new Error("El inventario cambió durante la carga. Vuelve a generar la vista previa.");
    }
    response.data.forEach((item) => ids.add(item.id));
    items.push(...response.data);
    onProgress(items.length, total);
  }
  return items;
}

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]!);
}

function cellValue(item: InventoryItem, column: InventoryPrintColumn, money: MoneyPreferences) {
  switch (column) {
    case "name": return item.name;
    case "sale_price": return formatInventoryCurrency(item.sale_price_with_tax_ars ?? item.sale_price_ars, money);
    case "internal_code": return item.internal_code;
    case "category": return item.category_catalog_item_name ?? getInventoryCategoryLabel(item.category);
    case "brand": return item.brand || "—";
    case "supplier": return item.supplier_name || item.supplier || "—";
    case "stock": return new Intl.NumberFormat(money.locale).format(Number(item.current_stock));
    case "unit": return getInventoryUnitLabel(item.unit);
    case "purchase_price": return formatInventoryCurrency(item.purchase_price_ars, money);
    case "status": return item.is_active ? "Activo" : "Inactivo";
  }
}

export function buildInventoryPrintDocument(
  items: InventoryItem[],
  selected: InventoryPrintColumn[],
  clinicName: string,
  generatedAt: string,
  money: MoneyPreferences,
) {
  const columns = inventoryPrintColumns.filter((column) => selected.includes(column.id));
  const numeric = (id: InventoryPrintColumn) => ["sale_price", "purchase_price", "stock"].includes(id);
  const heading = columns.map(({ id, label }) => `<th scope="col"${numeric(id) ? ' class="number"' : ""}>${escapeHtml(label)}</th>`).join("");
  const rows = items.map((item) => `<tr>${columns.map(({ id }) => `<td${numeric(id) ? ' class="number"' : ""}>${escapeHtml(cellValue(item, id, money))}</td>`).join("")}</tr>`).join("");
  // This isolated document contains no app navigation, external assets or executable markup.
  return `<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Inventario</title>
<style>
@page { size: ${columns.length > 6 ? "landscape" : "auto"}; margin: 12mm; }
* { box-sizing: border-box; }
body { margin: 0; padding: 20px; background: white; color: #111; font: 12px Arial, sans-serif; }
h1 { margin: 0 0 6px; font-size: 22px; }
p { margin: 4px 0; }
header { margin-bottom: 16px; }
table { border-collapse: collapse; width: 100%; table-layout: fixed; }
th, td { border-bottom: 1px solid #ccc; padding: 7px 5px; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
th { font-weight: bold; }
.number { text-align: right; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
@media print { body { padding: 0; } }
</style></head><body><header><h1>Inventario</h1>
${clinicName ? `<p>${escapeHtml(clinicName)}</p>` : ""}
<p>${escapeHtml(formatInventoryDateTime(generatedAt))} · ${items.length} productos</p></header>
<table><thead><tr>${heading}</tr></thead><tbody>${rows}</tbody></table></body></html>`;
}

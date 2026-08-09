"use client";

import { Building2, Plus, Search, ShoppingCart } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  formatPurchaseCurrency,
  formatPurchaseDate,
  formatPurchaseUser,
  labelPurchaseDocumentType,
  labelPurchaseStatus,
} from "@/features/purchases/components/purchase-helpers";
import { getApiErrorMessage } from "@/lib/api";
import { getPurchases } from "@/services/purchases";
import { getSuppliers } from "@/services/suppliers";
import type { PurchaseDocumentType, PurchaseListFilters, PurchaseSummary, SupplierSummary } from "@/types/api";


export function PurchasesScreen() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryString = searchParams.toString();
  const filters = useMemo(() => readFilters(queryString), [queryString]);
  const [searchValue, setSearchValue] = useState(filters.search ?? "");
  const [items, setItems] = useState<PurchaseSummary[]>([]);
  const [suppliers, setSuppliers] = useState<SupplierSummary[]>([]);
  const [meta, setMeta] = useState({ page: 1, page_size: 20, total: 0, total_pages: 0 });
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => setSearchValue(filters.search ?? ""), [filters.search]);

  const load = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const response = await getPurchases(filters);
      setItems(response.data);
      setMeta(response.meta);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    Promise.all([
      getSuppliers({ is_active: true, page_size: 100, sort_by: "name", sort_direction: "asc" }),
      getSuppliers({ is_active: false, page_size: 100, sort_by: "name", sort_direction: "asc" }),
    ])
      .then(([active, inactive]) => setSuppliers([...active.data, ...inactive.data].sort((left, right) => left.name.localeCompare(right.name))))
      .catch(() => setSuppliers([]));
  }, []);

  function updateFilters(updates: Record<string, string | number | null>) {
    const params = new URLSearchParams(queryString);
    Object.entries(updates).forEach(([key, value]) => {
      if (value === null || value === "") params.delete(key);
      else params.set(key, String(value));
    });
    if (!("page" in updates)) params.delete("page");
    router.push(`${pathname}${params.toString() ? `?${params}` : ""}`, { scroll: false });
  }

  function handleSearch(event: FormEvent) {
    event.preventDefault();
    updateFilters({ search: searchValue.trim() || null });
  }

  const hasFilters = Boolean(
    filters.search || filters.supplier_id || filters.status || filters.document_type || filters.date_from || filters.date_to,
  );

  return (
    <div className="page-stack purchases-page">
      <section className="screen-heading list-page__header">
        <div>
          <p className="eyebrow">Operaciones</p>
          <h1>Compras</h1>
          <p>Registra documentos de compra en borrador sin modificar existencias.</p>
        </div>
        <div className="screen-heading__actions">
          <Link className="secondary-button" href="/suppliers"><Building2 size={18} /> Proveedores</Link>
          <Link className="primary-button" href="/purchases/new"><Plus size={18} /> Nueva compra</Link>
        </div>
      </section>

      <section className="panel purchase-filters" aria-label="Filtros de compras">
        <form className="purchase-search" onSubmit={handleSearch}>
          <label className="field">
            <span>Buscar</span>
            <input
              placeholder="Proveedor o comprobante"
              value={searchValue}
              onChange={(event) => setSearchValue(event.target.value)}
            />
          </label>
          <button className="secondary-button" type="submit"><Search size={17} /> Buscar</button>
        </form>
        <label className="field">
          <span>Proveedor</span>
          <select value={filters.supplier_id ?? ""} onChange={(event) => updateFilters({ supplier_id: event.target.value || null })}>
            <option value="">Todos</option>
            {suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}{supplier.is_active ? "" : " (inactivo)"}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Estado</span>
          <select value={filters.status ?? ""} onChange={(event) => updateFilters({ status: event.target.value || null })}>
            <option value="">Todos</option>
            <option value="draft">Borrador</option>
            <option value="cancelled">Cancelada</option>
          </select>
        </label>
        <label className="field">
          <span>Comprobante</span>
          <select value={filters.document_type ?? ""} onChange={(event) => updateFilters({ document_type: event.target.value || null })}>
            <option value="">Todos</option>
            <option value="invoice">Factura</option>
            <option value="receipt">Recibo</option>
            <option value="ticket">Ticket</option>
            <option value="delivery_note">Remito</option>
            <option value="other">Otro</option>
          </select>
        </label>
        <label className="field">
          <span>Desde</span>
          <input type="date" value={filters.date_from ?? ""} onChange={(event) => updateFilters({ date_from: event.target.value || null })} />
        </label>
        <label className="field">
          <span>Hasta</span>
          <input type="date" value={filters.date_to ?? ""} onChange={(event) => updateFilters({ date_to: event.target.value || null })} />
        </label>
        {hasFilters ? (
          <button className="secondary-button" type="button" onClick={() => router.push(pathname)}>Limpiar filtros</button>
        ) : null}
      </section>

      {errorMessage ? <section className="error-state">{errorMessage}</section> : null}
      {isLoading ? <div className="loading-card" aria-label="Cargando compras" /> : null}

      {!isLoading && !errorMessage && items.length === 0 ? (
        <section className="empty-state purchase-empty-state">
          <ShoppingCart size={30} />
          <h2>{hasFilters ? "No hay compras para estos filtros" : "Todavía no hay compras"}</h2>
          <p>{hasFilters ? "Prueba limpiando o ajustando los filtros." : "Crea el primer borrador para comenzar el historial."}</p>
          {!hasFilters ? <Link className="primary-button" href="/purchases/new">Nueva compra</Link> : null}
        </section>
      ) : null}

      {!isLoading && items.length > 0 ? (
        <>
          <section className="inventory-table-card" aria-label="Listado de compras">
            <div className="inventory-table-scroll">
              <table className="inventory-table purchase-table">
                <thead>
                  <tr>
                    <th>Fecha</th><th>Proveedor</th><th>Comprobante</th><th>Líneas</th>
                    <th>Subtotal</th><th>IVA</th><th>Total</th><th>Estado</th><th>Usuario</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((purchase) => (
                    <tr
                      key={purchase.id}
                      className="inventory-table__row--clickable"
                      role="link"
                      tabIndex={0}
                      aria-label={`Abrir compra de ${purchase.supplier_name}`}
                      onClick={() => router.push(`/purchases/${purchase.id}`)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          router.push(`/purchases/${purchase.id}`);
                        }
                      }}
                    >
                      <td>{formatPurchaseDate(purchase.purchase_date)}</td>
                      <td className="purchase-wrap"><strong>{purchase.supplier_name}</strong><small>{purchase.supplier_tax_id || "Sin identificación fiscal"}</small></td>
                      <td className="purchase-wrap"><strong>{labelPurchaseDocumentType(purchase.document_type)}</strong><small>{purchase.document_number || "Sin número"}</small></td>
                      <td>{purchase.item_count}</td>
                      <td>{formatPurchaseCurrency(purchase.subtotal_ars)}</td>
                      <td>{formatPurchaseCurrency(purchase.tax_total_ars)}</td>
                      <td><strong>{formatPurchaseCurrency(purchase.total_ars)}</strong></td>
                      <td><span className={`badge purchase-status purchase-status--${purchase.status}`}>{labelPurchaseStatus(purchase.status)}</span></td>
                      <td className="purchase-wrap">{formatPurchaseUser(purchase.created_by_user_name, purchase.created_by_user_email)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <nav className="purchase-pagination" aria-label="Paginación de compras">
            <button className="secondary-button" type="button" disabled={meta.page <= 1} onClick={() => updateFilters({ page: meta.page - 1 })}>Anterior</button>
            <span>Página {meta.page} de {Math.max(meta.total_pages, 1)} · {meta.total} compras</span>
            <button className="secondary-button" type="button" disabled={meta.page >= meta.total_pages} onClick={() => updateFilters({ page: meta.page + 1 })}>Siguiente</button>
          </nav>
        </>
      ) : null}
    </div>
  );
}

function readFilters(queryString: string): PurchaseListFilters {
  const params = new URLSearchParams(queryString);
  const status = params.get("status");
  const documentType = params.get("document_type") as PurchaseDocumentType | null;
  return {
    search: params.get("search") || undefined,
    supplier_id: params.get("supplier_id") || undefined,
    status: status === "draft" || status === "cancelled" ? status : undefined,
    document_type: ["invoice", "receipt", "ticket", "delivery_note", "other"].includes(documentType ?? "") ? documentType ?? undefined : undefined,
    date_from: params.get("date_from") || undefined,
    date_to: params.get("date_to") || undefined,
    page: Math.max(1, Number(params.get("page")) || 1),
    page_size: 20,
    sort_by: "purchase_date",
    sort_direction: "desc",
  };
}

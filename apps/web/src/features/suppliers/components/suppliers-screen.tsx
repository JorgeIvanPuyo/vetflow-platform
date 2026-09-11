"use client";

import { ArrowLeft, Building2, Pencil, Plus, Search } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { formatPurchaseDateTime } from "@/features/purchases/components/purchase-helpers";
import { getApiErrorMessage } from "@/lib/api";
import { getSuppliers, updateSupplier } from "@/services/suppliers";
import type { SupplierSummary } from "@/types/api";


export function SuppliersScreen() {
  const [items, setItems] = useState<SupplierSummary[]>([]);
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [page, setPage] = useState(1);
  const [meta, setMeta] = useState({ page: 1, page_size: 20, total: 0, total_pages: 0 });
  const [isLoading, setIsLoading] = useState(true);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const response = await getSuppliers({
        search: appliedQuery || undefined,
        is_active: isActive,
        page,
        page_size: 20,
        sort_by: "name",
        sort_direction: "asc",
      });
      setItems(response.data);
      setMeta(response.meta);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, [appliedQuery, isActive, page]);

  useEffect(() => { void load(); }, [load]);

  function handleSearch(event: FormEvent) {
    event.preventDefault();
    setPage(1);
    setAppliedQuery(query.trim());
  }

  async function toggleSupplier(supplier: SupplierSummary) {
    setUpdatingId(supplier.id);
    setErrorMessage(null);
    try {
      await updateSupplier(supplier.id, { is_active: !supplier.is_active });
      await load();
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setUpdatingId(null);
    }
  }

  const hasFilters = Boolean(appliedQuery || !isActive);

  return (
    <div className="page-stack suppliers-page">
      <section className="screen-heading list-page__header">
        <div>
          <Link className="back-link" href="/purchases"><ArrowLeft size={18} /> Compras</Link>
          <p className="eyebrow">Compras</p>
          <h1>Proveedores</h1>
          <p>Administra el catálogo formal usado al registrar compras.</p>
        </div>
        <Link className="primary-button" href="/suppliers/new"><Plus size={18} /> Nuevo proveedor</Link>
      </section>

      <section className="panel supplier-filters" aria-label="Filtros de proveedores">
        <form className="purchase-search" onSubmit={handleSearch}>
          <label className="field"><span>Buscar</span><input placeholder="Nombre, identificación fiscal o email" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
          <button className="secondary-button" type="submit"><Search size={17} /> Buscar</button>
        </form>
        <label className="field"><span>Estado</span><select value={isActive ? "active" : "inactive"} onChange={(event) => { setIsActive(event.target.value === "active"); setPage(1); }}><option value="active">Activos</option><option value="inactive">Inactivos</option></select></label>
        {hasFilters ? <button className="secondary-button" type="button" onClick={() => { setQuery(""); setAppliedQuery(""); setIsActive(true); setPage(1); }}>Limpiar</button> : null}
      </section>

      {errorMessage ? <section className="error-state" role="alert">{errorMessage}</section> : null}
      {isLoading ? <div className="loading-card" aria-label="Cargando proveedores" /> : null}

      {!isLoading && !errorMessage && items.length === 0 ? (
        <section className="empty-state"><Building2 size={30} /><h2>{hasFilters ? "No hay proveedores para estos filtros" : "Todavía no hay proveedores activos"}</h2><p>{hasFilters ? "Ajusta la búsqueda o el estado." : "Crea el primer proveedor para usarlo en compras."}</p>{!hasFilters ? <Link className="primary-button" href="/suppliers/new">Nuevo proveedor</Link> : null}</section>
      ) : null}

      {!isLoading && items.length > 0 ? (
        <>
          <section className="inventory-table-card" aria-label="Listado de proveedores">
            <div className="inventory-table-scroll">
              <table className="inventory-table supplier-table">
                <thead><tr><th>Nombre</th><th>Identificación fiscal</th><th>Teléfono</th><th>Email</th><th>Estado</th><th>Actualizado</th><th>Acciones</th></tr></thead>
                <tbody>{items.map((supplier) => (
                  <tr key={supplier.id} className="inventory-table__row--static">
                    <td><Link href={`/suppliers/${supplier.id}`}><strong>{supplier.name}</strong></Link></td>
                    <td>{supplier.tax_id || "—"}</td><td>{supplier.phone || "—"}</td><td>{supplier.email || "—"}</td>
                    <td><span className={`badge ${supplier.is_active ? "supplier-status--active" : "supplier-status--inactive"}`}>{supplier.is_active ? "Activo" : "Inactivo"}</span></td>
                    <td>{formatPurchaseDateTime(supplier.updated_at)}</td>
                    <td><div className="supplier-actions"><Link className="icon-button" aria-label={`Editar ${supplier.name}`} href={`/suppliers/${supplier.id}/edit`}><Pencil size={16} /></Link><button className="secondary-button" type="button" disabled={updatingId === supplier.id} onClick={() => void toggleSupplier(supplier)}>{supplier.is_active ? "Inactivar" : "Activar"}</button></div></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </section>
          <nav className="purchase-pagination" aria-label="Paginación de proveedores"><button className="secondary-button" type="button" disabled={meta.page <= 1} onClick={() => setPage((current) => current - 1)}>Anterior</button><span>Página {meta.page} de {Math.max(meta.total_pages, 1)} · {meta.total} proveedores</span><button className="secondary-button" type="button" disabled={meta.page >= meta.total_pages} onClick={() => setPage((current) => current + 1)}>Siguiente</button></nav>
        </>
      ) : null}
    </div>
  );
}

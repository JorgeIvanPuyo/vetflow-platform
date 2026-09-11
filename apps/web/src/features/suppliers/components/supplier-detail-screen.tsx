"use client";

import { ArrowLeft, Pencil } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { formatPurchaseDateTime, formatPurchaseUser } from "@/features/purchases/components/purchase-helpers";
import { getApiErrorMessage } from "@/lib/api";
import { getSupplier, updateSupplier } from "@/services/suppliers";
import type { Supplier } from "@/types/api";


export function SupplierDetailScreen({ supplierId }: { supplierId: string }) {
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const load = useCallback(async () => {
    setErrorMessage(null);
    try { setSupplier((await getSupplier(supplierId)).data); }
    catch (error) { setErrorMessage(getApiErrorMessage(error)); }
  }, [supplierId]);
  useEffect(() => { void load(); }, [load]);

  async function toggleStatus() {
    if (!supplier) return;
    setIsUpdating(true);
    try { setSupplier((await updateSupplier(supplier.id, { is_active: !supplier.is_active })).data); }
    catch (error) { setErrorMessage(getApiErrorMessage(error)); }
    finally { setIsUpdating(false); }
  }

  if (!supplier && !errorMessage) return <div className="loading-card" aria-label="Cargando proveedor" />;
  return (
    <div className="page-stack suppliers-page">
      <section className="screen-heading list-page__header"><div><Link className="back-link" href="/suppliers"><ArrowLeft size={18} /> Proveedores</Link><h1>{supplier?.name ?? "Proveedor"}</h1><p>{supplier ? (supplier.is_active ? "Proveedor activo" : "Proveedor inactivo; se conserva en compras históricas.") : "Proveedor no disponible"}</p></div>{supplier ? <div className="screen-heading__actions"><button className="secondary-button" type="button" disabled={isUpdating} onClick={() => void toggleStatus()}>{supplier.is_active ? "Inactivar" : "Activar"}</button><Link className="primary-button" href={`/suppliers/${supplier.id}/edit`}><Pencil size={17} /> Editar</Link></div> : null}</section>
      {errorMessage ? <section className="error-state" role="alert">{errorMessage}</section> : null}
      {supplier ? <><section className="panel supplier-detail-grid"><div><span>Identificación fiscal</span><strong>{supplier.tax_id || "Sin identificación fiscal"}</strong></div><div><span>Teléfono</span><strong>{supplier.phone || "Sin teléfono"}</strong></div><div><span>Email</span><strong>{supplier.email || "Sin email"}</strong></div><div><span>Estado</span><strong>{supplier.is_active ? "Activo" : "Inactivo"}</strong></div><div className="supplier-detail-wide"><span>Dirección</span><p>{supplier.address || "Sin dirección"}</p></div><div className="supplier-detail-wide"><span>Notas</span><p>{supplier.notes || "Sin notas"}</p></div></section><section className="panel purchase-traceability"><h2>Trazabilidad</h2><dl><div><dt>Creado por</dt><dd>{formatPurchaseUser(supplier.created_by_user_name, supplier.created_by_user_email)}</dd></div><div><dt>Creado el</dt><dd>{formatPurchaseDateTime(supplier.created_at)}</dd></div><div><dt>Actualizado</dt><dd>{formatPurchaseDateTime(supplier.updated_at)}</dd></div><div><dt>ID</dt><dd>{supplier.id}</dd></div></dl></section></> : null}
    </div>
  );
}

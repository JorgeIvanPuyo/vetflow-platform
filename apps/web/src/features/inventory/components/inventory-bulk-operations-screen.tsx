"use client";

import { ArrowLeft, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { formatInventoryDateTime } from "@/features/inventory/components/inventory-helpers";
import { getApiErrorMessage } from "@/lib/api";
import { getInventoryBulkOperations } from "@/services/inventory";
import type { InventoryBulkOperationListItem } from "@/types/api";

export function InventoryBulkOperationsScreen() {
  const router = useRouter();
  const [items, setItems] = useState<InventoryBulkOperationListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function load() {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const response = await getInventoryBulkOperations(1, 20);
      setItems(response.data);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="page-stack inventory-page">
      <section className="screen-heading list-page__header">
        <div>
          <Link className="back-link" href="/inventory">
            <ArrowLeft size={18} />
            Inventario
          </Link>
          <h1>Operaciones grupales</h1>
          <p>{isLoading ? "Cargando historial..." : `${items.length} operaciones recientes`}</p>
        </div>
        <button className="secondary-button" type="button" onClick={() => void load()}>
          <RefreshCw size={18} />
          Actualizar
        </button>
      </section>
      {errorMessage ? <section className="error-state">{errorMessage}</section> : null}
      <section className="inventory-table-card" aria-label="Historial de operaciones grupales">
        <div className="inventory-table-scroll">
          <table className="inventory-table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Ejecutada por</th>
                <th>Tipo</th>
                <th>Productos</th>
                <th>Estado</th>
                <th>Reversión</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.id}
                  aria-label={`Abrir operación grupal ${labelBulkOperation(item.operation_type)}`}
                  className="inventory-table__row--clickable"
                  role="link"
                  tabIndex={0}
                  onClick={() => router.push(`/inventory/bulk-operations/${item.id}`)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      router.push(`/inventory/bulk-operations/${item.id}`);
                    }
                  }}
                >
                  <td>
                    <span className="inventory-table__secondary">
                      <strong>{formatInventoryDateTime(item.created_at)}</strong>
                      <small>Confirmada: {formatInventoryDateTime(item.confirmed_at)}</small>
                    </span>
                  </td>
                  <td>{formatUserName(item.created_by_user_name, item.created_by_user_email)}</td>
                  <td>{labelBulkOperation(item.operation_type)}</td>
                  <td>
                    <span className="inventory-table__secondary">
                      <strong>{item.affected_count} afectados</strong>
                      <small>
                        {item.unchanged_count} sin cambio · {item.conflict_count} conflictos
                      </small>
                    </span>
                  </td>
                  <td>{labelBulkStatus(item.status)}</td>
                  <td>
                    <span className="inventory-table__secondary">
                      <strong>{item.reversed_count} revertidos</strong>
                      <small>{item.reversed_at ? formatInventoryDateTime(item.reversed_at) : "Sin reversión"}</small>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

export function labelBulkOperation(value: string) {
  const labels: Record<string, string> = {
    increase_sale_price_percentage: "Aumentar precio",
    decrease_sale_price_percentage: "Disminuir precio",
    set_profit_margin_percentage: "Establecer margen",
    set_sale_price: "Establecer precio",
    set_brand: "Establecer marca",
    set_supplier: "Establecer proveedor",
    set_minimum_stock: "Stock mínimo",
    activate: "Activar",
    deactivate: "Inactivar",
  };
  return labels[value] ?? value;
}

export function labelBulkStatus(value: string) {
  const labels: Record<string, string> = {
    preview: "Preview",
    confirmed: "Confirmada",
    partially_reversed: "Parcialmente revertida",
    reversed: "Revertida",
    failed: "Fallida",
    expired: "Expirada",
  };
  return labels[value] ?? value;
}

export function formatUserName(name?: string | null, email?: string | null) {
  if (name && email) {
    return `${name} · ${email}`;
  }
  return name || email || "Sin usuario";
}

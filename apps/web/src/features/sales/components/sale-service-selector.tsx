"use client";

import { Plus, Search, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { useCurrentUser } from "@/features/auth/current-user-context";
import { formatCurrency, type MoneyPreferences } from "@/lib/money";
import { getServices } from "@/services/services";
import type { ClinicService } from "@/types/api";
import { filterSaleServices } from "./sale-service-helpers";

type ServiceOptionsProps = {
  services: ClinicService[];
  query: string;
  isLoading: boolean;
  hasError: boolean;
  canConfigure: boolean;
  moneyPreferences: MoneyPreferences;
  onRetry: () => void;
  onSelect: (service: ClinicService) => void;
};

export function SaleServiceOptions({ services, query, isLoading, hasError, canConfigure, moneyPreferences, onRetry, onSelect }: ServiceOptionsProps) {
  if (isLoading) return <p role="status">Cargando servicios...</p>;
  if (hasError) return <div className="error-state" role="alert"><p>No pudimos cargar los servicios. Intenta nuevamente.</p><button type="button" className="secondary-button" onClick={onRetry}>Reintentar</button></div>;
  const visible = filterSaleServices(services, query);
  if (!filterSaleServices(services, "").length) return (
    <div className="empty-state">
      <p>No hay servicios activos disponibles.</p>
      <p>Configura los servicios de la clínica para poder agregarlos a una venta.</p>
      {canConfigure ? <Link className="secondary-button" href="/settings">Ir a Ajustes</Link> : null}
    </div>
  );
  return (
    <>
      <p role="status">{visible.length ? `${visible.length} servicios disponibles` : "No hay servicios que coincidan con la búsqueda."}</p>
      <ul className="sale-service-options" aria-label="Servicios activos">
        {visible.map((service) => (
          <li key={service.id}>
            <button type="button" className="sale-product-selector__option" onClick={() => onSelect(service)}>
              <span><strong>{service.name}</strong><small className="sale-product-selector__metadata">{service.price == null ? "Precio no configurado" : formatCurrency(service.price, moneyPreferences)}</small></span>
              <Plus aria-hidden="true" size={18} />
              <span className="sr-only">Agregar a la venta</span>
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}

export function SaleServiceSelector({ moneyPreferences, onSelect, onClose }: {
  moneyPreferences: MoneyPreferences;
  onSelect: (service: ClinicService) => void;
  onClose: () => void;
}) {
  const { role } = useCurrentUser();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [services, setServices] = useState<ClinicService[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const previousFocus = document.activeElement;
    const dialog = dialogRef.current;
    dialog?.showModal();
    inputRef.current?.focus();
    return () => {
      dialog?.close();
      if (previousFocus instanceof HTMLElement) previousFocus.focus();
    };
  }, []);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setHasError(false);
    setServices([]);
    getServices({ include_inactive: false }).then(({ data }) => {
      if (active) setServices(data);
    }).catch(() => {
      if (active) setHasError(true);
    }).finally(() => {
      if (active) setIsLoading(false);
    });
    return () => { active = false; };
  }, [revision]);

  return (
    <dialog ref={dialogRef} className="panel sale-service-dialog" aria-labelledby="sale-service-title" onCancel={(event) => { event.preventDefault(); onClose(); }}>
      <div className="section-heading-inline">
        <h2 id="sale-service-title">Agregar servicio</h2>
        <button type="button" className="icon-button" aria-label="Cerrar selector de servicios" onClick={onClose}><X aria-hidden="true" size={20} /></button>
      </div>
      <label className="field" htmlFor="sale-service-search"><span>Buscar servicio por nombre</span></label>
      <div className="sale-product-selector__control">
        <Search aria-hidden="true" size={18} />
        <input ref={inputRef} id="sale-service-search" type="search" autoComplete="off" placeholder="Nombre del servicio" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") event.preventDefault(); }} />
      </div>
      <SaleServiceOptions services={services} query={query} isLoading={isLoading} hasError={hasError} canConfigure={role === "clinic_admin"} moneyPreferences={moneyPreferences} onRetry={() => setRevision((value) => value + 1)} onSelect={onSelect} />
      <button type="button" className="secondary-button" onClick={onClose}>Cancelar</button>
    </dialog>
  );
}

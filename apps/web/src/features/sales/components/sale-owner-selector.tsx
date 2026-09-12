"use client";

import { ChevronDown, Search } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { getOwners } from "@/services/owners";
import type { Owner } from "@/types/api";

type Props = {
  ownerId: string;
  ownerName: string;
  onSelect: (owner: Owner | null) => void;
};

const PAGE_SIZE = 30;

export function SaleOwnerSelector({ ownerId, ownerName, onSelect }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [owners, setOwners] = useState<Owner[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [revision, setRevision] = useState(0);
  const [activeIndex, setActiveIndex] = useState(-1);
  const requestId = useRef(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const currentRequest = ++requestId.current;
    setLoading(true);
    setHasError(false);
    setOwners([]);
    setActiveIndex(-1);
    const timeout = window.setTimeout(() => {
      getOwners({ search: query.trim() || undefined, page, pageSize: PAGE_SIZE, sortBy: "full_name" })
        .then(({ data, meta }) => {
          if (requestId.current !== currentRequest) return;
          setOwners(data);
          setTotal(meta.total);
        })
        .catch(() => {
          if (requestId.current === currentRequest) setHasError(true);
        })
        .finally(() => {
          if (requestId.current === currentRequest) setLoading(false);
        });
    }, query.trim() ? 350 : 0);
    return () => {
      window.clearTimeout(timeout);
      requestId.current += 1;
    };
  }, [open, query, page, revision]);

  useEffect(() => {
    if (activeIndex >= 0) {
      document.getElementById(`sale-owner-option-${owners[activeIndex]?.id}`)?.scrollIntoView({ block: "nearest" });
    }
  }, [activeIndex, owners]);

  useEffect(() => {
    function outsideClick(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        requestId.current += 1;
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", outsideClick);
    return () => document.removeEventListener("mousedown", outsideClick);
  }, []);

  function close() {
    requestId.current += 1;
    setOpen(false);
    triggerRef.current?.focus();
  }

  function select(owner: Owner | null) {
    onSelect(owner);
    close();
  }

  function resetResults() {
    // Invalidate immediately, including the interval before the next effect runs.
    requestId.current += 1;
    setLoading(true);
    setOwners([]);
    setActiveIndex(-1);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      if (!loading && !hasError && activeIndex >= 0) select(owners[activeIndex]);
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!owners.length) return;
      setActiveIndex((index) => event.key === "ArrowDown"
        ? (index + 1) % owners.length
        : (index <= 0 ? owners.length : index) - 1);
    }
  }

  return (
    <div className="sale-product-selector" ref={containerRef}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          requestId.current += 1;
          setOpen(false);
        }
      }}
      onKeyDown={(event) => {
        if (open && event.key === "Escape") { event.preventDefault(); event.stopPropagation(); close(); }
      }}>
      <label className="field" htmlFor="sale-owner-trigger"><span>Propietario</span></label>
      <button ref={triggerRef} id="sale-owner-trigger" type="button" className="secondary-button" style={{ width: "100%", justifyContent: "space-between", textAlign: "left", overflowWrap: "anywhere" }}
        aria-expanded={open} aria-controls="sale-owner-dropdown"
        onClick={() => {
          if (open) { close(); return; }
          resetResults(); setQuery(""); setPage(1); setOpen(true);
        }}>
        {ownerId ? ownerName || "Propietario seleccionado" : "Venta de mostrador"}
        <ChevronDown size={18} aria-hidden="true" />
      </button>
      {open ? <div id="sale-owner-dropdown" className="sale-product-selector__dropdown">
        <div className="sale-product-selector__control">
          <Search size={18} aria-hidden="true" />
          <input ref={inputRef} role="combobox" aria-label="Buscar propietario" aria-autocomplete="list"
            aria-expanded={open} aria-controls="sale-owner-options"
            aria-activedescendant={activeIndex >= 0 ? `sale-owner-option-${owners[activeIndex]?.id}` : undefined}
            autoComplete="off" placeholder="Buscar propietario..." value={query}
            onChange={(event) => { resetResults(); setQuery(event.target.value); setPage(1); }} onKeyDown={handleKeyDown} />
        </div>
        <button type="button" className="sale-product-selector__option" onClick={() => select(null)}>Venta de mostrador</button>
        {loading ? <p className="sale-product-selector__state" role="status">Buscando propietarios...</p> : null}
        {!loading && hasError ? <div className="sale-product-selector__state" role="alert">
          <p>No pudimos cargar los propietarios. Intenta nuevamente.</p>
          <button type="button" className="secondary-button" onClick={() => { inputRef.current?.focus(); resetResults(); setRevision((value) => value + 1); }}>Reintentar</button>
        </div> : null}
        {!loading && !hasError && !owners.length ? <p className="sale-product-selector__state" role="status">No encontramos propietarios con ese nombre.</p> : null}
        <div id="sale-owner-options" role="listbox" aria-label="Propietarios" aria-busy={loading}>
          {!loading && !hasError ? owners.map((owner, index) => (
            <button type="button" role="option" tabIndex={-1} key={owner.id} id={`sale-owner-option-${owner.id}`}
              className="sale-product-selector__option" aria-selected={owner.id === ownerId}
              style={index === activeIndex ? { outline: "2px solid var(--color-primary)", outlineOffset: "-2px" } : undefined}
              onMouseDown={(event) => event.preventDefault()} onClick={() => select(owner)}>
              <span>{owner.full_name}</span>
            </button>
          )) : null}
        </div>
        {!loading && !hasError && total > PAGE_SIZE ? <div className="sale-product-selector__footer" style={{ flexWrap: "wrap", alignItems: "center", gap: "0.5rem" }}>
          <button type="button" className="secondary-button" disabled={page === 1}
            onClick={() => { inputRef.current?.focus(); resetResults(); setPage((value) => value - 1); }}>Anterior</button>
          <span role="status">Página {page} de {Math.ceil(total / PAGE_SIZE)} · {total} propietarios</span>
          <button type="button" className="secondary-button" disabled={page * PAGE_SIZE >= total}
            onClick={() => { inputRef.current?.focus(); resetResults(); setPage((value) => value + 1); }}>Siguiente</button>
        </div> : null}
      </div> : null}
    </div>
  );
}

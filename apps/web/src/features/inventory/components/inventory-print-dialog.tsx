"use client";

import { Printer, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useClinic } from "@/features/clinic/clinic-context";
import type { InventoryItem, InventoryListFilters } from "@/types/api";
import {
  buildInventoryPrintDocument,
  defaultInventoryPrintColumns,
  inventoryPrintColumns,
  loadInventoryPrintItems,
  type InventoryPrintColumn,
} from "./inventory-print";
import styles from "./inventory-print.module.css";

type Props = { filters: InventoryListFilters; onClose: () => void };

export function InventoryPrintDialog({ filters, onClose }: Props) {
  const { profile, preferences } = useClinic();
  const [columns, setColumns] = useState<InventoryPrintColumn[]>(defaultInventoryPrintColumns);
  const [preview, setPreview] = useState<{ items: InventoryItem[]; generatedAt: string } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState({ loaded: 0, total: 0 });
  const [error, setError] = useState<string | null>(null);
  const [isFrameReady, setIsFrameReady] = useState(false);
  const frame = useRef<HTMLIFrameElement>(null);
  const dialog = useRef<HTMLElement>(null);
  const cancelled = useRef(false);

  useEffect(() => {
    cancelled.current = false;
    const previousFocus = document.activeElement as HTMLElement | null;
    dialog.current?.focus();
    return () => { cancelled.current = true; previousFocus?.focus(); };
  }, []);

  const documentHtml = useMemo(() => preview ? buildInventoryPrintDocument(
    preview.items, columns, profile?.display_name || profile?.name || "", preview.generatedAt,
    { currencyCode: preferences?.currency_code ?? "ARS", locale: preferences?.locale ?? "es-AR" },
  ) : "", [preview, columns, profile, preferences]);

  function close() {
    cancelled.current = true;
    onClose();
  }

  async function preparePreview() {
    setIsLoading(true);
    setError(null);
    setPreview(null);
    setIsFrameReady(false);
    setProgress({ loaded: 0, total: 0 });
    try {
      const items = await loadInventoryPrintItems(filters, (loaded, total) => {
        setProgress({ loaded, total });
      }, () => cancelled.current);
      if (items && !cancelled.current) {
        if (items.length === 0) setError("No hay productos con los filtros actuales.");
        else setPreview({ items, generatedAt: new Date().toISOString() });
      }
    } catch (cause) {
      if (!cancelled.current) setError(cause instanceof Error ? cause.message : "No se pudo preparar la impresión. Intenta nuevamente.");
    } finally {
      if (!cancelled.current) setIsLoading(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={close}>
      <section ref={dialog} tabIndex={-1} className={`bottom-sheet ${styles.dialog}`} role="dialog"
        aria-modal="true" aria-labelledby="inventory-print-title"
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => {
          if (event.key === "Escape") close();
          if (event.key === "Tab") {
            const controls = dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), iframe');
            const first = controls?.[0];
            const last = controls?.[controls.length - 1];
            if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) {
              event.preventDefault(); last?.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault(); first?.focus();
            }
          }
        }}>
        <div className="bottom-sheet__header">
          <h2 id="inventory-print-title">Imprimir inventario</h2>
          <button className="icon-button" type="button" aria-label="Cerrar impresión" onClick={close}><X size={18} /></button>
        </div>
        <p>Incluye todos los resultados de la búsqueda y filtros actuales, en el mismo orden.</p>
        <fieldset className={styles.columns}>
          <legend>Columnas a incluir</legend>
          {inventoryPrintColumns.map(({ id, label }) => (
            <label key={id}>
              <input type="checkbox" checked={columns.includes(id)} onChange={() => {
                setIsFrameReady(false);
                setColumns((current) => current.includes(id) ? current.filter((column) => column !== id) : [...current, id]);
              }} />
              {label}
            </label>
          ))}
        </fieldset>
        {columns.length === 0 ? <p role="status">Selecciona al menos una columna.</p> : null}
        {isLoading ? <p role="status">Cargando productos… {progress.loaded} de {progress.total || "…"}</p> : null}
        {error ? <div className="error-state" role="alert">{error}</div> : null}
        {preview && columns.length > 0 ? (
          <iframe ref={frame} className={styles.preview} title="Vista previa de inventario"
            sandbox="allow-same-origin allow-modals" srcDoc={documentHtml} onLoad={() => setIsFrameReady(true)} />
        ) : null}
        <div className="modal-actions">
          <button className="secondary-button" type="button" onClick={close}>Volver al listado</button>
          {preview ? (
            <button className="primary-button" type="button" disabled={!columns.length || !isFrameReady}
              onClick={() => { frame.current?.contentWindow?.focus(); frame.current?.contentWindow?.print(); }}>
              <Printer size={18} /> Imprimir
            </button>
          ) : (
            <button className="primary-button" type="button" disabled={!columns.length || isLoading} onClick={() => void preparePreview()}>
              Vista previa
            </button>
          )}
        </div>
      </section>
    </div>
  );
}

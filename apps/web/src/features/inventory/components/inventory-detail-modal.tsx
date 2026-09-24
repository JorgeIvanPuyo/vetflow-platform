"use client";

import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { InventoryDetail } from "./inventory-detail";
import styles from "./inventory-detail.module.css";

export function InventoryDetailModal({ itemId, onClose, onChanged }: {
  itemId: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    const previousFocus = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    element?.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      element?.close();
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus({ preventScroll: true });
    };
  }, []);

  return (
    <dialog ref={dialog} className={styles.modal} aria-label="Detalle del producto"
      onCancel={(event) => { event.preventDefault(); onClose(); }}>
      <div className={styles.toolbar}>
        <span>Detalle del producto</span>
        <button autoFocus type="button" className="icon-button" aria-label="Cerrar detalle" onClick={onClose}>
          <X size={20} />
        </button>
      </div>
      <InventoryDetail itemId={itemId} onClose={onClose} onChanged={onChanged} />
    </dialog>
  );
}

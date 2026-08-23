"use client";

import { X } from "lucide-react";
import { FormEvent, useState } from "react";

import { createTenant } from "@/features/users/services/users";
import { getApiErrorMessage } from "@/lib/api";
import type { TenantOption } from "@/types/api";

export function CreateTenantModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (tenant: TenantOption) => void;
}) {
  const [name, setName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await createTenant({ name: name.trim() });
      onCreated(response.data);
      onClose();
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section
        aria-labelledby="create-tenant-title"
        aria-modal="true"
        className="bottom-sheet"
        role="dialog"
      >
        <div className="bottom-sheet__header">
          <div>
            <h2 id="create-tenant-title">Nueva clínica</h2>
          </div>
          <button
            aria-label="Cerrar"
            className="icon-button"
            disabled={isSubmitting}
            onClick={onClose}
            type="button"
          >
            <X aria-hidden="true" size={20} />
          </button>
        </div>

        <form className="entity-form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Nombre de la clínica</span>
            <input
              autoFocus
              onChange={(event) => setName(event.target.value)}
              required
              type="text"
              value={name}
            />
          </label>

          {errorMessage ? (
            <div className="error-state">{errorMessage}</div>
          ) : null}

          <button
            className="primary-button primary-button--full"
            disabled={isSubmitting || !name.trim()}
            type="submit"
          >
            {isSubmitting ? "Creando..." : "Crear clínica"}
          </button>
        </form>
      </section>
    </div>
  );
}

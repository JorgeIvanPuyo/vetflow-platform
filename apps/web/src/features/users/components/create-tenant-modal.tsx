"use client";

import { Copy, X } from "lucide-react";
import { FormEvent, useState } from "react";

import { createTenant } from "@/features/users/services/users";
import { getApiErrorMessage } from "@/lib/api";
import type { CreateTenantResult, TenantOption } from "@/types/api";

export function CreateTenantModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (tenant: TenantOption) => void;
}) {
  const [name, setName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [adminFullName, setAdminFullName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [result, setResult] = useState<CreateTenantResult | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await createTenant({
        name: name.trim(),
        admin_email: adminEmail.trim(),
        admin_full_name: adminFullName.trim(),
      });
      setResult(response.data);
      onCreated(response.data.tenant);
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

        {result ? (
          <div className="entity-form">
            <div className="success-state">
              Clínica <strong>{result.tenant.name}</strong> creada con{" "}
              <strong>{result.admin_user.email}</strong> como administrador.
            </div>
            {result.password_reset_link ? (
              <label className="field">
                <span>Enlace para establecer contraseña</span>
                <div className="invite-reset-link">
                  <input readOnly value={result.password_reset_link} />
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() =>
                      navigator.clipboard?.writeText(result.password_reset_link ?? "")
                    }
                  >
                    <Copy aria-hidden="true" size={16} /> Copiar
                  </button>
                </div>
                <small>Compártelo con el administrador para que acceda.</small>
              </label>
            ) : null}
            <button
              className="primary-button primary-button--full"
              onClick={onClose}
              type="button"
            >
              Listo
            </button>
          </div>
        ) : (
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

            <label className="field">
              <span>Correo del administrador</span>
              <input
                onChange={(event) => setAdminEmail(event.target.value)}
                required
                type="email"
                value={adminEmail}
              />
            </label>

            <label className="field">
              <span>Nombre del administrador</span>
              <input
                onChange={(event) => setAdminFullName(event.target.value)}
                required
                type="text"
                value={adminFullName}
              />
            </label>

            {errorMessage ? (
              <div className="error-state">{errorMessage}</div>
            ) : null}

            <button
              className="primary-button primary-button--full"
              disabled={
                isSubmitting || !name.trim() || !adminEmail.trim() || !adminFullName.trim()
              }
              type="submit"
            >
              {isSubmitting ? "Creando..." : "Crear clínica"}
            </button>
          </form>
        )}
      </section>
    </div>
  );
}

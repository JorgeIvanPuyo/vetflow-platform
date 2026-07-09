"use client";

import { Copy, X } from "lucide-react";
import { FormEvent, useState } from "react";

import { inviteUser } from "@/features/users/services/users";
import { getApiErrorMessage } from "@/lib/api";
import type { AppRole, InviteUserResult, TenantOption } from "@/types/api";

const ROLE_OPTIONS: { value: AppRole; label: string }[] = [
  { value: "medico_veterinario", label: "Médico veterinario" },
  { value: "contador", label: "Contador" },
  { value: "superadmin", label: "Superadmin" },
];

export function InviteUserModal({
  tenants,
  onClose,
  onInvited,
}: {
  tenants: TenantOption[];
  onClose: () => void;
  onInvited: () => void;
}) {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<AppRole>("medico_veterinario");
  const [tenantId, setTenantId] = useState<string>(tenants[0]?.id ?? "");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [result, setResult] = useState<InviteUserResult | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await inviteUser({
        email: email.trim(),
        full_name: fullName.trim(),
        role,
        tenant_id: tenantId,
      });
      setResult(response.data);
      onInvited();
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section
        aria-labelledby="invite-user-title"
        aria-modal="true"
        className="bottom-sheet"
        role="dialog"
      >
        <div className="bottom-sheet__header">
          <div>
            <h2 id="invite-user-title">Invitar usuario</h2>
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
              Usuario <strong>{result.user.email}</strong> creado correctamente.
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
                      navigator.clipboard?.writeText(
                        result.password_reset_link ?? "",
                      )
                    }
                  >
                    <Copy aria-hidden="true" size={16} /> Copiar
                  </button>
                </div>
                <small>Compártelo con la persona invitada para que acceda.</small>
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
              <span>Correo electrónico</span>
              <input
                autoFocus
                onChange={(event) => setEmail(event.target.value)}
                required
                type="email"
                value={email}
              />
            </label>

            <label className="field">
              <span>Nombre completo</span>
              <input
                onChange={(event) => setFullName(event.target.value)}
                required
                type="text"
                value={fullName}
              />
            </label>

            <label className="field">
              <span>Compañía</span>
              <select
                onChange={(event) => setTenantId(event.target.value)}
                required
                value={tenantId}
              >
                {tenants.map((tenant) => (
                  <option key={tenant.id} value={tenant.id}>
                    {tenant.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>Rol</span>
              <select
                onChange={(event) => setRole(event.target.value as AppRole)}
                value={role}
              >
                {ROLE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            {errorMessage ? (
              <div className="error-state">{errorMessage}</div>
            ) : null}

            <button
              className="primary-button primary-button--full"
              disabled={isSubmitting || !tenantId}
              type="submit"
            >
              {isSubmitting ? "Invitando..." : "Enviar invitación"}
            </button>
          </form>
        )}
      </section>
    </div>
  );
}

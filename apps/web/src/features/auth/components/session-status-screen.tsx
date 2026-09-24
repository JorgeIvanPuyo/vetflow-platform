"use client";

import { Stethoscope } from "lucide-react";
import type { SessionStatus } from "../session-bootstrap";

export function SessionStatusScreen({ status, onRetry, onLogin }: {
  status?: SessionStatus;
  onRetry?: () => void;
  onLogin?: () => void;
}) {
  const failed = status?.endsWith("failed") ?? false;
  const title = status === "waiting-for-server" ? "Conectando con el servidor…"
    : status === "connection-failed" ? "No pudimos conectar con el servidor"
    : status === "authentication-failed" ? "Tu sesión expiró. Vuelve a iniciar sesión."
    : status === "authorization-failed" ? "No tienes acceso a esta aplicación"
    : status === "validating-session" ? "Cargando tus datos de inicio…"
    : "Cargando tu sesión…";
  const description = status === "connection-failed"
    ? "No hemos podido verificar tu sesión porque el servidor no respondió correctamente. Espera unos instantes y vuelve a intentarlo. Si el problema continúa, comunícate con el administrador del sistema."
    : status === "waiting-for-server" ? "El servidor puede tardar unos segundos en iniciar."
    : status === "authorization-failed" ? "Comunícate con el administrador para revisar tu acceso."
    : !failed ? "Estamos verificando tu acceso." : null;
  return (
    <main className="auth-loading-screen" aria-live="polite" aria-busy={!failed}>
      <section className="auth-loading-card">
        <span className="brand__mark brand__mark--large" aria-hidden="true"><Stethoscope size={28} /></span>
        <div>
          <strong>{failed ? title : "VetClinic"}</strong>
          {!failed ? <p>{title}</p> : null}
          {description ? <p>{description}</p> : null}
          {status === "connection-failed" ? <button className="primary-button" type="button" onClick={onRetry}>Reintentar</button> : null}
          {status === "authentication-failed" || status === "authorization-failed" ?
            <button className="primary-button" type="button" onClick={onLogin}>Volver a iniciar sesión</button> : null}
        </div>
        {!failed ? <span className="loading-spinner" aria-hidden="true" /> : null}
      </section>
    </main>
  );
}

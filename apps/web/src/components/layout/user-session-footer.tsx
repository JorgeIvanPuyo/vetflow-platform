"use client";

import { LogOut } from "lucide-react";
import type { User } from "firebase/auth";

function getEmailPrefix(email?: string | null) {
  return email?.split("@")[0] || "";
}

function getInitial(displayName?: string | null, email?: string | null) {
  const source = displayName?.trim() || email?.trim() || "U";

  return source.charAt(0).toUpperCase();
}

export function UserSessionFooter({
  className,
  onLogout,
  user,
}: {
  className: string;
  onLogout: () => void | Promise<void>;
  user: User | null;
}) {
  const email = user?.email ?? "";
  const displayName = user?.displayName?.trim() ?? "";
  const primaryLabel = displayName || getEmailPrefix(email) || "Usuario";

  return (
    <div className={className}>
      <span className="session-profile__avatar" aria-hidden="true">
        {getInitial(displayName, email)}
      </span>

      <span className="session-profile__info">
        <span className="session-profile__name">{primaryLabel}</span>
        {email ? <span className="session-profile__email">{email}</span> : null}
      </span>

      <button
        aria-label="Cerrar sesión"
        className="session-profile__logout"
        type="button"
        onClick={onLogout}
      >
        <LogOut aria-hidden="true" size={18} />
      </button>
    </div>
  );
}

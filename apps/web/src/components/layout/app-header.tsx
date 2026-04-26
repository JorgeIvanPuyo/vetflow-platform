"use client";

import Link from "next/link";

import { useAuth } from "@/features/auth/auth-context";
import { GlobalSearch } from "@/features/search/components/global-search";

export function AppHeader() {
  const { logout, user } = useAuth();

  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link className="brand" href="/">
          <span className="brand__mark">V</span>
          <span>Vetflow</span>
        </Link>

        <nav className="site-nav" aria-label="Navegación principal">
          <Link href="/">Inicio</Link>
          <Link href="/owners">Propietarios</Link>
          <Link href="/patients">Pacientes</Link>
        </nav>

        <GlobalSearch />

        <div className="session-actions">
          <span className="session-actions__email">{user?.email}</span>
          <button className="logout-button" onClick={logout} type="button">
            Cerrar sesión
          </button>
        </div>
      </div>
    </header>
  );
}

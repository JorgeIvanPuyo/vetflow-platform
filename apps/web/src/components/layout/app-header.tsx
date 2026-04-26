"use client";

import { LogOut, Menu, Search, Stethoscope } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/features/auth/auth-context";
import { GlobalSearch } from "@/features/search/components/global-search";

export function AppHeader() {
  const { logout, user } = useAuth();
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <header className="site-header">
      <div className="site-header__bar">
        <button
          className="icon-button"
          type="button"
          aria-expanded={isMenuOpen}
          aria-label="Abrir menú"
          onClick={() => setIsMenuOpen((current) => !current)}
        >
          <Menu aria-hidden="true" size={22} />
        </button>

        <Link className="brand" href="/" aria-label="Ir al dashboard de VetClinic">
          <span className="brand__mark" aria-hidden="true">
            <Stethoscope size={20} />
          </span>
          <span>VetClinic</span>
        </Link>

        <button
          className="icon-button"
          type="button"
          aria-expanded={isSearchOpen}
          aria-label="Buscar"
          onClick={() => setIsSearchOpen((current) => !current)}
        >
          <Search aria-hidden="true" size={22} />
        </button>
      </div>

      {isMenuOpen ? (
        <nav className="mobile-menu" aria-label="Menú principal">
          <Link href="/" onClick={() => setIsMenuOpen(false)}>Dashboard</Link>
          <Link href="/owners" onClick={() => setIsMenuOpen(false)}>Propietarios</Link>
          <Link href="/patients" onClick={() => setIsMenuOpen(false)}>Pacientes</Link>
          <Link href="/agenda" onClick={() => setIsMenuOpen(false)}>Agenda</Link>
          <Link href="/inventario" onClick={() => setIsMenuOpen(false)}>Inventario</Link>
          <Link href="/ajustes" onClick={() => setIsMenuOpen(false)}>Ajustes</Link>
          <button className="logout-button" onClick={logout} type="button">
            <LogOut aria-hidden="true" size={16} />
            <span>Cerrar sesión</span>
          </button>
        </nav>
      ) : null}

      <div className="site-header__desktop-row">
        <nav className="desktop-nav" aria-label="Navegación principal">
          <Link href="/">Dashboard</Link>
          <Link href="/owners">Propietarios</Link>
          <Link href="/patients">Pacientes</Link>
          <Link href="/agenda">Agenda</Link>
          <Link href="/inventario">Inventario</Link>
          <Link href="/ajustes">Ajustes</Link>
        </nav>

        <div className="session-actions">
          <span className="session-actions__email">{user?.email}</span>
          <button className="logout-button" onClick={logout} type="button">
            <LogOut aria-hidden="true" size={16} />
            <span>Cerrar sesión</span>
          </button>
        </div>
      </div>

      <div className={`site-search${isSearchOpen ? " site-search--open" : ""}`}>
        <GlobalSearch onResultSelected={() => setIsSearchOpen(false)} />
      </div>
    </header>
  );
}

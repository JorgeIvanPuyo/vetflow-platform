"use client";

import {
  Calendar,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  PawPrint,
  Search,
  Settings,
  Stethoscope,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/features/auth/auth-context";
import { useClinic } from "@/features/clinic/clinic-context";
import { GlobalSearch } from "@/features/search/components/global-search";

const menuItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/owners", label: "Propietarios", icon: Users },
  { href: "/patients", label: "Pacientes", icon: PawPrint },
  { href: "/agenda", label: "Agenda", icon: Calendar },
  { href: "/inventario", label: "Inventario", icon: Package },
  { href: "/settings", label: "Ajustes", icon: Settings },
];

export function AppHeader() {
  const { logout, user } = useAuth();
  const { displayName, profile, refreshProfile } = useClinic();
  const pathname = usePathname();
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  useEffect(() => {
    if (!isMenuOpen) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsMenuOpen(false);
      }
    }

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isMenuOpen]);

  useEffect(() => {
    setIsMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    function handleCloseMobileMenu() {
      setIsMenuOpen(false);
    }

    window.addEventListener("vetclinic:close-mobile-menu", handleCloseMobileMenu);

    return () => {
      window.removeEventListener(
        "vetclinic:close-mobile-menu",
        handleCloseMobileMenu,
      );
    };
  }, []);

  function isActive(href: string) {
    return href === "/" ? pathname === "/" : pathname.startsWith(href);
  }

  const mobileMenu = isMenuOpen ? (
    <div
      className="mobile-menu-overlay"
      role="presentation"
      onClick={() => setIsMenuOpen(false)}
    >
      <nav
        className="mobile-menu"
        aria-label="Menú principal"
        role="dialog"
        aria-modal="true"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mobile-menu__header">
          <Link
            className="brand"
            href="/"
            onClick={() => setIsMenuOpen(false)}
            aria-label={`Ir al dashboard de ${displayName}`}
          >
            <ClinicBrandMark logoUrl={profile?.logo_url} onLogoError={refreshProfile} />
            <span>{displayName}</span>
          </Link>
          <button
            className="icon-button"
            type="button"
            aria-label="Cerrar menú"
            onClick={() => setIsMenuOpen(false)}
          >
            <X aria-hidden="true" size={22} />
          </button>
        </div>

        <div className="mobile-menu__links">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);

            return (
              <Link
                aria-current={active ? "page" : undefined}
                className={`mobile-menu__link${active ? " mobile-menu__link--active" : ""}`}
                href={item.href}
                key={item.href}
                onClick={() => setIsMenuOpen(false)}
              >
                <Icon aria-hidden="true" size={22} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </div>

        <button
          aria-label="Cerrar sesión"
          className="mobile-menu__logout"
          onClick={logout}
          type="button"
        >
          <LogOut aria-hidden="true" size={20} />
          <span>Cerrar sesión</span>
        </button>
      </nav>
    </div>
  ) : null;

  return (
    <>
      <header className="site-header">
      <div className="site-header__bar">
        <button
          className="icon-button menu-trigger"
          type="button"
          aria-expanded={isMenuOpen}
          aria-label="Abrir menú"
          onClick={() => setIsMenuOpen(true)}
        >
          <Menu aria-hidden="true" size={22} />
        </button>

        <Link className="brand" href="/" aria-label={`Ir al dashboard de ${displayName}`}>
          <ClinicBrandMark logoUrl={profile?.logo_url} onLogoError={refreshProfile} />
          <span>{displayName}</span>
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

      <div className="site-header__desktop-row">
        <nav className="desktop-nav" aria-label="Navegación principal">
          {menuItems.map((item) => (
            <Link
              aria-current={isActive(item.href) ? "page" : undefined}
              className={isActive(item.href) ? "desktop-nav__link--active" : undefined}
              href={item.href}
              key={item.href}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="session-actions">
          <span className="session-actions__email">{user?.email}</span>
          <button
            aria-label="Cerrar sesión"
            className="logout-button"
            onClick={logout}
            type="button"
          >
            <LogOut aria-hidden="true" size={16} />
            <span>Cerrar sesión</span>
          </button>
        </div>
      </div>

      <div className={`site-search${isSearchOpen ? " site-search--open" : ""}`}>
        <GlobalSearch onResultSelected={() => setIsSearchOpen(false)} />
      </div>
      </header>
      {mobileMenu}
    </>
  );
}

function ClinicBrandMark({
  logoUrl,
  onLogoError,
}: {
  logoUrl?: string | null;
  onLogoError: () => Promise<void>;
}) {
  const [hasLogoError, setHasLogoError] = useState(false);

  useEffect(() => {
    setHasLogoError(false);
  }, [logoUrl]);

  if (logoUrl && !hasLogoError) {
    return (
      <span className="brand__mark brand__mark--image" aria-hidden="true">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          alt=""
          src={logoUrl}
          onError={() => {
            setHasLogoError(true);
            void onLogoError();
          }}
        />
      </span>
    );
  }

  return (
    <span className="brand__mark" aria-hidden="true">
      <Stethoscope size={20} />
    </span>
  );
}

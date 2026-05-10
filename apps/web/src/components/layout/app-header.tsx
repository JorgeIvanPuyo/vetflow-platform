"use client";

import { LogOut, Menu, Search, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ClinicBrandMark } from "@/components/layout/clinic-brand-mark";
import { navigationItems } from "@/components/layout/navigation-items";
import { useClinic } from "@/features/clinic/clinic-context";
import { GlobalSearch } from "@/features/search/components/global-search";
import { useAuth } from "@/features/auth/auth-context";

export function AppHeader() {
  const { displayName, profile, refreshProfile } = useClinic();

  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const { logout } = useAuth();

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

  const mobileMenu = isMenuOpen ? (
    <div
      className="mobile-menu-overlay"
      onClick={() => setIsMenuOpen(false)}
    >
      <nav
        className="mobile-menu"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mobile-menu__header">
          <span className="mobile-menu__title">Menú</span>
          
          <button
            className="icon-button"
            type="button"
            onClick={() => setIsMenuOpen(false)}
          >
            <X size={22} />
          </button>
        </div>

        <div className="mobile-menu__links">
          {navigationItems.map((item) => {
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                className="mobile-menu__link"
                onClick={() => setIsMenuOpen(false)}
              >
                <Icon size={20} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </div>
        <button
          className="mobile-menu__logout"
          type="button"
          onClick={() => {
            setIsMenuOpen(false);
            logout();
          }}
        >
          <LogOut size={20} />
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
            onClick={() => setIsMenuOpen(true)}
          >
            <Menu size={22} />
          </button>

          <Link className="brand mobile-brand" href="/">
            <ClinicBrandMark
              logoUrl={profile?.logo_url}
              onLogoError={refreshProfile}
            />
            <span>{displayName}</span>
          </Link>

          <button
            className="icon-button"
            type="button"
            onClick={() => setIsSearchOpen((current) => !current)}
          >
            <Search size={22} />
          </button>
        </div>

        <div className={`site-search${isSearchOpen ? " site-search--open" : ""}`}>
          <GlobalSearch onResultSelected={() => setIsSearchOpen(false)} />
        </div>
      </header>

      {mobileMenu}
    </>
  );
}
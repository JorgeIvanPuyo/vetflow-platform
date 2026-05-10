"use client";

import { Menu, Search, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ClinicBrandMark } from "@/components/layout/clinic-brand-mark";
import { navigationItems } from "@/components/layout/navigation-items";
import { UserSessionFooter } from "@/components/layout/user-session-footer";
import { useAuth } from "@/features/auth/auth-context";
import { useClinic } from "@/features/clinic/clinic-context";
import { GlobalSearch } from "@/features/search/components/global-search";

export function AppHeader() {
  const { displayName, profile, refreshProfile } = useClinic();
  const { logout, user } = useAuth();

  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

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
    <div className="mobile-menu-overlay" onClick={() => setIsMenuOpen(false)}>
      <nav className="mobile-menu" onClick={(event) => event.stopPropagation()}>
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

        <UserSessionFooter
          className="mobile-menu__user-footer"
          onLogout={() => {
            setIsMenuOpen(false);
            void logout();
          }}
          user={user}
        />
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
            <Menu size={16} />
          </button>

          <Link className="brand mobile-brand" href="/">
            <ClinicBrandMark
              logoUrl={profile?.logo_url}
              onLogoError={refreshProfile}
            />
            <span>{displayName}</span>
          </Link>

          <div className="desktop-header-search">
            <GlobalSearch />
          </div>

          <button
            className="icon-button mobile-search-trigger"
            type="button"
            onClick={() => setIsSearchOpen((current) => !current)}
          >
            <Search size={16} />
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

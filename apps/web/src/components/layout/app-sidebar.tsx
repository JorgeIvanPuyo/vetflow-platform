"use client";

import { Building2, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { ClinicBrandMark } from "@/components/layout/clinic-brand-mark";
import {
  filterNavigationByRole,
  navigationItems,
} from "@/components/layout/navigation-items";
import { UserSessionFooter } from "@/components/layout/user-session-footer";
import { useAuth } from "@/features/auth/auth-context";
import { useCurrentUser } from "@/features/auth/current-user-context";
import { useClinic } from "@/features/clinic/clinic-context";
import { getStoredActingTenantId, setStoredActingTenantId } from "@/lib/acting-tenant";
import { listTenants } from "@/features/users/services/users";
import type { TenantOption } from "@/types/api";
import styles from "./app-sidebar.module.css";

function SuperadminTenantSwitcher() {
  const [tenants, setTenants] = useState<TenantOption[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState("");

  useEffect(() => {
    setSelectedTenantId(getStoredActingTenantId() ?? "");
    listTenants()
      .then((response) => setTenants(response.data))
      .catch(() => setTenants([]));
  }, []);

  function handleChange(nextTenantId: string) {
    setStoredActingTenantId(nextTenantId || null);
    window.location.reload();
  }

  return (
    <label className="field app-sidebar__tenant-switcher">
      <span>Viendo clínica</span>
      <select
        value={selectedTenantId}
        onChange={(event) => handleChange(event.target.value)}
      >
        <option value="">Mi clínica</option>
        {tenants.map((tenant) => (
          <option key={tenant.id} value={tenant.id}>
            {tenant.name}
          </option>
        ))}
      </select>
    </label>
  );
}

export function AppSidebar() {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(false);
  useEffect(() => {
    try {
      setIsCollapsed(window.localStorage.getItem("vetflow:sidebar-collapsed") === "true");
    } catch {
      // Storage may be unavailable; the sidebar remains usable for this session.
    }
  }, []);

  function setCollapsed(value: boolean) {
    setIsCollapsed(value);
    try {
      window.localStorage.setItem("vetflow:sidebar-collapsed", String(value));
    } catch {
      // A visual preference must not prevent navigation when storage is blocked.
    }
  }
  const { logout, user } = useAuth();
  const { role } = useCurrentUser();
  const { displayName, profile, refreshProfile } = useClinic();
  const visibleItems = filterNavigationByRole(navigationItems, role);

  function isActive(href: string) {
    if (href === "/inventory/dashboard") {
      return pathname.startsWith("/inventory") || pathname.startsWith("/inventario");
    }
    if (href === "/purchases/dashboard") {
      return pathname.startsWith("/purchases") || pathname.startsWith("/suppliers");
    }

    return href === "/" ? pathname === "/" : pathname.startsWith(href);
  }

  return (
    <aside className={`app-sidebar ${styles.sidebar}${isCollapsed ? ` ${styles.collapsed}` : ""}`} aria-label="Navegación principal">
      <div className="app-sidebar__inner">
        <div className={styles.heading}>
          <Link className="brand app-sidebar__brand" href="/" aria-label={displayName}
            data-sidebar-tooltip={isCollapsed ? displayName : undefined}>
            <ClinicBrandMark logoUrl={profile?.logo_url} onLogoError={refreshProfile} />
            <span className={styles.brandName}>{displayName}</span>
          </Link>

          <button type="button" className={`icon-button ${styles.toggle}`}
            aria-label={isCollapsed ? "Expandir navegación" : "Colapsar navegación"}
            aria-expanded={!isCollapsed} aria-controls="desktop-navigation"
            data-sidebar-tooltip={isCollapsed ? "Expandir navegación" : undefined}
            onClick={() => setCollapsed(!isCollapsed)}>
            {isCollapsed ? <PanelLeftOpen size={19} aria-hidden="true" /> : <PanelLeftClose size={19} aria-hidden="true" />}
          </button>
        </div>

        {role === "superadmin" ? <>
          <div className={styles.tenantSwitcher}><SuperadminTenantSwitcher /></div>
          {isCollapsed ? <button type="button" className={`icon-button ${styles.tenantToggle}`}
            aria-label="Expandir para cambiar clínica" data-sidebar-tooltip="Cambiar clínica"
            onClick={() => setCollapsed(false)}><Building2 size={18} aria-hidden="true" /></button> : null}
        </> : null}

        <nav id="desktop-navigation" className="app-sidebar__nav">
          {visibleItems.map((item) => {
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                aria-label={item.label}
                aria-current={isActive(item.href) ? "page" : undefined}
                data-sidebar-tooltip={isCollapsed ? item.label : undefined}
                className={`app-sidebar__link${
                  isActive(item.href) ? " app-sidebar__link--active" : ""
                }`}
              >
                <Icon size={18} aria-hidden="true" />
                <span className={styles.linkLabel}>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <UserSessionFooter className="app-sidebar__user-footer" onLogout={logout} user={user} compact={isCollapsed} />
      </div>
    </aside>
  );
}

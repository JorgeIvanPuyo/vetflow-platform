"use client";

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
  const { logout, user } = useAuth();
  const { role } = useCurrentUser();
  const { displayName, profile, refreshProfile } = useClinic();
  const visibleItems = filterNavigationByRole(navigationItems, role);

  function isActive(href: string) {
    if (href === "/inventory") {
      return pathname.startsWith("/inventory") || pathname.startsWith("/inventario");
    }

    return href === "/" ? pathname === "/" : pathname.startsWith(href);
  }

  return (
    <aside className="app-sidebar">
      <div className="app-sidebar__inner">
        <Link className="brand app-sidebar__brand" href="/">
          <ClinicBrandMark logoUrl={profile?.logo_url} onLogoError={refreshProfile} />
          <span>{displayName}</span>
        </Link>

        {role === "superadmin" ? <SuperadminTenantSwitcher /> : null}

        <nav className="app-sidebar__nav">
          {visibleItems.map((item) => {
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`app-sidebar__link${
                  isActive(item.href) ? " app-sidebar__link--active" : ""
                }`}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <UserSessionFooter className="app-sidebar__user-footer" onLogout={logout} user={user} />
      </div>
    </aside>
  );
}

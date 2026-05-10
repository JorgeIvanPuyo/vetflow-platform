"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { ClinicBrandMark } from "@/components/layout/clinic-brand-mark";
import { navigationItems } from "@/components/layout/navigation-items";
import { UserSessionFooter } from "@/components/layout/user-session-footer";
import { useAuth } from "@/features/auth/auth-context";
import { useClinic } from "@/features/clinic/clinic-context";

export function AppSidebar() {
  const pathname = usePathname();
  const { logout, user } = useAuth();
  const { displayName, profile, refreshProfile } = useClinic();

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

        <nav className="app-sidebar__nav">
          {navigationItems.map((item) => {
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

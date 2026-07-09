"use client";

import {
  Calculator,
  Calendar,
  LayoutDashboard,
  Package,
  PawPrint,
  Settings,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { SCOPED_ROLES } from "@/components/layout/navigation-items";
import { useCurrentUser } from "@/features/auth/current-user-context";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/patients", label: "Pacientes", icon: PawPrint },
  { href: "/agenda", label: "Agenda", icon: Calendar },
  { href: "/inventory", label: "Inventario", icon: Package },
  {
    href: "/accounting",
    label: "Contabilidad",
    icon: Calculator,
    roles: ["contador", "superadmin"] as const,
  },
  {
    href: "/users",
    label: "Usuarios",
    icon: ShieldCheck,
    roles: ["superadmin"] as const,
  },
  { href: "/settings", label: "Ajustes", icon: Settings },
];

function closeMobileMenu() {
  window.dispatchEvent(new Event("vetclinic:close-mobile-menu"));
}

export function BottomNav() {
  const pathname = usePathname();
  const { role } = useCurrentUser();
  const isConsultationWorkflow =
    pathname.startsWith("/consultations/") ||
    /^\/patients\/[^/]+\/consultations\/new$/.test(pathname);

  if (isConsultationWorkflow) {
    return null;
  }

  const visibleItems = navItems.filter((item) => {
    if ("roles" in item) {
      return role ? (item.roles as readonly string[]).includes(role) : false;
    }
    return role ? !SCOPED_ROLES.includes(role) : true;
  });

  return (
    <nav className="bottom-nav" aria-label="Navegación principal móvil">
      {visibleItems.map((item) => {
        const Icon = item.icon;
        const isActive =
          item.href === "/agenda"
            ? pathname.startsWith("/agenda") || pathname.startsWith("/follow-ups")
            : item.href === "/inventory"
              ? pathname.startsWith("/inventory") || pathname.startsWith("/inventario")
            : item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);

        return (
          <Link
            aria-current={isActive ? "page" : undefined}
            className={`bottom-nav__item${isActive ? " bottom-nav__item--active" : ""}`}
            href={item.href}
            key={item.href}
            onClick={closeMobileMenu}
          >
            <Icon aria-hidden="true" size={21} strokeWidth={2.2} />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

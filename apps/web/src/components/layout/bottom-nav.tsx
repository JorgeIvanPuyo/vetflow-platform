"use client";

import { Calendar, LayoutDashboard, Package, PawPrint, Settings } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/patients", label: "Pacientes", icon: PawPrint },
  { href: "/agenda", label: "Agenda", icon: Calendar },
  { href: "/inventario", label: "Inventario", icon: Package },
  { href: "/settings", label: "Ajustes", icon: Settings },
];

function closeMobileMenu() {
  window.dispatchEvent(new Event("vetclinic:close-mobile-menu"));
}

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="bottom-nav" aria-label="Navegación principal móvil">
      {navItems.map((item) => {
        const Icon = item.icon;
        const isActive =
          item.href === "/agenda"
            ? pathname.startsWith("/agenda") || pathname.startsWith("/follow-ups")
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

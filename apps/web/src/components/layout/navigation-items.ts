import {
  Calculator,
  Calendar,
  LayoutDashboard,
  LucideIcon,
  Package,
  PawPrint,
  Settings,
  ShieldCheck,
  Users,
} from "lucide-react";

import type { AppRole } from "@/types/api";

export type NavigationItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  roles?: AppRole[];
};

export const navigationItems: NavigationItem[] = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/owners", label: "Propietarios", icon: Users },
  { href: "/patients", label: "Pacientes", icon: PawPrint },
  { href: "/agenda", label: "Agenda", icon: Calendar },
  { href: "/inventory", label: "Inventario", icon: Package },
  {
    href: "/accounting",
    label: "Contabilidad",
    icon: Calculator,
    roles: ["contador", "superadmin"],
  },
  {
    href: "/users",
    label: "Usuarios",
    icon: ShieldCheck,
    roles: ["superadmin"],
  },
  { href: "/settings", label: "Ajustes", icon: Settings },
];

// Roles that must ONLY see modules explicitly granted to them (via `roles`),
// never the unrestricted base modules.
export const SCOPED_ROLES: AppRole[] = ["contador"];

export function filterNavigationByRole(
  items: NavigationItem[],
  role: AppRole | null,
): NavigationItem[] {
  return items.filter((item) => {
    if (item.roles) {
      return role ? item.roles.includes(role) : false;
    }
    // Unrestricted items: visible to everyone except scoped roles.
    return role ? !SCOPED_ROLES.includes(role) : true;
  });
}

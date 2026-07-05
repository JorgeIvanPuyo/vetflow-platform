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

export function filterNavigationByRole(
  items: NavigationItem[],
  role: AppRole | null,
): NavigationItem[] {
  return items.filter((item) => !item.roles || (role ? item.roles.includes(role) : false));
}

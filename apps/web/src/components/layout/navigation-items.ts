import {
  Calendar,
  LayoutDashboard,
  Package,
  PawPrint,
  Settings,
  Users,
} from "lucide-react";

export const navigationItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/owners", label: "Propietarios", icon: Users },
  { href: "/patients", label: "Pacientes", icon: PawPrint },
  { href: "/agenda", label: "Agenda", icon: Calendar },
  { href: "/inventory", label: "Inventario", icon: Package },
  { href: "/settings", label: "Ajustes", icon: Settings },
];
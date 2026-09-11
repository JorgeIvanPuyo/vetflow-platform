import type { AppRole } from "@/types/api";

export const helpCategories = {
  "primeros-pasos": { label: "Primeros pasos", description: "Conoce Vetflow y encuentra cada tarea." },
  agenda: { label: "Agenda", description: "Organiza turnos y revisa la atención del día." },
  pacientes: { label: "Propietarios y pacientes", description: "Registra contactos y consulta la historia clínica." },
  consultas: { label: "Consultas", description: "Documenta la atención y programa seguimientos." },
  inventario: { label: "Inventario", description: "Controla productos, existencias y precios." },
  proveedores: { label: "Proveedores", description: "Mantén el directorio para tus compras." },
  compras: { label: "Compras", description: "Registra compras, recepciones y devoluciones." },
  ventas: { label: "Ventas", description: "Registra ventas, cobros y comprobantes." },
  configuracion: { label: "Configuración", description: "Personaliza las preferencias y catálogos en Ajustes." },
  usuarios: { label: "Usuarios y permisos", description: "Conoce los roles y la gestión de accesos." },
  clinicas: { label: "Administración de clínicas", description: "Herramientas exclusivas de Superadmin." },
} as const;

export type HelpCategory = keyof typeof helpCategories;

type HelpRoute = { appRoute?: string; appRouteLabel?: string };

export type HelpStep = HelpRoute & {
  title: string;
  description: string;
} & ({ imageSrc: string; imageAlt: string } | { imageSrc?: never; imageAlt?: never });

export type HelpGuide = HelpRoute & {
  slug: string;
  title: string;
  description: string;
  category: HelpCategory;
  keywords: string[];
  estimatedMinutes?: number;
  requiredRoles?: AppRole[];
  prerequisites?: string[];
  steps: HelpStep[];
  tips?: string[];
  youtubeUrl?: string;
  youtubeLabel?: string;
  relatedGuides?: string[];
  updatedAt: string;
};

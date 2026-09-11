import type { HelpGuide } from "../types";

export const guides: HelpGuide[] = [
  {
    "slug": "conocer-vetflow",
    "title": "Conocer Vetflow y navegar por la aplicación",
    "description": "Encuentra las tareas de tu clínica desde el menú principal.",
    "category": "primeros-pasos",
    "keywords": [
      "inicio",
      "menu",
      "navegar",
      "modulos",
      "clinica"
    ],
    "appRoute": "/",
    "appRouteLabel": "Ir al inicio",
    "estimatedMinutes": 4,
    "steps": [
      {
        "title": "Revisa el menú",
        "description": "En computadora, usa el menú lateral. En móvil, abre el menú de navegación para acceder a los módulos disponibles para tu rol."
      },
      {
        "title": "Elige una tarea",
        "description": "Propietarios y Pacientes reúnen contactos e historias clínicas. Agenda organiza turnos y seguimientos; Inventario, Compras y Ventas cubren la operación comercial."
      },
      {
        "title": "Abre el detalle",
        "description": "Selecciona un registro en un listado para ver su información y las acciones disponibles. Usa el enlace Volver de cada pantalla para regresar."
      },
      {
        "title": "Encuentra las opciones de tu clínica",
        "description": "En Ajustes puedes consultar la configuración y los catálogos. Si eres Superadmin, el selector Viendo clínica permite elegir la clínica activa."
      },
      {
        "title": "Vuelve cuando necesites ayuda",
        "description": "Abre Centro de ayuda desde la navegación y busca la tarea que quieres realizar."
      }
    ],
    "relatedGuides": [
      "registrar-paciente",
      "agendar-cita",
      "entender-roles"
    ],
    "updatedAt": "2026-09-10",
    "tips": [
      "Las opciones del menú dependen del rol. El Contador dispone de Contabilidad, que actualmente muestra En construcción, y del Centro de ayuda."
    ]
  }
];

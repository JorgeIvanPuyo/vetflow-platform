import type { HelpGuide } from "../types";

export const guides: HelpGuide[] = [
  {
    "slug": "consultar-usuarios",
    "title": "Consultar usuarios",
    "description": "Busca usuarios y revisa la clínica y el rol asignados.",
    "category": "usuarios",
    "keywords": [
      "usuario",
      "acceso",
      "rol",
      "compania",
      "buscar"
    ],
    "appRoute": "/users",
    "appRouteLabel": "Ir a Usuarios",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre Usuarios",
        "description": "Accede desde el menú con tu cuenta de Superadmin."
      },
      {
        "title": "Filtra el listado",
        "description": "Usa Buscar, Compañía y Estado para localizar a la persona."
      },
      {
        "title": "Revisa sus datos",
        "description": "Consulta nombre, correo, rol, clínica, actividad y fechas de creación y actualización."
      }
    ],
    "relatedGuides": [
      "invitar-usuario",
      "entender-roles"
    ],
    "updatedAt": "2026-09-10",
    "requiredRoles": [
      "superadmin"
    ]
  },
  {
    "slug": "invitar-usuario",
    "title": "Invitar un usuario",
    "description": "Crea el acceso de una persona y asígnale su clínica y rol.",
    "category": "usuarios",
    "keywords": [
      "invitar",
      "usuario",
      "acceso",
      "correo",
      "contrasena"
    ],
    "appRoute": "/users",
    "appRouteLabel": "Ir a Usuarios",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Inicia la invitación",
        "description": "En Usuarios, pulsa Invitar usuario."
      },
      {
        "title": "Completa los datos",
        "description": "Ingresa correo y nombre de la persona. Selecciona su clínica y el rol que corresponde a sus tareas."
      },
      {
        "title": "Confirma el registro",
        "description": "Envía el formulario y revisa el mensaje de creación."
      },
      {
        "title": "Comparte el acceso",
        "description": "Si aparece Enlace para establecer contraseña, pulsa Copiar y compártelo con la persona invitada."
      }
    ],
    "relatedGuides": [
      "consultar-usuarios",
      "entender-roles",
      "crear-clinica"
    ],
    "updatedAt": "2026-09-10",
    "requiredRoles": [
      "superadmin"
    ]
  },
  {
    "slug": "entender-roles",
    "title": "Entender los roles y permisos",
    "description": "Identifica a quién acudir para cada tarea y por qué cambia la navegación.",
    "category": "usuarios",
    "keywords": [
      "roles",
      "permisos",
      "administrador",
      "medico",
      "veterinario",
      "contador",
      "secretaria",
      "superadmin"
    ],
    "appRoute": "/help",
    "appRouteLabel": "Ir al Centro de ayuda",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Administrador de clínica",
        "description": "Trabaja con los módulos de la clínica y puede administrar sus catálogos, servicios y preferencias en Ajustes."
      },
      {
        "title": "Médico veterinario",
        "description": "Gestiona la operación de la clínica y es el único rol que puede asumir responsabilidad clínica. Puede ser emisor fiscal si tiene una configuración fiscal válida."
      },
      {
        "title": "Secretaria",
        "description": "Gestiona agenda, propietarios, pacientes administrativos, inventario, proveedores, compras, ventas, cobros, catálogos y configuración operativa. Puede configurar emisores veterinarios y métodos de pago. Consulta la historia clínica sin asumir responsabilidad clínica ni fiscal. No administra usuarios o tenants ni elimina historia clínica."
      },
      {
        "title": "Contador",
        "description": "Gestiona los mismos módulos operativos que los demás roles de clínica, además de acceder a Contabilidad, actualmente En construcción. No asume responsabilidad clínica ni fiscal."
      },
      {
        "title": "Superadmin",
        "description": "Puede abrir Usuarios, invitar personas, crear clínicas y cambiar la clínica activa. La interfaz de edición de catálogos y preferencias sigue reservada al Administrador de clínica."
      }
    ],
    "relatedGuides": [
      "consultar-usuarios",
      "invitar-usuario",
      "preferencias-clinica"
    ],
    "updatedAt": "2026-09-10",
    "tips": [
      "Leer una guía no cambia tus permisos. Si necesitas una acción que no está disponible para tu rol, solicita ayuda al responsable correspondiente."
    ]
  }
];

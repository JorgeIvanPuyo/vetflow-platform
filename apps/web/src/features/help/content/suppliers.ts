import type { HelpGuide } from "../types";

export const guides: HelpGuide[] = [
  {
    "slug": "registrar-proveedor",
    "title": "Registrar un proveedor",
    "description": "Añade al directorio la empresa o persona a la que compras productos.",
    "category": "proveedores",
    "keywords": [
      "proveedor",
      "directorio",
      "identificacion fiscal",
      "compras",
      "contacto"
    ],
    "appRoute": "/suppliers/new",
    "appRouteLabel": "Ir a Nuevo proveedor",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre Nuevo proveedor",
        "description": "Desde Compras, entra a Proveedores y pulsa Nuevo proveedor."
      },
      {
        "title": "Completa sus datos",
        "description": "Ingresa Nombre e Identificación fiscal cuando corresponda, junto con teléfono, email, dirección y notas."
      },
      {
        "title": "Guarda el registro",
        "description": "Revisa que Estado sea Activo si lo utilizarás en nuevas compras y guarda."
      }
    ],
    "relatedGuides": [
      "editar-proveedor",
      "registrar-compra"
    ],
    "updatedAt": "2026-09-10",
    "tips": [
      "El nombre y la identificación fiscal deben ser únicos dentro de la clínica."
    ]
  },
  {
    "slug": "editar-proveedor",
    "title": "Buscar, editar o desactivar un proveedor",
    "description": "Mantén actualizado el directorio de proveedores.",
    "category": "proveedores",
    "keywords": [
      "proveedor",
      "buscar",
      "editar",
      "desactivar",
      "inactivo",
      "identificacion fiscal"
    ],
    "appRoute": "/suppliers",
    "appRouteLabel": "Ir a Proveedores",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Busca el proveedor",
        "description": "En Proveedores, usa Buscar y el filtro Estado para encontrar registros activos o inactivos."
      },
      {
        "title": "Actualiza la información",
        "description": "Abre el detalle y pulsa Editar. Corrige los datos de contacto o la Identificación fiscal."
      },
      {
        "title": "Cambia su disponibilidad",
        "description": "Si ya no debe usarse en nuevas compras, selecciona Estado Inactivo y guarda. Puedes volver a activarlo desde la edición."
      }
    ],
    "relatedGuides": [
      "registrar-proveedor",
      "registrar-compra"
    ],
    "updatedAt": "2026-09-10"
  }
];

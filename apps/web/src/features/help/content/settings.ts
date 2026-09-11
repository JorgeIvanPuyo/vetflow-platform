import type { HelpGuide } from "../types";

export const guides: HelpGuide[] = [
  {
    "slug": "formas-pago",
    "title": "Configurar métodos de pago (formas de pago)",
    "description": "Define las opciones que aparecen al registrar un cobro.",
    "category": "configuracion",
    "keywords": [
      "pago",
      "pagos",
      "metodo",
      "forma",
      "efectivo",
      "tarjeta",
      "transferencia"
    ],
    "appRoute": "/settings/sales/payment-methods",
    "appRouteLabel": "Ir a Formas de pago",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre Formas de pago",
        "description": "En Ajustes, entra a Ventas y facturación y selecciona Formas de pago."
      },
      {
        "title": "Crea una opción",
        "description": "Pulsa Nueva forma de pago. Completa Nombre y Tipo; por ejemplo, efectivo, tarjeta o transferencia."
      },
      {
        "title": "Define su disponibilidad",
        "description": "Indica Orden y activa Disponible para nuevos cobros si deseas ofrecerla."
      },
      {
        "title": "Guarda y mantén el catálogo",
        "description": "Pulsa Guardar. Usa Editar, Inactivar o Activar para mantener las opciones."
      }
    ],
    "relatedGuides": [
      "registrar-pagos",
      "saldo-pendiente"
    ],
    "updatedAt": "2026-09-10",
    "tips": [
      "Si una forma ya tiene cobros históricos, su tipo no puede cambiarse."
    ]
  },
  {
    "slug": "emisores-fiscales",
    "title": "Configurar emisores fiscales",
    "description": "Configura las personas que pueden figurar como emisoras de comprobantes.",
    "category": "configuracion",
    "keywords": [
      "fiscal",
      "emisor",
      "factura",
      "recibo",
      "comprobante"
    ],
    "appRoute": "/settings/sales/fiscal-issuers",
    "appRouteLabel": "Ir a Emisores fiscales",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre Emisores fiscales",
        "description": "En Ajustes, selecciona Ventas y facturación y después Emisores fiscales."
      },
      {
        "title": "Crea el emisor",
        "description": "Pulsa Nuevo emisor. Selecciona Usuario y completa Nombre fiscal e Identificación tributaria."
      },
      {
        "title": "Configura los comprobantes",
        "description": "Indica si Puede emitir por servicios o por productos. Completa los tipos y códigos permitidos para cada caso."
      },
      {
        "title": "Guarda su disponibilidad",
        "description": "Revisa Emisor activo y guarda. Usa Editar para actualizar la configuración."
      }
    ],
    "relatedGuides": [
      "documentos-fiscales",
      "registrar-venta"
    ],
    "updatedAt": "2026-09-10",
    "tips": [
      "El emisor fiscal y la persona que carga el comprobante se registran por separado."
    ]
  },
  {
    "slug": "administrar-servicios",
    "title": "Crear y administrar servicios",
    "description": "Configura las prestaciones disponibles al agendar un turno.",
    "category": "configuracion",
    "keywords": [
      "servicio",
      "agenda",
      "duracion",
      "turno",
      "prestacion"
    ],
    "appRoute": "/settings",
    "appRouteLabel": "Ir a Ajustes",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre Servicios",
        "description": "En Ajustes, despliega Servicios y pulsa Nuevo servicio."
      },
      {
        "title": "Define la prestación",
        "description": "Completa Código, Nombre, Tipo y Duración. Ajusta Color, Orden y Descripción cuando corresponda."
      },
      {
        "title": "Habilita la agenda",
        "description": "Marca Disponible para agenda para permitir seleccionar el servicio al crear turnos y guarda."
      },
      {
        "title": "Mantén el catálogo",
        "description": "Usa Editar o las acciones de actividad y orden de los servicios para mantener las opciones."
      }
    ],
    "relatedGuides": [
      "agendar-cita",
      "preferencias-clinica",
      "catalogos-clinica"
    ],
    "updatedAt": "2026-09-10",
    "requiredRoles": [
      "clinic_admin"
    ]
  },
  {
    "slug": "catalogos-clinica",
    "title": "Administrar los catálogos de la clínica",
    "description": "Organiza las opciones reutilizables que usa el equipo al registrar datos.",
    "category": "configuracion",
    "keywords": [
      "catalogo",
      "configuracion",
      "especies",
      "razas",
      "categorias",
      "examenes"
    ],
    "appRoute": "/settings",
    "appRouteLabel": "Ir a Ajustes",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Elige el catálogo",
        "description": "En Ajustes, abre Especies y razas, Categorías de inventario o Catálogos clínicos."
      },
      {
        "title": "Crea una opción",
        "description": "Selecciona el grupo adecuado y pulsa Nueva opción. Completa nombre, descripción y la categoría o especie superior cuando corresponda."
      },
      {
        "title": "Guarda y revisa",
        "description": "Guarda la opción y verifica que aparezca en su grupo."
      },
      {
        "title": "Mantén la lista",
        "description": "Usa Editar, las acciones de activar o desactivar y los controles de orden disponibles."
      }
    ],
    "relatedGuides": [
      "especies-razas",
      "categorias-inventario",
      "catalogos-clinicos"
    ],
    "updatedAt": "2026-09-10",
    "requiredRoles": [
      "clinic_admin"
    ]
  },
  {
    "slug": "especies-razas",
    "title": "Configurar especies y razas",
    "description": "Mantén las opciones disponibles para identificar pacientes.",
    "category": "configuracion",
    "keywords": [
      "especie",
      "raza",
      "canino",
      "felino",
      "catalogo"
    ],
    "appRoute": "/settings",
    "appRouteLabel": "Ir a Ajustes",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre Especies y razas",
        "description": "En Ajustes, despliega esta sección y selecciona el grupo de especies."
      },
      {
        "title": "Añade una especie",
        "description": "Pulsa Nueva opción, completa el nombre y la descripción opcional y guarda."
      },
      {
        "title": "Añade una raza",
        "description": "Selecciona el grupo de razas, pulsa Nueva opción y elige su Especie antes de guardar."
      },
      {
        "title": "Actualiza las opciones",
        "description": "Usa Editar o los controles de actividad para mantener la lista."
      }
    ],
    "relatedGuides": [
      "registrar-paciente",
      "catalogos-clinica"
    ],
    "updatedAt": "2026-09-10",
    "requiredRoles": [
      "clinic_admin"
    ]
  },
  {
    "slug": "categorias-inventario",
    "title": "Configurar categorías de inventario",
    "description": "Organiza artículos con categorías y subcategorías propias de la clínica.",
    "category": "configuracion",
    "keywords": [
      "categoria",
      "subcategoria",
      "inventario",
      "producto",
      "catalogo"
    ],
    "appRoute": "/settings",
    "appRouteLabel": "Ir a Ajustes",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre Categorías de inventario",
        "description": "En Ajustes, despliega la sección de categorías."
      },
      {
        "title": "Crea una categoría",
        "description": "En el grupo correspondiente, pulsa Nueva opción y completa Nombre y Descripción opcional."
      },
      {
        "title": "Añade subcategorías",
        "description": "En subcategorías, crea una opción y selecciona la Categoría a la que pertenece."
      },
      {
        "title": "Utiliza la clasificación",
        "description": "Guarda y selecciona estas opciones al crear o editar un producto.",
        "appRoute": "/inventory/new",
        "appRouteLabel": "Ir a Nuevo item"
      }
    ],
    "relatedGuides": [
      "crear-producto",
      "catalogos-clinica"
    ],
    "updatedAt": "2026-09-10",
    "requiredRoles": [
      "clinic_admin"
    ]
  },
  {
    "slug": "catalogos-clinicos",
    "title": "Configurar estudios, cuidados y archivos clínicos",
    "description": "Personaliza las opciones y plantillas que se utilizan durante la atención.",
    "category": "configuracion",
    "keywords": [
      "catalogos",
      "examen",
      "estudios",
      "preventivo",
      "documento",
      "archivo",
      "mucosas",
      "hidratacion",
      "prescripcion"
    ],
    "appRoute": "/settings",
    "appRouteLabel": "Ir a Ajustes",
    "estimatedMinutes": 4,
    "steps": [
      {
        "title": "Abre Catálogos clínicos",
        "description": "En Ajustes, despliega esta sección."
      },
      {
        "title": "Selecciona el grupo",
        "description": "Para estudios usa Estudios y exámenes; para vacunas y desparasitaciones, Prestaciones preventivas; para documentos, Tipos de archivo clínico."
      },
      {
        "title": "Añade una opción",
        "description": "Pulsa Nueva opción, completa Nombre y Descripción opcional y guarda."
      },
      {
        "title": "Revisa otros catálogos",
        "description": "También puedes mantener Mucosas, Hidratación, Plantillas de seguimiento, Etiquetas diagnósticas y Plantillas de prescripción."
      },
      {
        "title": "Mantén el catálogo",
        "description": "Usa Editar, los controles de actividad y orden. Los grupos que lo ofrecen permiten Restaurar predeterminados."
      }
    ],
    "relatedGuides": [
      "cuidados-preventivos",
      "documentos-paciente",
      "hallazgos-medicamentos-estudios"
    ],
    "updatedAt": "2026-09-10",
    "requiredRoles": [
      "clinic_admin"
    ]
  },
  {
    "slug": "preferencias-clinica",
    "title": "Configurar las preferencias de la clínica",
    "description": "Define región, moneda y valores sugeridos para nuevas operaciones.",
    "category": "configuracion",
    "keywords": [
      "preferencias",
      "moneda",
      "region",
      "impuesto",
      "margen",
      "redondeo",
      "configuracion"
    ],
    "appRoute": "/settings",
    "appRouteLabel": "Ir a Ajustes",
    "estimatedMinutes": 4,
    "steps": [
      {
        "title": "Abre Preferencias",
        "description": "En Ajustes, despliega Preferencias."
      },
      {
        "title": "Selecciona la región",
        "description": "Elige USD · es-PA o ARS · es-AR. Esta selección define la moneda y el formato regional de los importes."
      },
      {
        "title": "Configura la agenda",
        "description": "Revisa Duración predeterminada y Opciones de duración para los turnos."
      },
      {
        "title": "Revisa impuestos y margen",
        "description": "Completa Impuesto de compra predeterminado (%), Impuesto de venta predeterminado (%) y Margen de ganancia predeterminado (%)."
      },
      {
        "title": "Configura el redondeo",
        "description": "Indica Incremento de redondeo y guarda las preferencias."
      }
    ],
    "relatedGuides": [
      "crear-producto",
      "administrar-servicios",
      "catalogos-clinica"
    ],
    "updatedAt": "2026-09-10",
    "requiredRoles": [
      "clinic_admin"
    ],
    "tips": [
      "Estos valores se utilizan como configuración predeterminada en los formularios que los aplican. No recalculan automáticamente los importes históricos.",
      "La sección Ubicación y zona horaria indica Próximamente y todavía no permite modificar esos datos."
    ]
  }
];

import type { HelpGuide } from "../types";

export const guides: HelpGuide[] = [
  {
    "slug": "registrar-propietario",
    "title": "Registrar un propietario",
    "description": "Guarda los datos de contacto de la persona responsable del paciente.",
    "category": "pacientes",
    "keywords": [
      "dueno",
      "tutor",
      "contacto",
      "telefono",
      "propietario"
    ],
    "appRoute": "/owners",
    "appRouteLabel": "Ir a Propietarios",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre el registro",
        "description": "En Propietarios, pulsa el botón de agregar identificado como Crear propietario."
      },
      {
        "title": "Completa el contacto",
        "description": "Ingresa Nombre completo y Teléfono. Agrega Correo opcional y Dirección opcional si están disponibles."
      },
      {
        "title": "Crea el propietario",
        "description": "Pulsa Crear propietario y comprueba que aparezca en el listado."
      }
    ],
    "relatedGuides": [
      "consultar-propietario",
      "registrar-paciente"
    ],
    "updatedAt": "2026-09-10"
  },
  {
    "slug": "consultar-propietario",
    "title": "Consultar un propietario y sus pacientes",
    "description": "Encuentra sus datos de contacto y las mascotas asociadas.",
    "category": "pacientes",
    "keywords": [
      "propietario",
      "mascotas",
      "contacto",
      "buscar"
    ],
    "appRoute": "/owners",
    "appRouteLabel": "Ir a Propietarios",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Encuentra al propietario",
        "description": "Busca en Propietarios y abre el registro correspondiente."
      },
      {
        "title": "Revisa sus datos",
        "description": "Consulta teléfono, correo y dirección. Usa Editar si necesitas corregir la información y guarda."
      },
      {
        "title": "Abre un paciente",
        "description": "En las mascotas asociadas, selecciona el paciente para consultar su ficha."
      }
    ],
    "relatedGuides": [
      "registrar-propietario",
      "actualizar-paciente"
    ],
    "updatedAt": "2026-09-10"
  },
  {
    "slug": "registrar-paciente",
    "title": "Registrar un paciente",
    "description": "Crea la ficha de una mascota y asígnala a su propietario.",
    "category": "pacientes",
    "keywords": [
      "mascota",
      "animal",
      "paciente",
      "registrar",
      "ficha"
    ],
    "appRoute": "/patients",
    "appRouteLabel": "Ir a Pacientes",
    "estimatedMinutes": 4,
    "steps": [
      {
        "title": "Abre Crear paciente",
        "description": "En Pacientes, pulsa el botón de agregar identificado como Crear paciente."
      },
      {
        "title": "Selecciona al propietario",
        "description": "Elige un propietario existente. Si falta, usa + Crear nuevo propietario, completa sus datos y regresa al registro del paciente."
      },
      {
        "title": "Completa la ficha",
        "description": "Ingresa Nombre del paciente, Especie y los datos disponibles de Raza, Sexo, Edad estimada y Peso (kg)."
      },
      {
        "title": "Registra las alertas",
        "description": "Completa alergias y condiciones crónicas cuando existan. Revisa las opciones Sin alergias conocidas y Sin condiciones crónicas conocidas."
      },
      {
        "title": "Guarda el paciente",
        "description": "Puedes añadir una foto si la tienes. Pulsa Crear paciente y revisa la nueva ficha."
      }
    ],
    "relatedGuides": [
      "registrar-propietario",
      "actualizar-paciente",
      "iniciar-consulta"
    ],
    "updatedAt": "2026-09-10"
  },
  {
    "slug": "actualizar-paciente",
    "title": "Consultar y actualizar la ficha de un paciente",
    "description": "Revisa la información general y la historia clínica de una mascota.",
    "category": "pacientes",
    "keywords": [
      "ficha",
      "editar",
      "paciente",
      "mascota",
      "historial",
      "alergias"
    ],
    "appRoute": "/patients",
    "appRouteLabel": "Ir a Pacientes",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Busca al paciente",
        "description": "Abre Pacientes y selecciona la mascota que necesitas consultar."
      },
      {
        "title": "Consulta la historia",
        "description": "En Historial completo, filtra los registros y expande una entrada para ver más información."
      },
      {
        "title": "Actualiza la ficha",
        "description": "En Información, pulsa Editar. Revisa propietario, datos del paciente y alertas clínicas antes de guardar."
      }
    ],
    "relatedGuides": [
      "registrar-paciente",
      "cuidados-preventivos",
      "documentos-paciente"
    ],
    "updatedAt": "2026-09-10"
  },
  {
    "slug": "cuidados-preventivos",
    "title": "Registrar cuidados preventivos",
    "description": "Añade vacunas y desparasitaciones a la historia del paciente.",
    "category": "pacientes",
    "keywords": [
      "vacuna",
      "desparasitacion",
      "dosis",
      "prevencion",
      "lote"
    ],
    "appRoute": "/patients",
    "appRouteLabel": "Ir a Pacientes",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre la sección preventiva",
        "description": "En la ficha del paciente, entra a Vacunas y desparasitación y pulsa Agregar."
      },
      {
        "title": "Identifica la prestación",
        "description": "Selecciona una Prestación del catálogo o Escribir manualmente. Completa Nombre y Tipo."
      },
      {
        "title": "Completa las fechas",
        "description": "Indica Fecha y, cuando corresponda, Próxima dosis, Lote y Notas."
      },
      {
        "title": "Guarda y revisa",
        "description": "Guarda el registro. Después puedes editarlo desde la sección preventiva."
      }
    ],
    "relatedGuides": [
      "actualizar-paciente",
      "catalogos-clinicos",
      "gestionar-seguimiento"
    ],
    "updatedAt": "2026-09-10"
  },
  {
    "slug": "documentos-paciente",
    "title": "Gestionar archivos e historia clínica",
    "description": "Adjunta documentos y prepara la historia clínica en PDF.",
    "category": "pacientes",
    "keywords": [
      "documento",
      "archivo",
      "pdf",
      "historia",
      "laboratorio",
      "radiografia"
    ],
    "appRoute": "/patients",
    "appRouteLabel": "Ir a Pacientes",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre Archivos adjuntos",
        "description": "Selecciona el paciente y abre la sección Archivos adjuntos."
      },
      {
        "title": "Sube el documento",
        "description": "Pulsa Subir archivo, selecciona el archivo y completa Nombre, Tipo y Descripción. Guarda y revisa el registro."
      },
      {
        "title": "Añade una referencia si corresponde",
        "description": "Usa Agregar referencia para registrar un nombre, un tipo y una URL externa opcional cuando el archivo no se suba a Vetflow."
      },
      {
        "title": "Prepara la historia clínica",
        "description": "En Historial completo, usa Visualizar historia o Exportar PDF. Elige rango de fechas, tamaño de hoja, nivel de detalle y secciones a incluir."
      }
    ],
    "relatedGuides": [
      "actualizar-paciente",
      "catalogos-clinicos"
    ],
    "updatedAt": "2026-09-10"
  }
];

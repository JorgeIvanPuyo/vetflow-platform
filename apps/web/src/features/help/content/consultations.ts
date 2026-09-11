import type { HelpGuide } from "../types";

export const guides: HelpGuide[] = [
  {
    "slug": "iniciar-consulta",
    "title": "Iniciar una consulta",
    "description": "Abre una nueva atención desde la ficha del paciente.",
    "category": "consultas",
    "keywords": [
      "consulta",
      "registrar",
      "iniciar",
      "atencion",
      "medico"
    ],
    "appRoute": "/patients",
    "appRouteLabel": "Ir a Pacientes",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre al paciente",
        "description": "Busca la mascota en Pacientes y comprueba su identidad y sus alertas clínicas."
      },
      {
        "title": "Inicia la atención",
        "description": "Pulsa Nueva consulta en su ficha para abrir el flujo de atención."
      },
      {
        "title": "Completa el inicio",
        "description": "Revisa el Médico responsable y registra la Fecha de consulta y el Motivo de consulta en Anamnesis."
      },
      {
        "title": "Continúa la atención",
        "description": "Usa Siguiente para guardar el paso y avanzar. En el último paso aparecen Guardar borrador y Completar consulta."
      }
    ],
    "relatedGuides": [
      "registrar-paciente",
      "completar-consulta",
      "hallazgos-medicamentos-estudios"
    ],
    "updatedAt": "2026-09-10"
  },
  {
    "slug": "completar-consulta",
    "title": "Completar el flujo de consulta",
    "description": "Documenta la atención siguiendo las seis etapas de la consulta.",
    "category": "consultas",
    "keywords": [
      "consulta",
      "anamnesis",
      "examen",
      "diagnostico",
      "tratamiento",
      "borrador"
    ],
    "appRoute": "/consultations",
    "appRouteLabel": "Ir a Consultas",
    "estimatedMinutes": 5,
    "steps": [
      {
        "title": "Abre la consulta",
        "description": "Selecciona una consulta del listado o inicia una desde la ficha del paciente. En Anamnesis, registra el motivo y los antecedentes relevantes."
      },
      {
        "title": "Completa Examen",
        "description": "Registra los signos vitales y hallazgos del examen físico disponibles."
      },
      {
        "title": "Registra el Diagnóstico presuntivo",
        "description": "Describe tu evaluación inicial y las etiquetas diagnósticas que correspondan."
      },
      {
        "title": "Completa Plan diagnóstico y resultados",
        "description": "Añade los estudios solicitados y resume sus hallazgos cuando estén disponibles."
      },
      {
        "title": "Registra el Diagnóstico final",
        "description": "Completa la conclusión clínica de la atención."
      },
      {
        "title": "Completa el plan terapéutico",
        "description": "En Plan terapéutico e indicaciones, registra medicamentos, indicaciones y próximo control cuando corresponda."
      },
      {
        "title": "Finaliza la consulta",
        "description": "Revisa los datos y pulsa Completar consulta. Si aún necesitas continuar, usa Guardar borrador."
      }
    ],
    "relatedGuides": [
      "iniciar-consulta",
      "hallazgos-medicamentos-estudios",
      "gestionar-seguimiento"
    ],
    "updatedAt": "2026-09-10",
    "tips": [
      "Anterior y Siguiente permiten recorrer los pasos. Solicitar recordatorio se muestra como una funcionalidad en desarrollo."
    ]
  },
  {
    "slug": "hallazgos-medicamentos-estudios",
    "title": "Registrar hallazgos, medicamentos y estudios",
    "description": "Añade detalles clínicos y distingue los medicamentos del inventario de las indicaciones libres.",
    "category": "consultas",
    "keywords": [
      "hallazgos",
      "medicamentos",
      "estudios",
      "laboratorio",
      "dosis",
      "stock"
    ],
    "appRoute": "/consultations",
    "appRouteLabel": "Ir a Consultas",
    "estimatedMinutes": 4,
    "steps": [
      {
        "title": "Registra los hallazgos",
        "description": "En Examen, completa las observaciones y valores medidos durante la atención."
      },
      {
        "title": "Añade los estudios",
        "description": "En Plan diagnóstico y resultados, elige Estudio del catálogo o Escribir manualmente. Completa Estudio, Tipo y Notas y añade el estudio."
      },
      {
        "title": "Registra un medicamento libre",
        "description": "En Plan terapéutico e indicaciones, selecciona Otro medicamento. Completa nombre, dosis e indicaciones; puedes usar una plantilla de prescripción."
      },
      {
        "title": "Registra el consumo de inventario",
        "description": "Para un medicamento usado de la clínica, elige Medicamento de inventario, busca el producto y completa Cantidad usada. Revisa las existencias antes de añadirlo."
      },
      {
        "title": "Revisa los registros",
        "description": "Comprueba estudios, medicamentos e indicaciones antes de completar la consulta."
      }
    ],
    "relatedGuides": [
      "completar-consulta",
      "movimientos-inventario"
    ],
    "updatedAt": "2026-09-10",
    "tips": [
      "Añadir un medicamento de inventario descuenta existencias en ese momento. Eliminar ese medicamento de la consulta no restaura las existencias automáticamente.",
      "Otro medicamento permite dejar una indicación sin descontar inventario."
    ]
  },
  {
    "slug": "gestionar-seguimiento",
    "title": "Crear y consultar un seguimiento",
    "description": "Programa controles y revisa su evolución desde Agenda o la ficha del paciente.",
    "category": "consultas",
    "keywords": [
      "seguimiento",
      "control",
      "vacuna",
      "revision",
      "programar"
    ],
    "appRoute": "/follow-ups",
    "appRouteLabel": "Ir a Seguimientos",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre Nuevo seguimiento",
        "description": "En Agenda, selecciona Seguimientos y pulsa el botón de agregar. También puedes usar Programar seguimiento desde un paciente."
      },
      {
        "title": "Define la atención",
        "description": "Selecciona paciente, profesional, tipo, fecha y hora. Completa Título, Descripción y Notas; puedes elegir una plantilla."
      },
      {
        "title": "Decide si necesita turno",
        "description": "Activa Crear turno en agenda si deseas asociar un turno y revisa su duración."
      },
      {
        "title": "Guarda y consulta",
        "description": "Pulsa Programar seguimiento. Abre su detalle para consultar o editar los datos, completar el seguimiento o cancelarlo con una nota."
      }
    ],
    "relatedGuides": [
      "consultar-agenda",
      "actualizar-paciente"
    ],
    "updatedAt": "2026-09-10"
  }
];

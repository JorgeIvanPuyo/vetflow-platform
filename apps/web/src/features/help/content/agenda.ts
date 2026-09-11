import type { HelpGuide } from "../types";

export const guides: HelpGuide[] = [
  {
    "slug": "consultar-agenda",
    "title": "Consultar la agenda",
    "description": "Revisa los turnos y seguimientos previstos para cada día.",
    "category": "agenda",
    "keywords": [
      "calendario",
      "citas",
      "turnos",
      "dia",
      "profesional"
    ],
    "appRoute": "/agenda",
    "appRouteLabel": "Ir a Agenda",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Selecciona el día",
        "description": "Abre Agenda y cambia la fecha del calendario. Usa Hoy para regresar al día actual."
      },
      {
        "title": "Ajusta los filtros",
        "description": "En Turnos, filtra por Veterinario, Estado o Tipo para encontrar la atención que necesitas."
      },
      {
        "title": "Revisa el detalle",
        "description": "Selecciona un turno para consultar sus datos. Cambia a Seguimientos para ver los controles programados."
      }
    ],
    "relatedGuides": [
      "agendar-cita",
      "actualizar-cita",
      "gestionar-seguimiento"
    ],
    "updatedAt": "2026-09-10"
  },
  {
    "slug": "agendar-cita",
    "title": "Agendar una cita (nuevo turno)",
    "description": "Programa la atención de un paciente con un profesional y un horario.",
    "category": "agenda",
    "keywords": [
      "cita",
      "turno",
      "agendar",
      "reservar",
      "paciente",
      "profesional"
    ],
    "appRoute": "/agenda",
    "appRouteLabel": "Ir a Agenda",
    "estimatedMinutes": 4,
    "steps": [
      {
        "title": "Abre Nuevo turno",
        "description": "En la pestaña Turnos de Agenda, pulsa el botón de agregar identificado como Nuevo turno."
      },
      {
        "title": "Identifica la atención",
        "description": "Completa Título y selecciona el Paciente y el Propietario cuando correspondan."
      },
      {
        "title": "Asigna al profesional y el servicio",
        "description": "Elige Veterinario asignado y Servicio. Si no hay servicios disponibles, completa Tipo."
      },
      {
        "title": "Define el horario",
        "description": "Selecciona Fecha, Hora inicio y Hora fin. Revisa la hora final sugerida al elegir un servicio."
      },
      {
        "title": "Guarda el turno",
        "description": "Completa Motivo y Notas si los necesitas y pulsa Crear turno. Revisa la cita en la agenda."
      }
    ],
    "relatedGuides": [
      "registrar-paciente",
      "administrar-servicios",
      "actualizar-cita"
    ],
    "updatedAt": "2026-09-10",
    "prerequisites": [
      "Debe existir un integrante activo del equipo para asignar el turno."
    ]
  },
  {
    "slug": "actualizar-cita",
    "title": "Consultar o actualizar una cita",
    "description": "Cambia los datos de un turno o registra el resultado de la atención.",
    "category": "agenda",
    "keywords": [
      "editar",
      "cita",
      "turno",
      "cancelar",
      "completado",
      "no asistio"
    ],
    "appRoute": "/agenda",
    "appRouteLabel": "Ir a Agenda",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre el turno",
        "description": "Busca la fecha en Agenda y selecciona el turno. Revisa paciente, profesional, servicio, horario y notas."
      },
      {
        "title": "Actualiza los datos",
        "description": "Pulsa Editar, corrige la información y guarda los cambios."
      },
      {
        "title": "Registra el estado",
        "description": "En Gestionar turno, usa Marcar completado, Cancelar turno o No asistió según lo ocurrido."
      }
    ],
    "relatedGuides": [
      "consultar-agenda",
      "agendar-cita"
    ],
    "updatedAt": "2026-09-10"
  }
];

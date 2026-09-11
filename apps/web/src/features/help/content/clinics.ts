import type { HelpGuide } from "../types";

export const guides: HelpGuide[] = [
  {
    "slug": "crear-clinica",
    "title": "Crear una clínica",
    "description": "Registra una clínica y su primer administrador.",
    "category": "clinicas",
    "keywords": [
      "clinica",
      "crear",
      "superadmin",
      "administrador"
    ],
    "appRoute": "/users",
    "appRouteLabel": "Ir a Usuarios",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre Nueva clínica",
        "description": "En Usuarios, pulsa Nueva clínica con una cuenta de Superadmin."
      },
      {
        "title": "Completa el registro",
        "description": "Ingresa Nombre de la clínica, Correo del administrador y Nombre del administrador."
      },
      {
        "title": "Crea la clínica",
        "description": "Envía el formulario y revisa el mensaje con la clínica y el administrador creados."
      },
      {
        "title": "Entrega el acceso",
        "description": "Si se muestra el enlace para establecer contraseña, cópialo y compártelo con el administrador."
      }
    ],
    "relatedGuides": [
      "cambiar-clinica",
      "invitar-usuario"
    ],
    "updatedAt": "2026-09-10",
    "requiredRoles": [
      "superadmin"
    ]
  },
  {
    "slug": "cambiar-clinica",
    "title": "Cambiar de clínica activa",
    "description": "Selecciona la clínica con la que vas a trabajar como Superadmin.",
    "category": "clinicas",
    "keywords": [
      "clinica activa",
      "cambiar",
      "superadmin",
      "viendo clinica"
    ],
    "appRoute": "/",
    "appRouteLabel": "Ir al inicio",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Localiza el selector",
        "description": "En la vista de computadora, busca Viendo clínica en la parte superior del menú lateral."
      },
      {
        "title": "Selecciona la clínica",
        "description": "Elige una clínica del listado. La aplicación se recargará para aplicar la selección."
      },
      {
        "title": "Comprueba el contexto",
        "description": "Revisa el nombre de la clínica antes de continuar. Para regresar, selecciona Mi clínica."
      }
    ],
    "relatedGuides": [
      "crear-clinica",
      "conocer-vetflow"
    ],
    "updatedAt": "2026-09-10",
    "requiredRoles": [
      "superadmin"
    ]
  }
];

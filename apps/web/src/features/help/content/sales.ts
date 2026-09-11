import type { HelpGuide } from "../types";

export const guides: HelpGuide[] = [
  {
    "slug": "registrar-venta",
    "title": "Registrar una venta",
    "description": "Crea un borrador con productos, servicios o ambos.",
    "category": "ventas",
    "keywords": [
      "venta",
      "vender",
      "mostrador",
      "cliente",
      "producto",
      "servicio"
    ],
    "appRoute": "/sales/new",
    "appRouteLabel": "Ir a Nueva venta",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Completa los datos",
        "description": "Abre Nueva venta. Selecciona Propietario y Paciente si corresponde, o usa Venta de mostrador. Indica Fecha y Notas."
      },
      {
        "title": "Añade productos o servicios",
        "description": "Busca los productos del catálogo. Para un servicio manual, pulsa Agregar servicio y completa su descripción."
      },
      {
        "title": "Revisa las líneas",
        "description": "Comprueba Cantidad, Precio unitario y Descuento % de cada línea."
      },
      {
        "title": "Guarda el borrador",
        "description": "Revisa el total y guarda. El inventario se descontará al confirmar la venta."
      }
    ],
    "relatedGuides": [
      "confirmar-venta",
      "registrar-pagos",
      "documentos-fiscales"
    ],
    "updatedAt": "2026-09-10",
    "tips": [
      "El propietario y el paciente son opcionales. El borrador no genera movimientos ni comprobantes."
    ]
  },
  {
    "slug": "confirmar-venta",
    "title": "Confirmar una venta",
    "description": "Cierra el borrador y descuenta los productos vendidos del inventario.",
    "category": "ventas",
    "keywords": [
      "venta",
      "confirmar",
      "stock",
      "descuento",
      "inventario"
    ],
    "appRoute": "/sales",
    "appRouteLabel": "Ir a Ventas",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre el borrador",
        "description": "En Ventas, busca y selecciona la venta en estado Borrador."
      },
      {
        "title": "Revisa antes de cerrar",
        "description": "Comprueba productos, servicios, cantidades, precios y descuentos. Usa Editar si necesitas corregirlos."
      },
      {
        "title": "Confirma",
        "description": "Pulsa Confirmar venta y revisa el resumen antes de confirmar. Los productos descuentan inventario y los servicios no afectan existencias."
      },
      {
        "title": "Continúa con el cobro",
        "description": "Una vez confirmada, la venta ya no puede editarse. Puedes registrar sus cobros y su comprobante fiscal desde el detalle."
      }
    ],
    "relatedGuides": [
      "registrar-venta",
      "registrar-pagos",
      "documentos-fiscales"
    ],
    "updatedAt": "2026-09-10",
    "prerequisites": [
      "Debes contar con existencias suficientes para los productos incluidos."
    ],
    "tips": [
      "Confirmar una venta no registra automáticamente un pago ni un comprobante fiscal."
    ]
  },
  {
    "slug": "registrar-pagos",
    "title": "Registrar pagos (cobros de una venta)",
    "description": "Registra lo recibido del cliente y actualiza el saldo de la venta.",
    "category": "ventas",
    "keywords": [
      "pago",
      "pagos",
      "cobro",
      "cobrar",
      "efectivo",
      "tarjeta",
      "transferencia"
    ],
    "appRoute": "/sales",
    "appRouteLabel": "Ir a Ventas",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre la venta confirmada",
        "description": "Busca la venta en Ventas y localiza la sección Cobros."
      },
      {
        "title": "Inicia el cobro",
        "description": "Pulsa Registrar cobro y elige Forma de pago."
      },
      {
        "title": "Completa lo recibido",
        "description": "Indica Importe y Fecha y hora. Agrega Referencia y Notas si ayudan a identificar el cobro."
      },
      {
        "title": "Guarda y verifica el saldo",
        "description": "Guarda el cobro y revisa Total, Cobrado y Saldo. Puedes registrar nuevos cobros para completar lo pendiente."
      }
    ],
    "relatedGuides": [
      "formas-pago",
      "saldo-pendiente",
      "confirmar-venta"
    ],
    "updatedAt": "2026-09-10",
    "prerequisites": [
      "La venta debe estar confirmada y debe existir una forma de pago activa."
    ],
    "tips": [
      "No ingreses números de tarjeta, CVV, PIN ni otros datos sensibles.",
      "Si registraste un cobro por error, usa Anular e indica el motivo. El registro queda en el historial."
    ]
  },
  {
    "slug": "saldo-pendiente",
    "title": "Consultar el saldo pendiente",
    "description": "Encuentra ventas sin cobrar o con pagos parciales.",
    "category": "ventas",
    "keywords": [
      "saldo",
      "pendiente",
      "deuda",
      "pago",
      "parcial",
      "cobrado"
    ],
    "appRoute": "/sales",
    "appRouteLabel": "Ir a Ventas",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Filtra las ventas",
        "description": "En Ventas, utiliza Pago para seleccionar Sin cobrar, Parcial o Pagada."
      },
      {
        "title": "Abre el detalle",
        "description": "Selecciona la venta y revisa la sección Cobros."
      },
      {
        "title": "Comprueba el saldo",
        "description": "Compara Total, Cobrado y Saldo. Revisa los cobros activos y anulados antes de registrar otro pago."
      }
    ],
    "relatedGuides": [
      "registrar-pagos",
      "confirmar-venta"
    ],
    "updatedAt": "2026-09-10"
  },
  {
    "slug": "documentos-fiscales",
    "title": "Gestionar documentos fiscales de una venta",
    "description": "Asocia a la venta un comprobante emitido manualmente fuera de Vetflow.",
    "category": "ventas",
    "keywords": [
      "comprobante",
      "fiscal",
      "documento",
      "factura",
      "recibo"
    ],
    "appRoute": "/sales",
    "appRouteLabel": "Ir a Ventas",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre una venta confirmada",
        "description": "En el detalle de la venta, busca Comprobante fiscal."
      },
      {
        "title": "Registra el comprobante",
        "description": "Pulsa Registrar comprobante y selecciona un Emisor habilitado para los productos o servicios vendidos."
      },
      {
        "title": "Completa sus datos",
        "description": "Revisa el Tipo permitido que aparece para el emisor y completa Número y Fecha de emisión. El total se toma de la venta."
      },
      {
        "title": "Guarda y revisa",
        "description": "Selecciona el comprobante PDF, JPEG o PNG y pulsa Registrar comprobante. Después puedes usar Ver, Descargar o Corregir o reemplazar."
      }
    ],
    "relatedGuides": [
      "emisores-fiscales",
      "confirmar-venta",
      "registrar-pagos"
    ],
    "updatedAt": "2026-09-10",
    "prerequisites": [
      "Debe existir un emisor fiscal activo con los tipos de comprobante correspondientes."
    ],
    "tips": [
      "Vetflow registra el comprobante que ya emitiste fuera de la aplicación. El comprobante y el cobro se gestionan por separado."
    ]
  }
];
